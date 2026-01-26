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
CHECK_INTERVAL = 3  # Reduzido para ser ultra-rápido
COOLDOWN_TIME = 120

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"vip_link": "", "webhook_url": ""}

def save_config(config_data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f, indent=4)

_config = load_config()
VIP_LINK = _config.get("vip_link", "")
WEBHOOK_URL = _config.get("webhook_url", "")

class InstanceMonitor:
    def __init__(self, package, manager):
        self.package = package
        self.manager = manager
        self.pid = None
        self.cpu = 0.0
        self.net_usage = "0 KB/s"
        self.last_bytes = 0
        self.status_code = "SYNC"
        self.error_count = 0
        self.cooldown_until = time.time() + 5
        self.is_running = True
        self.lock = threading.Lock()

    def run_adb(self, command):
        try:
            # Timeout curto para não travar a thread
            result = subprocess.run(f"adb shell {command}", shell=True, capture_output=True, text=True, timeout=2)
            return result.stdout.strip()
        except:
            return ""

    def update_stats(self):
        with self.lock:
            # 1. PID Check
            self.pid = self.run_adb(f"pidof {self.package}")
            if not self.pid:
                self.cpu = 0.0
                self.net_usage = "OFFLINE"
                self.status_code = "RECOVERY"
                return

            # 2. CPU Check (via top - mais rápido)
            top_out = self.run_adb(f"top -n 1 -p {self.pid} | grep {self.pid}")
            if top_out:
                try:
                    parts = top_out.split()
                    for p in parts:
                        if "%" in p: 
                            self.cpu = float(p.replace("%", "").replace(",", "."))
                            break
                except: pass

            # 3. Network Check (UID)
            uid_out = self.run_adb(f"dumpsys package {self.package} | grep userId=")
            if uid_out:
                try:
                    uid = uid_out.split('=')[1].split()[0]
                    net_out = self.run_adb(f"cat /proc/net/xt_qtaguid/stats | grep {uid}")
                    if net_out:
                        current_bytes = sum(int(line.split()[5]) for line in net_out.splitlines())
                        if self.last_bytes > 0:
                            diff = (current_bytes - self.last_bytes) / 1024 / CHECK_INTERVAL
                            self.net_usage = f"{diff:.1f} KB/s"
                        self.last_bytes = current_bytes
                except: pass

            # 4. Status Logic
            if time.time() < self.cooldown_until:
                self.status_code = "SYNC"
            elif self.cpu > 10.0:
                self.status_code = "ACTIVE"
                self.error_count = 0
            else:
                self.status_code = "IDLE"

    def monitor_logic(self):
        while self.is_running:
            if not self.manager.global_running: break
            
            self.update_stats()
            
            # Ação Real se não estiver em cooldown
            if time.time() > self.cooldown_until:
                if not self.pid:
                    self.reboot("Signal Lost")
                elif self.cpu < 5.0: # Se a CPU estiver morta
                    self.error_count += 1
                    if self.error_count >= 15: # ~45 segundos de inatividade real
                        self.reboot("Data Timeout")
                else:
                    self.error_count = 0
                    # Verificação de UI apenas se necessário (mais lenta)
                    if self.error_count % 5 == 0:
                        ui = self.run_adb("uiautomator dump /sdcard/view.xml > /dev/null 2>&1 && cat /sdcard/view.xml").lower()
                        if any(x in ui for x in ["disconnected", "desconectado", "reconnect"]):
                            self.reboot("Link Break")
            
            time.sleep(CHECK_INTERVAL)

    def reboot(self, reason):
        self.manager.add_log(f"⚡ [RE_PHONE] {self.package} -> {reason}", "red")
        self.manager.send_webhook(f"📡 **RE_PHONE**: `{self.package}` -> `{reason}`")
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
        # Busca pacotes de forma limpa
        output = subprocess.run("adb shell pm list packages roblox", shell=True, capture_output=True, text=True).stdout
        packages = [line.replace("package:", "").strip() for line in output.splitlines() if "roblox" in line]
        
        if not packages:
            rprint("[red]❌ Nenhum pacote Roblox encontrado via ADB![/red]")
            time.sleep(2)
            return

        for pkg in packages:
            if pkg not in self.instances:
                inst = InstanceMonitor(pkg, self)
                self.instances[pkg] = inst
                t = threading.Thread(target=inst.monitor_logic, daemon=True)
                t.start()
        
        # HUD com atualização forçada e tratamento de erro
        with Live(self.make_hud(), refresh_per_second=4, screen=True) as live:
            try:
                while self.global_running:
                    live.update(self.make_hud())
                    time.sleep(0.2)
            except KeyboardInterrupt:
                self.global_running = False

    def make_hud(self):
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body", size=12),
            Layout(name="footer", size=10)
        )
        layout["header"].update(Panel(Align.center("[bold cyan]RE_PHONE HUD v5.1 TURBO[/bold cyan] [white]by MSA[/white]"), border_style="cyan"))
        
        table = Table(expand=True, border_style="magenta", header_style="bold white")
        table.add_column("INSTANCE", style="green")
        table.add_column("CPU", justify="center")
        table.add_column("NETWORK", justify="center")
        table.add_column("STATUS", justify="center")
        
        for pkg, inst in self.instances.items():
            name = pkg.split('.')[-1].upper()
            with inst.lock:
                cpu_val = inst.cpu
                net_val = inst.net_usage
                status_val = inst.status_code
            
            cpu_color = "green" if cpu_val > 50 else "yellow" if cpu_val > 5 else "red"
            net_color = "cyan" if "KB/s" in net_val and float(net_val.split()[0]) > 0 else "red"
            status_style = "bold green" if status_val == "ACTIVE" else "bold blue"
            if status_val == "RECOVERY": status_style = "bold red"
            
            table.add_row(
                f"[bold]{name}[/bold]", 
                f"[{cpu_color}]{cpu_val}%[/{cpu_color}]", 
                f"[{net_color}]{net_val}[/{net_color}]", 
                f"[{status_style}]{status_val}[/{status_style}]"
            )
            
        layout["body"].update(Panel(table, title="[bold yellow]REAL-TIME DATA[/bold yellow]", border_style="magenta"))
        layout["footer"].update(Panel(Text("\n".join(self.logs)), title="[bold cyan]HEARTBEAT LOGS[/bold cyan]", border_style="cyan"))
        return layout

