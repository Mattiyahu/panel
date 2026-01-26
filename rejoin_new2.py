#!/usr/bin/env python3
import os
import subprocess
import time
import requests
import psutil
import datetime
import json
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.align import Align
from rich import print as rprint

# Configurações Globais
console = Console()
CONFIG_FILE = "config.json"
CHECK_INTERVAL = 10
LOW_CPU_THRESHOLD = 30.0  # Abaixo de 30% = Fora do jogo
HIGH_CPU_THRESHOLD = 100.0 # Acima de 100% = No jogo
MAX_LOWCPU_COUNT = 3      # Quantas vezes seguidas com CPU baixa antes de reiniciar
COOLDOWN_TIME = 60        # Cooldown reduzido para 1 minuto

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {"vip_link": "", "webhook_url": ""}

def save_config(config_data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f, indent=4)

config = load_config()
VIP_LINK = config.get("vip_link", "")
WEBHOOK_URL = config.get("webhook_url", "")

class RobloxManager:
    def __init__(self):
        self.packages = []
        self.lowcpu_count = {}
        self.cooldowns = {}
        self.is_running = False
        self.logs = []

    def add_log(self, msg, style="white"):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{timestamp}] {msg}")
        if len(self.logs) > 12:
            self.logs.pop(0)

    def run_adb(self, command):
        try:
            result = subprocess.run(f"adb shell {command}", shell=True, capture_output=True, text=True)
            return result.stdout.strip()
        except:
            return ""

    def get_packages(self):
        output = self.run_adb("pm list packages roblox")
        self.packages = [line.replace("package:", "").strip() for line in output.splitlines() if "roblox" in line]
        for pkg in self.packages:
            if pkg not in self.lowcpu_count:
                self.lowcpu_count[pkg] = 0
                self.cooldowns[pkg] = 0
        return self.packages

    def send_webhook(self, message):
        if not WEBHOOK_URL: return
        try:
            requests.post(WEBHOOK_URL, json={"content": message}, timeout=5)
        except:
            pass

    def get_cpu_usage(self, pid):
        # Pega a CPU do processo via top
        output = self.run_adb(f"top -n 1 -p {pid} | grep {pid}")
        if not output: return 0.0
        try:
            parts = output.split()
            # No Android, a CPU costuma ser a 9ª coluna no top
            for part in parts:
                if "%" in part:
                    return float(part.replace("%", "").replace(",", "."))
            # Se não achar %, tenta pegar o valor numérico que faz sentido
            return float(parts[8].replace(",", "."))
        except:
            return 0.0

    def reconnect(self, pkg, reason="Desconhecido"):
        self.add_log(f"🔄 Reiniciando {pkg} ({reason})", "cyan")
        self.send_webhook(f"⚠️ **REJ_PHONE Alert**: Reiniciando `{pkg}`\nMotivo: `{reason}`")
        
        self.run_adb(f"am force-stop {pkg}")
        time.sleep(2)
        
        # Comando de abertura otimizado
        cmd = f"am start -a android.intent.action.VIEW -d '{VIP_LINK}' {pkg}"
        self.run_adb(cmd)
        
        # Tenta forçar modo janela
        self.run_adb(f"am start --task-windowing-mode 5 -a android.intent.action.VIEW -d '{VIP_LINK}' {pkg}")
        
        self.cooldowns[pkg] = time.time() + COOLDOWN_TIME
        self.lowcpu_count[pkg] = 0

    def check_ui_state(self, package):
        focus = self.run_adb("dumpsys window windows | grep -E 'mCurrentFocus'")
        if package not in focus:
            return "bubble_or_background"

        ui_xml = self.run_adb("uiautomator dump /sdcard/view.xml > /dev/null 2>&1 && cat /sdcard/view.xml")
        if not ui_xml: return "ok"
        
        ui_lower = ui_xml.lower()
        if any(x in ui_lower for x in ["disconnected", "desconectado", "connection lost", "reconnect"]):
            return "disconnected"
        if all(x in ui_lower for x in ["home", "discover", "avatar"]):
            return "home"
        return "ok"

    def monitor_loop(self):
        if not VIP_LINK:
            self.add_log("❌ Erro: VIP LINK não configurado!", "red")
            return
        
        self.is_running = True
        self.get_packages()
        
        with Live(self.make_layout(), refresh_per_second=1) as live:
            while self.is_running:
                for pkg in self.packages:
                    if time.time() < self.cooldowns.get(pkg, 0): continue
                    
                    pid = self.run_adb(f"pidof {pkg}")
                    if not pid:
                        self.reconnect(pkg, "Processo fechado")
                        continue

                    # Verificação de CPU (Prioridade)
                    cpu = self.get_cpu_usage(pid)
                    if cpu < LOW_CPU_THRESHOLD:
                        self.lowcpu_count[pkg] += 1
                        if self.lowcpu_count[pkg] >= MAX_LOWCPU_COUNT:
                            self.reconnect(pkg, f"CPU Baixa ({cpu}%)")
                            continue
                    else:
                        self.lowcpu_count[pkg] = 0

                    # Verificação de UI
                    state = self.check_ui_state(pkg)
                    if state in ["disconnected", "home", "bubble_or_background"]:
                        self.reconnect(pkg, f"Estado UI: {state}")
                
                live.update(self.make_layout())
                time.sleep(CHECK_INTERVAL)

    def make_layout(self):
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", size=12),
            Layout(name="footer", size=14)
        )
        
        layout["header"].update(Panel(Align.center("[bold cyan]REJ_PHONE[/bold cyan] [white]by MSA[/white]"), border_style="cyan"))
        
        table = Table(expand=True, border_style="blue")
        table.add_column("Package", style="green")
        table.add_column("CPU", style="magenta")
        table.add_column("Status", style="white")
        table.add_column("Cooldown", style="yellow")
        
        for pkg in self.packages:
            cd = max(0, int(self.cooldowns.get(pkg, 0) - time.time()))
            pid = self.run_adb(f"pidof {pkg}")
            cpu = self.get_cpu_usage(pid) if pid else 0.0
            
            status = "[green]Jogando[/green]" if cpu > HIGH_CPU_THRESHOLD else "[yellow]Carregando[/yellow]"
            if cd > 0: status = "[bold blue]Estabilizando[/bold blue]"
            
            table.add_row(pkg, f"{cpu}%", status, f"{cd}s")
            
        layout["main"].update(Panel(table, title="[bold blue]Live Monitor[/bold blue]", border_style="blue"))
        
        log_text = Text("\n".join(self.logs))
        layout["footer"].update(Panel(log_text, title="[bold yellow]System Activity[/bold yellow]", border_style="yellow"))
        
        return layout

