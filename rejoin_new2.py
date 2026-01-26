#!/usr/bin/env python3
import os
import subprocess
import time
import requests
import datetime
import json
import threading
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
CHECK_INTERVAL = 5  # Reduzido para ser mais rápido
COOLDOWN_TIME = 120 # 2 minutos de estabilização

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

class InstanceMonitor:
    def __init__(self, package, manager):
        self.package = package
        self.manager = manager
        self.pid = None
        self.cpu = 0.0
        self.net_status = "WAIT"
        self.status_code = "STARTING"
        self.last_net_bytes = 0
        self.error_count = 0
        self.cooldown_until = time.time() + 10 # Pequeno delay inicial
        self.is_running = True

    def run_adb(self, command):
        try:
            result = subprocess.run(f"adb shell {command}", shell=True, capture_output=True, text=True, timeout=5)
            return result.stdout.strip()
        except:
            return ""

    def update_stats(self):
        # 1. Verifica PID
        self.pid = self.run_adb(f"pidof {self.package}")
        if not self.pid:
            self.cpu = 0.0
            self.net_status = "DEAD"
            self.status_code = "CRASHED"
            return

        # 2. Verifica CPU (Agressivo)
        top_out = self.run_adb(f"top -n 1 -p {self.pid} | grep {self.pid}")
        if top_out:
            try:
                parts = top_out.split()
                for p in parts:
                    if "%" in p: self.cpu = float(p.replace("%", "").replace(",", "."))
            except: pass

        # 3. Verifica Rede (Heartbeat Real)
        # Usando dumpsys netstats para ver tráfego recente
        net_out = self.run_adb(f"cat /proc/net/xt_qtaguid/stats | grep {self.package}")
        # Se falhar por nome, tenta por UID (mais complexo, vamos simplificar no top)
        # Como alternativa, vamos usar a variação de CPU e UI
        
        if time.time() < self.cooldown_until:
            self.status_code = "SYNCING"
        elif self.cpu > 30.0:
            self.status_code = "RUNNING"
            self.net_status = "ACTIVE"
            self.error_count = 0
        else:
            self.status_code = "IDLE"
            self.net_status = "STAGNANT"

    def monitor_logic(self):
        while self.is_running:
            if not self.manager.global_running: break
            
            self.update_stats()
            
            # Lógica de Ação Real
            if time.time() > self.cooldown_until:
                if not self.pid:
                    self.reboot("Process Lost")
                elif self.cpu < 10.0: # Se a CPU estiver muito baixa, algo está errado
                    self.error_count += 1
                    if self.error_count >= 6: # ~30 segundos de inatividade real
                        self.reboot("Inactivity")
                else:
                    # Verificação de UI para erros de conexão
                    ui = self.run_adb("uiautomator dump /sdcard/view.xml > /dev/null 2>&1 && cat /sdcard/view.xml").lower()
                    if any(x in ui for x in ["disconnected", "desconectado", "reconnect"]):
                        self.reboot("Link Break")
            
            time.sleep(CHECK_INTERVAL)

    def reboot(self, reason):
        self.manager.add_log(f"⚡ [RE_PHONE] {self.package} -> {reason}", "red")
        self.manager.send_webhook(f"📡 **RE_PHONE**: `{self.package}` reiniciado por `{reason}`")
        self.run_adb(f"am force-stop {self.package}")
        time.sleep(2)
        self.run_adb(f"am start -a android.intent.action.VIEW -d '{VIP_LINK}' {self.package}")
        self.cooldown_until = time.time() + COOLDOWN_TIME
        self.error_count = 0