manager = RE_PHONE_Manager()

def main_menu():
    global VIP_LINK, WEBHOOK_URL
    while True:
        console.clear()
        banner = """[bold cyan]
    ██████╗ ███████╗      ██████╗ ██╗  ██╗ ██████╗ ███╗   ██╗███████╗
    ██╔══██╗██╔════╝      ██╔══██╗██║  ██║██╔═══██╗████╗  ██║██╔════╝
    ██████╔╝█████╗  █████╗██████╔╝███████║██║   ██║██╔██╗ ██║█████╗  
    ██╔══██╗██╔══╝  ╚════╝██╔═══╝ ██╔══██║██║   ██║██║╚██╗██║██╔══╝  
    ██║  ██║███████╗      ██║     ██║  ██║╚██████╔╝██║ ╚████║███████╗
    ╚═╝  ╚═╝╚══════╝      ╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝[/bold cyan]
    [white]                      by MSA | v5.1 Turbo[/white]"""
        rprint(Align.center(banner))
        status = f"🔗 VIP: {'[green]OK[/green]' if VIP_LINK else '[red]NO[/red]'} | ⚓ WEBHOOK: {'[green]OK[/green]' if WEBHOOK_URL else '[red]NO[/red]'}"
        rprint(Panel(Align.center(status), border_style="white"))
        
        grid = Table.grid(expand=True, padding=1)
        grid.add_column(ratio=1); grid.add_column(ratio=1)
        grid.add_row(Panel("[bold green][1] 🚀 LAUNCH TURBO HUD[/bold green]", border_style="green"), Panel("[bold magenta][2] ⚙️ SETTINGS[/bold magenta]", border_style="magenta"))
        grid.add_row(Panel("[bold blue][3] 🛠️ TOOLS[/bold blue]", border_style="blue"), Panel("[bold red][0] ❌ EXIT[/bold red]", border_style="red"))
        rprint(grid)
        
        choice = Prompt.ask("\n[bold white]Action[/bold white]", choices=["1", "2", "3", "0"])
        if choice == "1": manager.start_monitoring()
        elif choice == "2":
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
