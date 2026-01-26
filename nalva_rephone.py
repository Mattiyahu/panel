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
from rich.progress import BarColumn, Progress, TextColumn
from rich import print as rprint

# Configurações Globais
console = Console()
CONFIG_FILE = "config.json"
CHECK_INTERVAL = 4
COOLDOWN_TIME = 150

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except: pass
    return {"vip_link": "", "webhook_url": ""}

def save_config(config_data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f, indent=4)

_config = load_config()
VIP_LINK = _config.get("vip_link", "")
WEBHOOK_URL = _config.get("webhook_url", "")

class InstanceVigilante:
    """Vigilante individual para cada instância - Isolamento Total"""
    def __init__(self, package, manager):
        self.package = package
        self.manager = manager
        self.pid = None
        self.cpu = 0.0
        self.net_kb = 0.0
        self.last_bytes = 0
        self.status = "INITIALIZING"
        self.color = "cyan"
        self.error_count = 0
        self.cooldown_until = time.time() + 10
        self.is_running = True
        self.lock = threading.Lock()

    def run_adb(self, command):
        try:
            result = subprocess.run(f"adb shell {command}", shell=True, capture_output=True, text=True, timeout=3)
            return result.stdout.strip()
        except: return ""

    def update(self):
        # 1. PID Check
        new_pid = self.run_adb(f"pidof {self.package}")
        
        with self.lock:
            self.pid = new_pid
            if not self.pid:
                self.cpu = 0.0
                self.net_kb = 0.0
                self.status = "OFFLINE"
                self.color = "red"
                return

            # 2. CPU Check
            top = self.run_adb(f"top -n 1 -p {self.pid} | grep {self.pid}")
            if top:
                try:
                    parts = top.split()
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
                    net = self.run_adb(f"cat /proc/net/xt_qtaguid/stats | grep {uid}")
                    if net:
                        curr = sum(int(l.split()[5]) for l in net.splitlines())
                        if self.last_bytes > 0:
                            self.net_kb = (curr - self.last_bytes) / 1024 / CHECK_INTERVAL
                        self.last_bytes = curr
                except: pass

            # 4. Status Logic
            if time.time() < self.cooldown_until:
                self.status = "STABILIZING"
                self.color = "blue"
            elif self.cpu > 15.0:
                self.status = "ACTIVE"
                self.color = "green"
                self.error_count = 0
            else:
                self.status = "IDLE/STUCK"
                self.color = "yellow"

    def monitor(self):
        while self.is_running and self.manager.global_running:
            self.update()
            
            if time.time() > self.cooldown_until:
                # Ação isolada - Só mexe neste pacote
                if not self.pid:
                    self.reboot("Process Lost")
                elif self.cpu < 5.0 and self.net_kb < 0.5:
                    self.error_count += 1
                    if self.error_count >= 12: # ~1 minuto de inatividade real
                        self.reboot("System Freeze")
                else:
                    # Verificação de UI (Link Break)
                    if self.error_count % 4 == 0:
                        ui = self.run_adb("uiautomator dump /sdcard/view.xml > /dev/null 2>&1 && cat /sdcard/view.xml").lower()
                        if any(x in ui for x in ["disconnected", "desconectado", "reconnect"]):
                            self.reboot("Connection Lost")
            
            time.sleep(CHECK_INTERVAL)

    def reboot(self, reason):
        self.manager.add_log(f"REBOOT: {self.package} | {reason}", "bold red")
        self.manager.send_webhook(f"🚨 **RE_PHONE v6**: `{self.package}` -> `{reason}`")
        self.run_adb(f"am force-stop {self.package}")
        time.sleep(2)
        self.run_adb(f"am start -a android.intent.action.VIEW -d '{VIP_LINK}' {self.package}")
        self.cooldown_until = time.time() + COOLDOWN_TIME
        self.error_count = 0

