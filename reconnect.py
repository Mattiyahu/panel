#!/usr/bin/env python3
import os
import subprocess
import time
import requests
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
from rich.columns import Columns
from rich import print as rprint

# Configurações Globais
console = Console()
CONFIG_FILE = "config.json"
CHECK_INTERVAL = 15
LOW_CPU_THRESHOLD = 15.0  # Mais tolerante ainda
MAX_LOWCPU_COUNT = 8      # Espera 2 minutos de CPU baixa
COOLDOWN_TIME = 150       # 2.5 minutos para estabilizar

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {"vip_link": "", "webhook_url": "", "auto_execute": ""}

def save_config(config_data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f, indent=4)

config = load_config()
VIP_LINK = config.get("vip_link", "")
WEBHOOK_URL = config.get("webhook_url", "")
AUTO_EXECUTE = config.get("auto_execute", "")

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
        if len(self.logs) > 15:
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
        output = self.run_adb(f"top -n 1 -p {pid} | grep {pid}")
        if not output: return 0.0
        try:
            parts = output.split()
            for part in parts:
                if "%" in part:
                    return float(part.replace("%", "").replace(",", "."))
            return float(parts[8].replace(",", "."))
        except:
            return 0.0

    def reconnect(self, pkg, reason="Desconhecido"):
        # ISOLAMENTO: Só reinicia o pacote específico
        self.add_log(f"🔄 Reiniciando {pkg} | Motivo: {reason}", "cyan")
        self.send_webhook(f"⚠️ **REJ_PHONE**: Reiniciando `{pkg}`\nMotivo: `{reason}`")
        
        self.run_adb(f"am force-stop {pkg}")
        time.sleep(3)
        
        # Abertura focada
        cmd = f"am start -a android.intent.action.VIEW -d '{VIP_LINK}' {pkg}"
        self.run_adb(cmd)
        
        # Define cooldown individual longo para evitar re-trigger
        self.cooldowns[pkg] = time.time() + COOLDOWN_TIME
        self.lowcpu_count[pkg] = 0

    def check_ui_state(self, package):
        # DETECÇÃO MELHORADA: Ignora 'bubble' se a CPU estiver minimamente ativa
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
                        self.reconnect(pkg, "App fechado")
                        continue

                    cpu = self.get_cpu_usage(pid)
                    
                    # Só checa UI e CPU se não estiver em cooldown
                    if cpu < LOW_CPU_THRESHOLD:
                        self.lowcpu_count[pkg] += 1
                        if self.lowcpu_count[pkg] >= MAX_LOWCPU_COUNT:
                            self.reconnect(pkg, f"Inatividade ({cpu}%)")
                            continue
                    else:
                        self.lowcpu_count[pkg] = 0
                        
                        # Se a CPU está alta, o jogo está rodando. 
                        # Só checa UI para erros críticos (desconexão)
                        state = self.check_ui_state(pkg)
                        if state in ["disconnected", "home"]:
                            self.reconnect(pkg, f"Erro UI: {state}")
                
                live.update(self.make_layout())
                time.sleep(CHECK_INTERVAL)

    def make_layout(self):
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", size=12),
            Layout(name="footer", size=16)
        )
        layout["header"].update(Panel(Align.center("[bold cyan]REJ_PHONE[/bold cyan] [white]by MSA[/white]"), border_style="cyan"))
        
        table = Table(expand=True, border_style="blue")
        table.add_column("Package", style="green")
        table.add_column("CPU", style="magenta")
        table.add_column("Status", style="white")
        table.add_column("Wait", style="yellow")
        
        for pkg in self.packages:
            cd = max(0, int(self.cooldowns.get(pkg, 0) - time.time()))
            pid = self.run_adb(f"pidof {pkg}")
            cpu = self.get_cpu_usage(pid) if pid else 0.0
            
            status = "[green]Rodando[/green]" if cpu > 50 else "[yellow]Carregando[/yellow]"
            if cd > 0: status = "[bold blue]Estabilizando[/bold blue]"
            
            table.add_row(pkg, f"{cpu}%", status, f"{cd}s" if cd > 0 else f"{self.lowcpu_count[pkg]}/{MAX_LOWCPU_COUNT}")
            
        layout["main"].update(Panel(table, title="[bold blue]Live Monitor[/bold blue]", border_style="blue"))
        layout["footer"].update(Panel(Text("\n".join(self.logs)), title="[bold yellow]System Activity[/bold yellow]", border_style="yellow"))
        return layout

manager = RobloxManager()

