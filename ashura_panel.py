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
CHECK_INTERVAL = 3
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

class RobloxInstance:
    def __init__(self, package, manager):
        self.package = package
        self.manager = manager
        self.pid = None
        self.cpu = 0.0
        self.status = "IDLE"
        self.last_action = "None"
        self.cooldown_until = 0
        self.error_streak = 0
        self.is_running = True

    def adb(self, cmd):
        try:
            return subprocess.check_output(f"adb shell {cmd}", shell=True, stderr=subprocess.STDOUT, timeout=3).decode().strip()
        except: return ""

    def update(self):
        self.pid = self.adb(f"pidof {self.package}")
        if not self.pid:
            self.cpu = 0.0
            self.status = "STOPPED"
            return

        try:
            top = self.adb(f"top -n 1 -p {self.pid} | grep {self.pid}")
            if top:
                parts = top.split()
                for p in parts:
                    if "%" in p:
                        self.cpu = float(p.replace("%", "").replace(",", "."))
                        break
        except: self.cpu = 0.0

        if time.time() < self.cooldown_until:
            self.status = "STABILIZING"
        elif self.cpu > 10.0:
            self.status = "RUNNING"
            self.error_streak = 0
        else:
            self.status = "STUCK/IDLE"

    def monitor_loop(self):
        while self.is_running and self.manager.global_running:
            self.update()
            if time.time() > self.cooldown_until:
                if not self.pid:
                    self.relaunch("Process Missing")
                elif self.cpu < 5.0:
                    self.error_streak += 1
                    if self.error_streak >= 12:
                        self.relaunch("Low Activity")
                else:
                    self.error_streak = 0
                    if self.error_streak % 5 == 0:
                        ui = self.adb("uiautomator dump /sdcard/view.xml > /dev/null 2>&1 && cat /sdcard/view.xml").lower()
                        if any(x in ui for x in ["disconnected", "desconectado", "reconnect"]):
                            self.relaunch("Connection Lost")
            time.sleep(CHECK_INTERVAL)

    def relaunch(self, reason):
        self.last_action = reason
        self.manager.add_log(f"[{self.package}] Relaunch: {reason}")
        self.manager.send_webhook(f"🔄 **RE_PHONE**: `{self.package}` -> `{reason}`")
        self.adb(f"am force-stop {self.package}")
        time.sleep(1)
        self.adb(f"am start -a android.intent.action.VIEW -d '{VIP_LINK}' {self.package}")
        self.cooldown_until = time.time() + COOLDOWN_TIME
        self.error_streak = 0

class RE_PHONE_v7:
    def __init__(self):
        self.instances = {}
        self.global_running = False
        self.logs = []

    def add_log(self, msg):
        t = datetime.datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{t}] {msg}")
        if len(self.logs) > 8: self.logs.pop(0)

    def send_webhook(self, msg):
        if WEBHOOK_URL:
            try: requests.post(WEBHOOK_URL, json={"content": msg}, timeout=3)
            except: pass

    def force_portrait(self):
        """Força a tela em modo retrato (em pé) e desativa rotação automática"""
        rprint("[bold red]Forçando modo Retrato...[/bold red]")
        subprocess.run("adb shell settings put system accelerometer_rotation 0", shell=True)
        subprocess.run("adb shell settings put system user_rotation 0", shell=True)

    def start(self):
        if not VIP_LINK:
            rprint("[bold red]Erro: VIP Link não configurado![/bold red]"); time.sleep(2); return
        
        self.force_portrait()
        self.global_running = True
        try:
            out = subprocess.check_output("adb shell pm list packages roblox", shell=True).decode()
            pkgs = [l.replace("package:", "").strip() for l in out.splitlines() if "roblox" in l]
        except: pkgs = []

        if not pkgs:
            rprint("[bold red]Erro: Nenhum pacote Roblox encontrado![/bold red]"); time.sleep(2); return

        for p in pkgs:
            inst = RobloxInstance(p, self)
            self.instances[p] = inst
            threading.Thread(target=inst.monitor_loop, daemon=True).start()

        with Live(self.render(), refresh_per_second=4, screen=True) as live:
            try:
                while self.global_running:
                    live.update(self.render())
                    time.sleep(0.25)
            except KeyboardInterrupt:
                self.global_running = False

    def render(self):
        # Correção do erro: Definindo o layout explicitamente
        main_layout = Layout()
        main_layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body", size=12),
            Layout(name="footer", size=10)
        )

        header_text = Text("RE_PHONE v7.1 RED EDITION", style="bold white")
        main_layout["header"].update(Panel(Align.center(header_text), border_style="red"))

        table = Table(expand=True, border_style="red", header_style="bold red")
        table.add_column("PACOTE", style="bold white")
        table.add_column("CPU", justify="center")
        table.add_column("STATUS", justify="center")
        table.add_column("AÇÃO", justify="center")

        for p, inst in self.instances.items():
            status_color = "bright_green" if inst.status == "RUNNING" else "yellow" if inst.status == "STABILIZING" else "red"
            table.add_row(
                p.split('.')[-1].upper(),
                f"{inst.cpu}%",
                f"[{status_color}]{inst.status}[/{status_color}]",
                inst.last_action
            )

        main_layout["body"].update(Panel(table, title="[bold red] MONITORAMENTO [/bold red]", border_style="red"))
        
        log_text = Text("\n".join(self.logs), style="white")
        main_layout["footer"].update(Panel(log_text, title="[bold red] LOGS [/bold red]", border_style="red"))
        
        return main_layout