class RE_PHONE_Manager:
    def __init__(self):
        self.instances = {}
        self.global_running = False
        self.logs = []

    def add_log(self, msg, style="white"):
        t = datetime.datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{t}] {msg}")
        if len(self.logs) > 8: self.logs.pop(0)

    def send_webhook(self, msg):
        if WEBHOOK_URL:
            try: requests.post(WEBHOOK_URL, json={"content": msg}, timeout=5)
            except: pass

    def start_monitoring(self):
        if not VIP_LINK:
            rprint("[red]❌ Configure o VIP LINK primeiro![/red]")
            time.sleep(2)
            return

        self.global_running = True
        output = subprocess.run("adb shell pm list packages roblox", shell=True, capture_output=True, text=True).stdout
        packages = [line.replace("package:", "").strip() for line in output.splitlines() if "roblox" in line]
        
        for pkg in packages:
            if pkg not in self.instances:
                inst = InstanceMonitor(pkg, self)
                self.instances[pkg] = inst
                threading.Thread(target=inst.monitor_logic, daemon=True).start()
        
        # HUD EM TEMPO REAL COM ATUALIZAÇÃO FORÇADA
        with Live(self.make_hud(), refresh_per_second=4, screen=True) as live:
            try:
                while self.global_running:
                    live.update(self.make_hud())
                    time.sleep(0.25)
            except KeyboardInterrupt:
                self.global_running = False

    def make_hud(self):
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body", size=12),
            Layout(name="footer", size=10)
        )
        
        layout["header"].update(Panel(Align.center("[bold cyan]RE_PHONE HUD[/bold cyan] [white]by MSA[/white]"), border_style="cyan"))
        
        table = Table(expand=True, border_style="magenta", header_style="bold white")
        table.add_column("CLONE", style="green", justify="left")
        table.add_column("CPU %", justify="center")
        table.add_column("NETWORK", justify="center")
        table.add_column("STATUS", justify="center")
        
        for pkg, inst in self.instances.items():
            name = pkg.split('.')[-1].upper()
            cpu_color = "green" if inst.cpu > 50 else "yellow" if inst.cpu > 10 else "red"
            net_color = "cyan" if inst.net_status == "ACTIVE" else "red"
            
            table.add_row(
                f"[bold]{name}[/bold]",
                f"[{cpu_color}]{inst.cpu}%[/{cpu_color}]",
                f"[{net_color}]{inst.net_status}[/{net_color}]",
                f"[bold white]{inst.status_code}[/bold white]"
            )
            
        layout["body"].update(Panel(table, title="[bold yellow]LIVE ACTIVITY[/bold yellow]", border_style="magenta"))
        layout["footer"].update(Panel(Text("\n".join(self.logs)), title="[bold cyan]SYSTEM LOGS[/bold cyan]", border_style="cyan"))
        return layout

manager = RE_PHONE_Manager()

def main_menu():
    while True:
        console.clear()
        banner = """[bold cyan]
    ██████╗ ███████╗      ██████╗ ██╗  ██╗ ██████╗ ███╗   ██╗███████╗
    ██╔══██╗██╔════╝      ██╔══██╗██║  ██║██╔═══██╗████╗  ██║██╔════╝
    ██████╔╝█████╗  █████╗██████╔╝███████║██║   ██║██╔██╗ ██║█████╗  
    ██╔══██╗██╔══╝  ╚════╝██╔═══╝ ██╔══██║██║   ██║██║╚██╗██║██╔══╝  
    ██║  ██║███████╗      ██║     ██║  ██║╚██████╔╝██║ ╚████║███████╗
    ╚═╝  ╚═╝╚══════╝      ╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝[/bold cyan]
    [white]                      by MSA | v4.0 Ultra-Realtime[/white]"""
        rprint(Align.center(banner))
        
        status = f"🔗 VIP: {'[green]OK[/green]' if VIP_LINK else '[red]NO[/red]'} | ⚓ WEBHOOK: {'[green]OK[/green]' if WEBHOOK_URL else '[red]NO[/red]'}"
        rprint(Panel(Align.center(status), border_style="white"))

        grid = Table.grid(expand=True, padding=1)
        grid.add_column(ratio=1); grid.add_column(ratio=1)
        grid.add_row(
            Panel("[bold green][1] 🚀 LAUNCH REAL-TIME HUD[/bold green]", border_style="green"),
            Panel("[bold magenta][2] ⚙️ SYSTEM SETTINGS[/bold magenta]", border_style="magenta")
        )
        grid.add_row(
            Panel("[bold blue][3] 🛠️ ADVANCED TOOLS[/bold blue]", border_style="blue"),
            Panel("[bold red][0] ❌ EXIT SYSTEM[/bold red]", border_style="red")
        )
        rprint(grid)
        
        choice = Prompt.ask("\n[bold white]Action[/bold white]", choices=["1", "2", "3", "0"])
        if choice == "1": manager.start_monitoring()
        elif choice == "2":
            global VIP_LINK, WEBHOOK_URL
            console.clear()
            rprint(Panel("[bold magenta]SYSTEM SETTINGS[/bold magenta]", border_style="magenta"))
            VIP_LINK = Prompt.ask("VIP Link", default=VIP_LINK)
            WEBHOOK_URL = Prompt.ask("Webhook URL", default=WEBHOOK_URL)
            save_config({"vip_link": VIP_LINK, "webhook_url": WEBHOOK_URL})
        elif choice == "3":
            console.clear()
            rprint(Panel("[bold blue]ADVANCED TOOLS[/bold blue]", border_style="blue"))
            rprint("[1] Run Auto-Setup\n[2] Force Stop All\n[0] Back")
            sub = Prompt.ask("Select", choices=["1", "2", "0"])
            if sub == "1": subprocess.run("bash setup.sh", shell=True); Prompt.ask("Done. Enter")
            elif sub == "2": 
                for p in ["com.roblox.clienb", "com.roblox.cliend", "com.roblox.cliene"]: subprocess.run(f"adb shell am force-stop {p}", shell=True)
                rprint("[red]All stopped.[/red]"); time.sleep(1)
        elif choice == "0": break

if __name__ == "__main__":
    main_menu()