def show_main_menu():
    console.clear()
    banner = """[bold cyan]
    ██████╗ ███████╗      ██████╗ ██╗  ██╗ ██████╗ ███╗   ██╗███████╗
    ██╔══██╗██╔════╝      ██╔══██╗██║  ██║██╔═══██╗████╗  ██║██╔════╝
    ██████╔╝█████╗  █████╗██████╔╝███████║██║   ██║██╔██╗ ██║█████╗  
    ██╔══██╗██╔══╝  ╚════╝██╔═══╝ ██╔══██║██║   ██║██║╚██╗██║██╔══╝  
    ██║  ██║███████╗      ██║     ██║  ██║╚██████╔╝██║ ╚████║███████╗
    ╚═╝  ╚═╝╚══════╝      ╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝[/bold cyan]"""
    rprint(Align.center(banner))
    rprint(Align.center("[white]v3.0 - Advanced Multi-Instance Control | by MSA[/white]\n"))

    menu = Table.grid(expand=True, padding=1)
    menu.add_column(ratio=1); menu.add_column(ratio=1)
    menu.add_row(
        Panel("[bold green][1] 🚀 START MONITOR[/bold green]\n[dim]Inicia o Rejoin Inteligente[/dim]", border_style="green"),
        Panel("[bold magenta][2] ⚙️ CONFIGURATIONS[/bold magenta]\n[dim]VIP, Webhook, Auto-Exec[/dim]", border_style="magenta")
    )
    menu.add_row(
        Panel("[bold blue][3] 🛠️ ADVANCED TOOLS[/bold blue]\n[dim]Setup, ADB, Shell[/dim]", border_style="blue"),
        Panel("[bold yellow][4] 📋 INSTANCE INFO[/bold yellow]\n[dim]Listar clones e PIDs[/dim]", border_style="yellow")
    )
    menu.add_row(
        Panel("[bold red][0] ❌ EXIT[/bold red]\n[dim]Fechar o painel[/dim]", border_style="red"),
        Panel("[bold white][?] HELP[/bold white]\n[dim]Suporte e Dicas[/dim]", border_style="white")
    )
    rprint(menu)

def sub_menu_configs():
    global VIP_LINK, WEBHOOK_URL, AUTO_EXECUTE
    while True:
        console.clear()
        rprint(Panel("[bold magenta]⚙️ CONFIGURATIONS[/bold magenta]", border_style="magenta"))
        rprint(f"[1] Edit VIP Link [dim]({VIP_LINK[:20]}...)[/dim]")
        rprint(f"[2] Edit Webhook URL [dim]({WEBHOOK_URL[:20]}...)[/dim]")
        rprint(f"[3] Auto-Execute Script [dim]({AUTO_EXECUTE})[/dim]")
        rprint("[0] Back")
        
        c = Prompt.ask("\nSelect", choices=["1", "2", "3", "0"])
        if c == "1": VIP_LINK = Prompt.ask("VIP Link")
        elif c == "2": WEBHOOK_URL = Prompt.ask("Webhook URL")
        elif c == "3": AUTO_EXECUTE = Prompt.ask("Script Name (ex: main.lua)")
        elif c == "0": break
        save_config({"vip_link": VIP_LINK, "webhook_url": WEBHOOK_URL, "auto_execute": AUTO_EXECUTE})

def sub_menu_tools():
    while True:
        console.clear()
        rprint(Panel("[bold blue]🛠️ ADVANCED TOOLS[/bold blue]", border_style="blue"))
        rprint("[1] Run Auto-Setup (Dependencies)")
        rprint("[2] ADB Connect (Wireless)")
        rprint("[3] Force Stop All Roblox")
        rprint("[4] Clear System Logs")
        rprint("[0] Back")
        
        c = Prompt.ask("\nSelect", choices=["1", "2", "3", "4", "0"])
        if c == "1": subprocess.run("bash setup.sh", shell=True); Prompt.ask("Enter to return")
        elif c == "2": ip = Prompt.ask("Device IP"); subprocess.run(f"adb connect {ip}", shell=True); Prompt.ask("Enter to return")
        elif c == "3": 
            for p in manager.get_packages(): manager.run_adb(f"am force-stop {p}")
            rprint("[red]Todos parados![/red]"); time.sleep(1)
        elif c == "4": manager.logs = []; rprint("[green]Logs limpos![/green]"); time.sleep(1)
        elif c == "0": break

def main():
    while True:
        show_main_menu()
        choice = Prompt.ask("\n[bold white]Action[/bold white]", choices=["1", "2", "3", "4", "0"])
        if choice == "1": manager.monitor_loop()
        elif choice == "2": sub_menu_configs()
        elif choice == "3": sub_menu_tools()
        elif choice == "4":
            pkgs = manager.get_packages()
            t = Table(title="Detected Clones", border_style="cyan")
            t.add_column("ID"); t.add_column("Package"); t.add_column("PID")
            for i, p in enumerate(pkgs): t.add_row(str(i+1), p, manager.run_adb(f"pidof {p}"))
            rprint(t); Prompt.ask("\nEnter to return")
        elif choice == "0": break

if __name__ == "__main__":
    main()