manager = RobloxManager()

def get_banner():
    banner = """
    [bold cyan]
    ██████╗ ███████╗      ██████╗ ██╗  ██╗ ██████╗ ███╗   ██╗███████╗
    ██╔══██╗██╔════╝      ██╔══██╗██║  ██║██╔═══██╗████╗  ██║██╔════╝
    ██████╔╝█████╗  █████╗██████╔╝███████║██║   ██║██╔██╗ ██║█████╗  
    ██╔══██╗██╔══╝  ╚════╝██╔═══╝ ██╔══██║██║   ██║██║╚██╗██║██╔══╝  
    ██║  ██║███████╗      ██║     ██║  ██║╚██████╔╝██║ ╚████║███████╗
    ╚═╝  ╚═╝╚══════╝      ╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝
    [/bold cyan][white]                      by MSA[/white]
    """
    return Align.center(banner)

def show_main_menu():
    console.clear()
    rprint(get_banner())
    
    status_info = f"🔗 VIP: {'[green]SET[/green]' if VIP_LINK else '[red]EMPTY[/red]'} | ⚓ Webhook: {'[green]SET[/green]' if WEBHOOK_URL else '[red]EMPTY[/red]'}"
    rprint(Panel(Align.center(status_info), border_style="white"))

    menu_table = Table.grid(expand=True, padding=1)
    menu_table.add_column(justify="center", ratio=1)
    menu_table.add_column(justify="center", ratio=1)
    
    menu_table.add_row(
        Panel("[bold green][1] 🚀 START MONITOR[/bold green]", border_style="green"),
        Panel("[bold blue][2] 🛠️ AUTO SETUP[/bold blue]", border_style="blue")
    )
    menu_table.add_row(
        Panel("[bold cyan][3] 📋 LIST CLONES[/bold cyan]", border_style="cyan"),
        Panel("[bold yellow][4] 🧹 CLEAR CACHE[/bold yellow]", border_style="yellow")
    )
    menu_table.add_row(
        Panel("[bold magenta][5] ⚙️ SETTINGS[/bold magenta]", border_style="magenta"),
        Panel("[bold red][0] ❌ EXIT[/bold red]", border_style="red")
    )
    rprint(menu_table)

def manage_settings():
    global VIP_LINK, WEBHOOK_URL
    while True:
        console.clear()
        rprint(Panel(Align.center("[bold magenta]SETTINGS[/bold magenta]"), border_style="magenta"))
        rprint(f"1. Edit VIP Link\n2. Edit Webhook URL\n3. Reset\n0. Back")
        choice = Prompt.ask("\nSelect", choices=["1", "2", "3", "0"])
        if choice == "1": VIP_LINK = Prompt.ask("VIP Link")
        elif choice == "2": WEBHOOK_URL = Prompt.ask("Webhook URL")
        elif choice == "3": VIP_LINK = WEBHOOK_URL = ""
        elif choice == "0": break
        save_config({"vip_link": VIP_LINK, "webhook_url": WEBHOOK_URL})

def main():
    while True:
        show_main_menu()
        choice = Prompt.ask("\n[bold white]Command[/bold white]", choices=["1", "2", "3", "4", "5", "0"])
        if choice == "1": manager.monitor_loop()
        elif choice == "2": subprocess.run("bash setup.sh", shell=True); Prompt.ask("\nEnter to return")
        elif choice == "3":
            pkgs = manager.get_packages()
            t = Table(title="Clones", border_style="cyan")
            t.add_column("ID"); t.add_column("Package")
            for i, p in enumerate(pkgs): t.add_row(str(i+1), p)
            rprint(t); Prompt.ask("\nEnter to return")
        elif choice == "4": manager.clear_cache(); Prompt.ask("\nEnter to return")
        elif choice == "5": manage_settings()
        elif choice == "0": break

if __name__ == "__main__":
    main()