class CyberManager:
    def __init__(self):
        self.vigilantes = {}
        self.global_running = False
        self.logs = []

    def add_log(self, msg, style="white"):
        t = datetime.datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{t}] {msg}")
        if len(self.logs) > 10: self.logs.pop(0)

    def send_webhook(self, msg):
        if WEBHOOK_URL:
            try: requests.post(WEBHOOK_URL, json={"content": msg}, timeout=5)
            except: pass

    def start(self):
        if not VIP_LINK:
            rprint("[red]❌ VIP LINK REQUIRED[/red]"); time.sleep(2); return
        
        self.global_running = True
        out = subprocess.run("adb shell pm list packages roblox", shell=True, capture_output=True, text=True).stdout
        pkgs = [l.replace("package:", "").strip() for l in out.splitlines() if "roblox" in l]
        
        for p in pkgs:
            v = InstanceVigilante(p, self)
            self.vigilantes[p] = v
            threading.Thread(target=v.monitor, daemon=True).start()
        
        with Live(self.make_layout(), refresh_per_second=4, screen=True) as live:
            try:
                while self.global_running:
                    live.update(self.make_layout())
                    time.sleep(0.25)
            except KeyboardInterrupt:
                self.global_running = False

    def make_layout(self):
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=4),
            Layout(name="main", size=14),
            Layout(name="footer", size=10)
        )
        
        # Header Cyber
        header_text = Text.assemble(
            (" RE_PHONE ", "bold black on cyan"),
            (" v6.0 CYBER EDITION ", "bold cyan on black"),
            (" by MSA ", "italic white")
        )
        layout["header"].update(Panel(Align.center(header_text), border_style="cyan", subtitle="[dim]Multi-Instance Isolation System[/dim]"))
        
        # Main Table
        table = Table(expand=True, border_style="bright_black", show_edge=False)
        table.add_column("INSTANCE", style="bold white", width=20)
        table.add_column("CPU USAGE", justify="center")
        table.add_column("NET TRAFFIC", justify="center")
        table.add_column("STATUS", justify="center")
        
        for p, v in self.vigilantes.items():
            name = p.split('.')[-1].upper()
            with v.lock:
                cpu, net, status, color = v.cpu, v.net_kb, v.status, v.color
            
            # Progress bar para CPU
            cpu_bar = Progress(BarColumn(bar_width=10, complete_style=color), TextColumn(f"[bold {color}]{cpu}%[/]"))
            cpu_bar.add_task("", total=100, completed=cpu)
            
            table.add_row(
                f"ID: {name}",
                cpu_bar,
                f"[bold cyan]{net:.1f} KB/s[/]",
                f"[bold {color}]{status}[/]"
            )
            
        layout["main"].update(Panel(table, title="[bold cyan]SYSTEM CORE[/bold cyan]", border_style="cyan"))
        
        # Footer Logs
        log_text = Text("\n".join(self.logs), style="dim")
        layout["footer"].update(Panel(log_text, title="[bold yellow]NEURAL LOGS[/bold yellow]", border_style="yellow"))
        return layout

manager = CyberManager()

def main():
    global VIP_LINK, WEBHOOK_URL
    while True:
        console.clear()
        banner = """[bold cyan]
    ▄████████    ▄████████      ███      ▄█    █▄  ███▄▄▄▄      ▄████████ 
    ███    ███   ███    ███  ▀█████████▄ ███    ███ ███▀▀▀██▄   ███    ███ 
    ███    █▀    ███    █▀      ▀███▀▀██ ███    ███ ███   ███   ███    █▀  
   ▄███▄▄▄      ▄███▄▄▄          ███   ▀ ███    ███ ███   ███  ▄███▄▄▄     
  ▀▀███▀▀▀     ▀▀███▀▀▀          ███     ███    ███ ███   ███ ▀▀███▀▀▀     
    ███    █▄    ███    █▄       ███     ███    ███ ███   ███   ███    █▄  
    ███    ███   ███    ███      ███     ███    ███ ███   ███   ███    ███ 
    ██████████   ██████████     ▄████▀    ▀██████▀   ▀█   █▀    ██████████ [/bold cyan]
    [italic white]                      Next-Gen Isolation by MSA[/italic white]"""
        rprint(Align.center(banner))
        
        status = f"📡 VIP: {'[bold green]ONLINE[/bold green]' if VIP_LINK else '[bold red]OFFLINE[/bold red]'} | ⚓ WEBHOOK: {'[bold green]ACTIVE[/bold green]' if WEBHOOK_URL else '[bold red]INACTIVE[/bold red]'}"
        rprint(Panel(Align.center(status), border_style="bright_black"))
        
        menu = Table.grid(expand=True, padding=1)
        menu.add_column(ratio=1); menu.add_column(ratio=1)
        menu.add_row(
            Panel("[bold cyan][1] ⚡ INITIATE CYBER HUD[/bold cyan]", border_style="cyan"),
            Panel("[bold magenta][2] ⚙️ NEURAL SETTINGS[/bold magenta]", border_style="magenta")
        )
        menu.add_row(
            Panel("[bold blue][3] 🛠️ SYSTEM TOOLS[/bold blue]", border_style="blue"),
            Panel("[bold red][0] ❌ TERMINATE[/bold red]", border_style="red")
        )
        rprint(menu)
        
        choice = Prompt.ask("\n[bold white]Select Protocol[/bold white]", choices=["1", "2", "3", "0"])
        if choice == "1": manager.start()
        elif choice == "2":
            console.clear()
            rprint(Panel("[bold magenta]NEURAL SETTINGS[/bold magenta]", border_style="magenta"))
            VIP_LINK = Prompt.ask("VIP Link", default=VIP_LINK)
            WEBHOOK_URL = Prompt.ask("Webhook URL", default=WEBHOOK_URL)
            save_config({"vip_link": VIP_LINK, "webhook_url": WEBHOOK_URL})
        elif choice == "3":
            console.clear()
            rprint(Panel("[bold blue]SYSTEM TOOLS[/bold blue]", border_style="blue"))
            rprint("[1] Run Auto-Setup\n[2] Force Stop All\n[0] Back")
            sub = Prompt.ask("Select", choices=["1", "2", "0"])
            if sub == "1": subprocess.run("bash setup.sh", shell=True); Prompt.ask("Done. Enter")
            elif sub == "2": 
                for p in manager.vigilantes.keys(): subprocess.run(f"adb shell am force-stop {p}", shell=True)
                rprint("[red]All instances terminated.[/red]"); time.sleep(1)
        elif choice == "0": break

if __name__ == "__main__":
    main()
