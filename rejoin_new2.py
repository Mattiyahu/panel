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
CHECK_INTERVAL = 10
COOLDOWN_TIME = 180

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
    """Classe para gerenciar uma única instância de forma isolada."""
    def __init__(self, package, manager):
        self.package = package
        self.manager = manager
        self.pid = None
        self.uid = None
        self.cpu = 0.0
        self.net_heartbeat = "OFFLINE"
        self.status_code = "IDLE" # Termos codificados: IDLE, SYNC, ACTIVE, RECOVERY
        self.last_net_bytes = 0
        self.low_activity_count = 0
        self.cooldown_until = 0
        self.is_running = True

    def run_adb(self, command):
        try:
            result = subprocess.run(f"adb shell {command}", shell=True, capture_output=True, text=True)
            return result.stdout.strip()
        except:
            return ""

    def get_uid(self):
        if not self.uid:
            out = self.run_adb(f"dumpsys package {self.package} | grep userId=")
            if out:
                try: self.uid = out.split('=')[1].split()[0]
                except: pass
        return self.uid

    def update_stats(self):
        self.pid = self.run_adb(f"pidof {self.package}")
        if not self.pid:
            self.cpu = 0.0
            self.net_heartbeat = "LOST"
            self.status_code = "RECOVERY"
            return

        # CPU Stats
        top_out = self.run_adb(f"top -n 1 -p {self.pid} | grep {self.pid}")
        if top_out:
            try:
                parts = top_out.split()
                for p in parts:
                    if "%" in p: self.cpu = float(p.replace("%", "").replace(",", "."))
            except: pass

        # Network Heartbeat (via UID traffic stats)
        uid = self.get_uid()
        if uid:
            net_out = self.run_adb(f"cat /proc/net/xt_qtaguid/stats | grep {uid}")
            if net_out:
                try:
                    current_bytes = sum(int(line.split()[5]) for line in net_out.splitlines())
                    if current_bytes > self.last_net_bytes:
                        self.net_heartbeat = "STABLE"
                        self.last_net_bytes = current_bytes
                    else:
                        self.net_heartbeat = "STAGNANT"
                except: pass
        
        # Codificação de Status
        if time.time() < self.cooldown_until:
            self.status_code = "SYNC"
        elif self.cpu > 80:
            self.status_code = "ACTIVE"
        else:
            self.status_code = "IDLE"

    def monitor_logic(self):
        while self.is_running:
            if not self.manager.global_running: break
            
            self.update_stats()
            
            if time.time() > self.cooldown_until:
                # Lógica de Reinicialização Isolada
                should_reboot = False
                reason = ""

                if not self.pid:
                    should_reboot = True
                    reason = "Signal Lost"
                elif self.cpu < 20.0 and self.net_heartbeat == "STAGNANT":
                    self.low_activity_count += 1
                    if self.low_activity_count >= 10:
                        should_reboot = True
                        reason = "Data Timeout"
                else:
                    self.low_activity_count = 0
                    # Verificação de UI (apenas se necessário)
                    ui = self.run_adb("uiautomator dump /sdcard/view.xml > /dev/null 2>&1 && cat /sdcard/view.xml").lower()
                    if "disconnected" in ui or "desconectado" in ui:
                        should_reboot = True
                        reason = "Link Break"

                if should_reboot:
                    self.reboot_instance(reason)

            time.sleep(CHECK_INTERVAL)

    def reboot_instance(self, reason):
        self.manager.add_log(f"⚡ [RE_PHONE] {self.package} -> {reason}", "red")
        self.manager.send_webhook(f"📡 **RE_PHONE Heartbeat**: `{self.package}` -> `{reason}`")
        self.run_adb(f"am force-stop {self.package}")
        time.sleep(2)
        self.run_adb(f"am start -a android.intent.action.VIEW -d '{VIP_LINK}' {self.package}")
        self.cooldown_until = time.time() + COOLDOWN_TIME
        self.low_activity_count = 0

