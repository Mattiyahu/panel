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
from rich.live import Live
from rich.text import Text
from rich.align import Align
from rich import print as rprint

# Configurações Globais
console = Console()
CONFIG_FILE = "config.json"
CHECK_INTERVAL = 2  # Monitoramento ultra-rápido
COOLDOWN_TIME = 120 # Tempo de estabilização

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
    """Representa uma instância isolada do Roblox"""
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
            # Execução direta e rápida
            return subprocess.check_output(f"adb shell {cmd}", shell=True, stderr=subprocess.STDOUT, timeout=3).decode().strip()
        except: return ""

    def update(self):
        # 1. Verifica se o processo existe
        self.pid = self.adb(f"pidof {self.package}")
        
        if not self.pid:
            self.cpu = 0.0
            self.status = "STOPPED"
            return

        # 2. Pega CPU de forma instantânea
        try:
            top = self.adb(f"top -n 1 -p {self.pid} | grep {self.pid}")
            if top:
                parts = top.split()
                for p in parts:
                    if "%" in p:
                        self.cpu = float(p.replace("%", "").replace(",", "."))
                        break
        except: self.cpu = 0.0

        # 3. Define Status
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
            
            # Ações sem delay se não estiver em cooldown
            if time.time() > self.cooldown_until:
                if not self.pid:
                    self.relaunch("Process Missing")
                elif self.cpu < 5.0:
                    self.error_streak += 1
                    if self.error_streak >= 10: # ~20 segundos de inatividade real
                        self.relaunch("Low Activity")
                else:
                    # Checagem de UI rápida para desconexão
                    if self.error_streak % 5 == 0:
                        ui = self.adb("uiautomator dump /sdcard/view.xml > /dev/null 2>&1 && cat /sdcard/view.xml").lower()
                        if any(x in ui for x in ["disconnected", "desconectado", "reconnect"]):
                            self.relaunch("Connection Lost")
            
            time.sleep(CHECK_INTERVAL)

    def relaunch(self, reason):
        self.last_action = reason
        self.manager.add_log(f"[{self.package}] Relaunching: {reason}")
        self.manager.send_webhook(f"🔄 **RE_PHONE**: `{self.package}` -> `{reason}`")
        
        # ISOLAMENTO: Só mata e abre este pacote específico
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
        if len(self.logs) > 10: self.logs.pop(0)

    def send_webhook(self, msg):
        if WEBHOOK_URL:
            try: requests.post(WEBHOOK_URL, json={"content": msg}, timeout=3)
            except: pass

    def start(self):
        if not VIP_LINK:
            rprint("[red]Error: VIP Link not set![/red]"); time.sleep(2); return
        
        self.global_running = True
        # Detecta pacotes
        try:
            out = subprocess.check_output("adb shell pm list packages roblox", shell=True).decode()
            pkgs = [l.replace("package:", "").strip() for l in out.splitlines() if "roblox" in l]
        except: pkgs = []

        if not pkgs:
            rprint("[red]Error: No Roblox packages found![/red]"); time.sleep(2); return

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
        table = Table(title="RE_PHONE v7.0 - Monitoramento em Tempo Real", expand=True, border_style="white")
        table.add_column("Pacote", style="cyan")
        table.add_column("CPU", justify="center")
        table.add_column("Status", justify="center")
        table.add_column("Última Ação", justify="center")

        for p, inst in self.instances.items():
            status_color = "green" if inst.status == "RUNNING" else "yellow" if inst.status == "STABILIZING" else "red"
            table.add_row(
                p.split('.')[-1],
                f"{inst.cpu}%",
                f"[{status_color}]{inst.status}[/{status_color}]",
                inst.last_action
            )

        log_panel = Panel("\n".join(self.logs), title="Logs do Sistema", border_style="white")
        
        layout = Layout()
        layout.split_column(
            Layout(table, size=12),
            Layout(log_panel, size=12)
        )
        return layout

manager = RE_PHONE_v7()

def main():
    global VIP_LINK, WEBHOOK_URL
    while True:
        console.clear()
        rprint(Panel(Align.center("[bold]RE_PHONE v7.0 by MSA[/bold]\n[dim]Sistema de Monitoramento Isolado[/dim]"), border_style="white"))
        
        rprint(f"VIP Link: [green]{VIP_LINK[:30]}...[/green]" if VIP_LINK else "VIP Link: [red]Não configurado[/red]")
        rprint(f"Webhook: [green]Configurado[/green]" if WEBHOOK_URL else "Webhook: [red]Não configurado[/red]")
        rprint("-" * 40)
        
        rprint("[1] Iniciar Monitoramento")
        rprint("[2] Configurações")
        rprint("[3] Ferramentas ADB")
        rprint("[0] Sair")
        
        choice = Prompt.ask("\nOpção", choices=["1", "2", "3", "0"])
        
        if choice == "1":
            manager.start()
        elif choice == "2":
            VIP_LINK = Prompt.ask("Cole o Link VIP", default=VIP_LINK)
            WEBHOOK_URL = Prompt.ask("Cole o Webhook Discord", default=WEBHOOK_URL)
            save_config({"vip_link": VIP_LINK, "webhook_url": WEBHOOK_URL})
        elif choice == "3":
            console.clear()
            rprint("[1] Forçar Parada de Todos\n[2] Testar Conexão ADB\n[0] Voltar")
            sub = Prompt.ask("Opção", choices=["1", "2", "0"])
            if sub == "1":
                subprocess.run("adb shell am force-stop com.roblox.client", shell=True) # Exemplo
                rprint("[green]Comando enviado.[/green]"); time.sleep(1)
            elif sub == "2":
                out = subprocess.run("adb devices", shell=True, capture_output=True, text=True).stdout
                rprint(f"Dispositivos:\n{out}"); Prompt.ask("Pressione Enter")
        elif choice == "0":
            break

if __name__ == "__main__":
    main()