manager = RE_PHONE_v7()

def main():
    global VIP_LINK, WEBHOOK_URL
    while True:
        console.clear()
        banner = """[bold red]
    ██████╗ ███████╗      ██████╗ ██╗  ██╗ ██████╗ ███╗   ██╗███████╗
    ██╔══██╗██╔════╝      ██╔══██╗██║  ██║██╔═══██╗████╗  ██║██╔════╝
    ██████╔╝█████╗  █████╗██████╔╝███████║██║   ██║██╔██╗ ██║█████╗  
    ██╔══██╗██╔══╝  ╚════╝██╔═══╝ ██╔══██║██║   ██║██║╚██╗██║██╔══╝  
    ██║  ██║███████╗      ██║     ██║  ██║╚██████╔╝██║ ╚████║███████╗
    ╚═╝  ╚═╝╚══════╝      ╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝[/bold red]
    [white]                      RED EDITION by MSA[/white]"""
        rprint(Align.center(banner))
        
        rprint(Panel(f"VIP: [red]{VIP_LINK[:40]}...[/red]\nWEBHOOK: [red]{'CONFIGURADO' if WEBHOOK_URL else 'PENDENTE'}[/red]", border_style="red"))
        
        grid = Table.grid(expand=True, padding=1)
        grid.add_column(ratio=1); grid.add_column(ratio=1)
        grid.add_row(
            Panel("[bold white][1] 🚀 INICIAR RED HUD[/bold white]", border_style="red"),
            Panel("[bold white][2] ⚙️ CONFIGURAÇÕES[/bold white]", border_style="red")
        )
        grid.add_row(
            Panel("[bold white][3] 🛠️ FERRAMENTAS[/bold white]", border_style="red"),
            Panel("[bold white][0] ❌ SAIR[/bold white]", border_style="red")
        )
        rprint(grid)
        
        choice = Prompt.ask("\n[bold red]Ação[/bold red]", choices=["1", "2", "3", "0"])
        
        if choice == "1":
            manager.start()
        elif choice == "2":
            VIP_LINK = Prompt.ask("Link VIP", default=VIP_LINK)
            WEBHOOK_URL = Prompt.ask("Webhook Discord", default=WEBHOOK_URL)
            save_config({"vip_link": VIP_LINK, "webhook_url": WEBHOOK_URL})
        elif choice == "3":
            console.clear()
            rprint(Panel("[bold red]FERRAMENTAS[/bold red]", border_style="red"))
            rprint("[1] Forçar Modo Retrato (Em pé)\n[2] Parar Todos Roblox\n[0] Voltar")
            sub = Prompt.ask("Opção", choices=["1", "2", "0"])
            if sub == "1": manager.force_portrait(); time.sleep(1)
            elif sub == "2":
                for p in manager.instances.keys(): subprocess.run(f"adb shell am force-stop {p}", shell=True)
                rprint("[red]Todos parados.[/red]"); time.sleep(1)
        elif choice == "0":
            break

if __name__ == "__main__":
    main()