class RE_PHONE_Manager:
    def __init__(self):
        self.instances = {}
        self.global_running = False
        self.logs = []
        self.webhook_url = WEBHOOK_URL

    def add_log(self, msg, style="white"):
        t = datetime.datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{t}] {msg}")
        if len(self.logs) > 10: self.logs.pop(0)

    def send_webhook(self, msg):
        if self.webhook_url:
            try: requests.post(self.webhook_url, json={"content": msg}, timeout=5)
            except: pass

    def start_monitoring(self):
        self.global_running = True
        output = subprocess.run("adb shell pm list packages roblox", shell=True, capture_output=True, text=True).stdout
        packages = [line.replace("package:", "").strip() for line in output.splitlines() if "roblox" in line]
        
        for pkg in packages:
            if pkg not in self.instances:
                inst = InstanceMonitor(pkg, self)
                self.instances[pkg] = inst
                threading.Thread(target=inst.monitor_logic, daemon=True).start()
        
        with Live(self.make_hud(), refresh_per_second=2) as live:
            while self.global_running:
                live.update(self.make_hud())
                time.sleep(1)

    def make_hud(self):
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body", size=15),
            Layout(name="footer", size=12)
        )
        
        layout["header"].update(Panel(Align.center("[bold cyan]RE_PHONE[/bold cyan] [white]by MSA[/white]"), border_style="cyan"))
        
        table = Table(expand=True, border_style="bright_black", header_style="bold cyan")
        table.add_column("INSTANCE", style="green")
        table.add_column("CPU", justify="center")
        table.add_column("NETWORK", justify="center")
        table.add_column("STATUS", justify="center")
        
        for pkg, inst in self.instances.items():
            net_style = "green" if inst.net_heartbeat == "STABLE" else "yellow"
            status_style = "bold green" if inst.status_code == "ACTIVE" else "bold blue"
            if inst.status_code == "RECOVERY": status_style = "bold red"
            
            table.add_row(
                pkg.split('.')[-1], 
                f"{inst.cpu}%", 
                f"[{net_style}]{inst.net_heartbeat}[/{net_style}]", 
                f"[{status_style}]{inst.status_code}[/{status_style}]"
            )
            
        layout["body"].update(Panel(table, title="[bold white]REAL-TIME HUD[/bold white]", border_style="bright_black"))
        layout["footer"].update(Panel(Text("\n".join(self.logs)), title="[bold yellow]HEARTBEAT LOGS[/bold yellow]", border_style="yellow"))
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
    ╚═╝  ╚═╝╚══════╝      ╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝[/bold cyan]"""
        rprint(Align.center(banner))
        rprint(Align.center("[white]RE_PHONE by MSA | Next-Gen Monitoring[/white]\n"))
        
        grid = Table.grid(expand=True, padding=1)
        grid.add_column(ratio=1); grid.add_column(ratio=1)
        grid.add_row(
            Panel("[bold green][1] 🚀 LAUNCH HUD[/bold green]", border_style="green"),
            Panel("[bold magenta][2] ⚙️ SETTINGS[/bold magenta]", border_style="magenta")
        )
        grid.add_row(
            Panel("[bold blue][3] 🛠️ TOOLS[/bold blue]", border_style="blue"),
            Panel("[bold red][0] ❌ EXIT[/bold red]", border_style="red")
        )
        rprint(grid)
        
        choice = Prompt.ask("\n[bold white]Select[/bold white]", choices=["1", "2", "3", "0"])
        if choice == "1": manager.start_monitoring()
        elif choice == "2":
            global VIP_LINK, WEBHOOK_URL
            VIP_LINK = Prompt.ask("VIP Link", default=VIP_LINK)
            WEBHOOK_URL = Prompt.ask("Webhook URL", default=WEBHOOK_URL)
            save_config({"vip_link": VIP_LINK, "webhook_url": WEBHOOK_URL})
        elif choice == "3":
            rprint("[yellow]Running Setup...[/yellow]")
            subprocess.run("bash setup.sh", shell=True)
            Prompt.ask("Done. Enter to return")
        elif choice == "0": break

if __name__ == "__main__":
    main_menu()
