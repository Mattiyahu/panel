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
CHECK_INTERVAL = 15
LOW_CPU_THRESHOLD = 0.3
MAX_LOWCPU_TIME = 90
COOLDOWN_TIME = 180 # Aumentado para 3 minutos para garantir estabilidade inicial

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
        if len(self.logs) > 10:
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

    def clear_cache(self):
        self.add_log("🧹 Limpando cache...", "yellow")
        for pkg in self.get_packages():
            self.run_adb(f"pm clear {pkg}")
        self.add_log("✅ Cache limpo!", "green")

    def reconnect(self, pkg):
        self.add_log(f"🔄 Reiniciando: {pkg}", "cyan")
        self.run_adb(f"am force-stop {pkg}")
        time.sleep(2)
        
        # Correção na abertura: Usando Intent VIEW direta com o link VIP
        # Alguns clones precisam do componente específico, outros apenas da action VIEW
        # Vamos tentar a forma mais universal primeiro
        cmd = f"am start -a android.intent.action.VIEW -d '{VIP_LINK}' {pkg}"
        self.run_adb(cmd)
        
        # Tenta forçar modo janela se possível
        self.run_adb(f"am start --task-windowing-mode 5 -a android.intent.action.VIEW -d '{VIP_LINK}' {pkg}")
        
        self.cooldowns[pkg] = time.time() + COOLDOWN_TIME

    def check_ui_state(self, package):
        focus = self.run_adb("dumpsys window windows | grep -E 'mCurrentFocus'")
        if package not in focus:
            return "bubble_or_background"

        ui_xml = self.run_adb("uiautomator dump /sdcard/view.xml > /dev/null 2>&1 && cat /sdcard/view.xml")
        if not ui_xml: return "ok"
        
        ui_lower = ui_xml.lower()
        if any(x in ui_lower for x in ["disconnected", "desconectado", "connection lost"]):
            return "disconnected"
        if all(x in ui_lower for x in ["home", "discover", "avatar"]):
            return "home"
        if "atlas" in ui_lower and ("key" in ui_lower or "enter" in ui_lower):
            return "key_request"
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
                    # Se estiver em cooldown, apenas ignora e passa para o próximo
                    if time.time() < self.cooldowns.get(pkg, 0):
                        continue
                    
                    # Verifica se o processo existe
                    pid = self.run_adb(f"pidof {pkg}")
                    
                    # Se o processo NÃO existe, ele caiu. Reinicia.
                    if not pid:
                        self.add_log(f"❌ {pkg} fechado. Reiniciando...", "red")
                        self.reconnect(pkg)
                        continue

                    # Se o processo EXISTE, verifica o estado da interface (UI)
                    state = self.check_ui_state(pkg)
                    
                    # SÓ REINICIA se o estado for explicitamente problemático
                    if state in ["disconnected", "home", "bubble_or_background"]:
                        self.add_log(f"⚠️ {pkg} em estado crítico: {state}", "yellow")
                        self.reconnect(pkg)
                    # Se o estado for "ok", não faz nada, deixa o jogo rodar.
                
                live.update(self.make_layout())
                time.sleep(CHECK_INTERVAL)

    def make_layout(self):
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", size=12),
            Layout(name="footer", size=12)
        )
        
        # Header
        layout["header"].update(Panel(Align.center("[bold magenta]MSA ROBLOX MANAGER v2.0[/bold magenta]"), border_style="magenta"))
        
        # Main - Status dos Pacotes
        table = Table(expand=True, border_style="cyan")
        table.add_column("Package", style="green")
        table.add_column("Status", style="white")
        table.add_column("Cooldown", style="yellow")
        
        for pkg in self.packages:
            cd = max(0, int(self.cooldowns.get(pkg, 0) - time.time()))
            status = "[green]Ativo[/green]" if cd == 0 else "[yellow]Aguardando[/yellow]"
            table.add_row(pkg, status, f"{cd}s")
            
        layout["main"].update(Panel(table, title="[bold cyan]Monitoramento Ativo[/bold cyan]", border_style="cyan"))
        
        # Footer - Logs
        log_text = Text("\n".join(self.logs))
        layout["footer"].update(Panel(log_text, title="[bold yellow]Logs do Sistema[/bold yellow]", border_style="yellow"))
        
        return layout

manager = RobloxManager()

def get_banner():
    banner = """
    [bold cyan]
    ███╗   ███╗███████╗ █████╗ 
    ████╗ ████║██╔════╝██╔══██╗
    ██╔████╔██║███████╗███████║
    ██║╚██╔╝██║╚════██║██╔══██║
    ██║ ╚═╝ ██║███████║██║  ██║
    ╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝[/bold cyan]
    """
    return Align.center(banner)

def show_main_menu():
    console.clear()
    rprint(get_banner())
    
    # Status Panel
    status_info = f"🔗 [bold white]VIP:[/bold white] {'[green]OK[/green]' if VIP_LINK else '[red]MISSING[/red]'} | "
    status_info += f"⚓ [bold white]Webhook:[/bold white] {'[green]OK[/green]' if WEBHOOK_URL else '[red]MISSING[/red]'}"
    rprint(Panel(Align.center(status_info), border_style="white", title="Config Status"))

    # Menu Grid
    menu_table = Table.grid(expand=True, padding=1)
    menu_table.add_column(justify="center", ratio=1)
    menu_table.add_column(justify="center", ratio=1)
    
    menu_table.add_row(
        Panel("[bold green][1] 🚀 START REJOIN[/bold green]", border_style="green", padding=(1, 2)),
        Panel("[bold blue][2] 🛠️ AUTO SETUP[/bold blue]", border_style="blue", padding=(1, 2))
    )
    menu_table.add_row(
        Panel("[bold cyan][3] 📋 LIST CLONES[/bold cyan]", border_style="cyan", padding=(1, 2)),
        Panel("[bold yellow][4] 🧹 CLEAR CACHE[/bold yellow]", border_style="yellow", padding=(1, 2))
    )
    menu_table.add_row(
        Panel("[bold magenta][5] ⚙️ SETTINGS[/bold magenta]", border_style="magenta", padding=(1, 2)),
        Panel("[bold red][0] ❌ EXIT[/bold red]", border_style="red", padding=(1, 2))
    )
    
    rprint(menu_table)

def manage_settings():
    global VIP_LINK, WEBHOOK_URL
    while True:
        console.clear()
        rprint(Panel(Align.center("[bold magenta]SETTINGS MENU[/bold magenta]"), border_style="magenta"))
        rprint(f"[1] [cyan]Edit VIP Link[/cyan]\n[2] [cyan]Edit Webhook URL[/cyan]\n[3] [red]Reset All[/red]\n[0] [green]Back[/green]")
        
        choice = Prompt.ask("\nSelect", choices=["1", "2", "3", "0"])
        if choice == "1":
            VIP_LINK = Prompt.ask("Enter VIP Link")
        elif choice == "2":
            WEBHOOK_URL = Prompt.ask("Enter Webhook URL")
        elif choice == "3":
            VIP_LINK = ""
            WEBHOOK_URL = ""
            rprint("[red]Settings reset![/red]")
            time.sleep(1)
        elif choice == "0":
            break
        
        save_config({"vip_link": VIP_LINK, "webhook_url": WEBHOOK_URL})

def main():
    while True:
        show_main_menu()
        choice = Prompt.ask("\n[bold white]Command[/bold white]", choices=["1", "2", "3", "4", "5", "0"])

        if choice == "1":
            manager.monitor_loop()
        elif choice == "2":
            subprocess.run("bash setup.sh", shell=True)
            Prompt.ask("\nPress Enter to return")
        elif choice == "3":
            pkgs = manager.get_packages()
            t = Table(title="Detected Clones", border_style="cyan")
            t.add_column("ID", justify="center")
            t.add_column("Package Name")
            for i, p in enumerate(pkgs): t.add_row(str(i+1), p)
            rprint(t)
            Prompt.ask("\nPress Enter to return")
        elif choice == "4":
            manager.clear_cache()
            Prompt.ask("\nPress Enter to return")
        elif choice == "5":
            manage_settings()
        elif choice == "0":
            rprint("[bold red]Exiting...[/bold red]")
            break

if __name__ == "__main__":
    main()
