#!/usr/bin/env python3
import os
import subprocess
import time
import requests
import json
import threading
import re
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.align import Align
from rich import print as rprint

# --- CONFIGURAÇÕES DO SUNA ---
VERSION = "1.0.3 Stable"
CONFIG_FILE = "suna_config.json"
CHECK_INTERVAL = 3
COOLDOWN_TIME = 60 

console = Console()

SUNA_ART = """
[bold yellow]
      \\   |   /
    .--.     .--.   [bold white]SUNA HUB[/bold white]
  - (          ) -  [bold white]MANAGER[/bold white]
    '--'     '--'
      /   |   \\     [dim]v{}[/dim]
[/bold yellow]""".format(VERSION)

# --- SISTEMA DE CONFIGURAÇÃO BLINDADO ---
def load_config():
    default = {"vip_link": "", "webhook_url": ""}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return {**default, **json.load(f)}
        except: pass
    return default

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Carrega configuração em um dicionário acessível globalmente
CONF = load_config()

# --- FUNÇÕES ADB ---
class ADB:
    @staticmethod
    def run(cmd):
        try:
            return subprocess.check_output(f"adb shell {cmd}", shell=True, stderr=subprocess.STDOUT, timeout=5).decode().strip()
        except: return ""

    @staticmethod
    def get_device_info():
        try:
            mem_info = ADB.run("cat /proc/meminfo")
            total_mem = int(re.search(r"MemTotal:\s+(\d+)", mem_info).group(1)) / 1024
            return total_mem
        except:
            return 2048.0

# --- CLASSE DE INSTÂNCIA (MODO PASSIVO) ---
class Instance:
    def __init__(self, package, manager):
        self.package = package
        self.manager = manager
        self.pid = None
        # Valores iniciais "falsos" para evitar fechamento prematuro
        self.cpu = 5.0 
        self.ram = 200.0
        self.status = "STARTING"
        self.last_action = "Init"
        self.cooldown_until = time.time() + 20 # 20s de carência inicial
        self.error_streak = 0
        self.is_running = True

    def get_stats(self):
        # 1. Verifica se o PID existe (Se não existir, o jogo fechou mesmo)
        self.pid = ADB.run(f"pidof {self.package}")
        
        if not self.pid:
            self.cpu = 0.0
            self.ram = 0.0
            self.status = "DEAD"
            return

        try:
            # Tenta ler estatísticas. Se falhar, mantém os valores anteriores
            top_data = ADB.run(f"top -n 1 -b -p {self.pid}")
            
            found_stats = False
            lines = top_data.splitlines()
            for line in lines:
                if str(self.pid) in line:
                    parts = line.split()
                    for p in parts:
                        # Tenta pegar CPU
                        if "%" in p: 
                            try: self.cpu = float(p.replace("%", ""))
                            except: pass
                        # Tenta pegar RAM (Suporte a M e K)
                        if "M" in p and not "%" in p:
                            try: self.ram = float(p.replace("M", ""))
                            except: pass
                        elif "K" in p:
                             try: self.ram = float(p.replace("K", "")) / 1024
                             except: pass
                    found_stats = True
                    break
            
            # Se o top falhou em ler (comum em alguns Androids), reseta para valores seguros
            if not found_stats:
                self.cpu = 5.0 
                self.ram = 250.0
                
        except: 
            pass

    def check_health(self):
        # Se estiver no tempo de espera inicial, ignora
        if time.time() < self.cooldown_until:
            self.status = "COOLDOWN"
            return

        # CRITÉRIO 1: O processo sumiu do Android?
        if not self.pid:
            self.relaunch("Processo morreu (Crash)")
            return

        # CRITÉRIO 2: RAM extremamente baixa (Tela preta ou crash silencioso)
        # Limite de 50MB é muito seguro. Nenhum jogo roda com menos que isso.
        if self.ram < 50.0: 
            self.error_streak += 1
            self.status = "LOW MEM"
        
        # CRITÉRIO 3: CPU Zero Absoluto
        elif self.cpu <= 0.0:
            self.error_streak += 1
            self.status = "FROZEN (0% CPU)"
        
        else:
            # Se tem qualquer sinal de vida, zera os erros
            self.error_streak = 0
            self.status = "RUNNING"

        # IMPORTANTE: Removida a verificação de "Background/Focus".
        # Isso permite que clones rodem em segundo plano sem serem fechados.
        
        # Precisa dar erro 20 vezes seguidas (~60 segundos) pra reiniciar
        if self.error_streak >= 20: 
            self.relaunch("Sem resposta por 60s")

    def relaunch(self, reason):
        self.last_action = reason
        self.manager.log(f"[{self.package}] {reason}")
        self.manager.webhook(f"☀️ **SUNA**: `{self.package}` reiniciado. Motivo: {reason}")
        
        ADB.run(f"am force-stop {self.package}")
        time.sleep(2)
        
        link = CONF.get("vip_link", "")
        if link:
            ADB.run(f"am start -a android.intent.action.VIEW -d '{link}' {self.package}")
        else:
            ADB.run(f"monkey -p {self.package} -c android.intent.category.LAUNCHER 1")
        
        self.cooldown_until = time.time() + COOLDOWN_TIME
        self.error_streak = 0
        self.status = "RESTARTING"
        self.cpu = 5.0
        self.ram = 200.0

    def loop(self):
        while self.is_running and self.manager.running:
            self.get_stats()
            self.check_health()
            time.sleep(CHECK_INTERVAL)

# --- GERENCIADOR ---
class SunaManager:
    def __init__(self):
        self.instances = {}
        self.running = False
        self.logs = []
        self.device_ram = 0

    def log(self, msg):
        t = datetime.datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{t}] {msg}")
        if len(self.logs) > 6: self.logs.pop(0)

    def webhook(self, content):
        url = CONF.get("webhook_url", "")
        if not url: return
        try: requests.post(url, json={"content": content}, timeout=2)
        except: pass

    def auto_setup(self):
        rprint("[bold yellow]☀️ Conectando ao dispositivo...[/bold yellow]")
        self.device_ram = ADB.get_device_info()
        rprint(f"[cyan]ℹ️ RAM Total Detectada: {self.device_ram:.0f} MB[/cyan]")
        time.sleep(1)

        raw = ADB.run("pm list packages roblox")
        pkgs = [l.replace("package:", "").strip() for l in raw.splitlines() if "roblox" in l]
        
        if not pkgs:
            rprint("[bold red]❌ Nenhum Roblox encontrado![/bold red]")
            return False
            
        self.instances = {p: Instance(p, self) for p in pkgs}
        return True

    def start(self):
        if not self.auto_setup(): return
        self.running = True

        for inst in self.instances.values():
            threading.Thread(target=inst.loop, daemon=True).start()

        self.ui_loop()

    def ui_loop(self):
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=6),
            Layout(name="body"),
            Layout(name="footer", size=8)
        )

        layout["header"].update(Panel(Align.center(Text.from_markup(SUNA_ART)), border_style="yellow"))

        with Live(layout, refresh_per_second=2, screen=True) as live:
            try:
                while self.running:
                    table = Table(expand=True, border_style="yellow", header_style="bold yellow")
                    table.add_column("CLONE", style="bold white")
                    table.add_column("RAM", justify="right")
                    table.add_column("CPU", justify="right")
                    table.add_column("STATUS", justify="center")
                    table.add_column("AÇÃO")

                    for p, inst in self.instances.items():
                        if inst.status == "RUNNING": s_style = "bold green"
                        elif inst.status == "COOLDOWN": s_style = "blue"
                        elif "IDLE" in inst.status: s_style = "bold red"
                        elif "LOW" in inst.status: s_style = "red"
                        else: s_style = "yellow"

                        name = p.split('.')[-1].upper()
                        table.add_row(
                            name,
                            f"{inst.ram:.0f}MB",
                            f"{inst.cpu:.1f}%",
                            f"[{s_style}]{inst.status}[/{s_style}]",
                            inst.last_action
                        )

                    layout["body"].update(Panel(table, title=f"[bold yellow]MONITORAMENTO ({self.device_ram:.0f}MB Total)[/bold yellow]", border_style="yellow"))
                    
                    log_text = "\n".join(self.logs)
                    layout["footer"].update(Panel(log_text, title="LOGS", border_style="white"))
                    
                    time.sleep(0.5)
            except KeyboardInterrupt:
                self.running = False

# --- MENU ---
import datetime
def main():
    while True:
        console.clear()
        rprint(Align.center(SUNA_ART))
        
        v_link = CONF.get("vip_link", "")
        w_url = CONF.get("webhook_url", "")
        
        rprint(Panel(f"[yellow]VIP:[/yellow] {v_link[:30]}...\n[yellow]WEBHOOK:[/yellow] {'Ativo' if w_url else 'Off'}", border_style="yellow"))
        
        rprint("[1] ☀️ INICIAR SUNA HUB")
        rprint("[2] ⚙️ CONFIGURAR")
        rprint("[3] 🛠️ FERRAMENTAS EXTRAS")
        rprint("[0] ❌ SAIR")
        
        opt = Prompt.ask("\n[bold yellow]Escolha[/bold yellow]", choices=["1", "2", "3", "0"])
        
        if opt == "1":
            if not CONF.get("vip_link"):
                rprint("[red]Configure o Link VIP primeiro![/red]")
                time.sleep(2)
            else:
                mgr = SunaManager()
                mgr.start()
        
        elif opt == "2":
            new_vip = Prompt.ask("Link do Servidor VIP", default=CONF.get("vip_link", ""))
            new_web = Prompt.ask("Webhook Discord (Opcional)", default=CONF.get("webhook_url", ""))
            
            CONF["vip_link"] = new_vip
            CONF["webhook_url"] = new_web
            save_config(CONF)
            
        elif opt == "3":
             rprint("\n[bold yellow]-- FERRAMENTAS --[/bold yellow]")
             rprint("[1] Forçar Modo Retrato (Arruma tela esticada)")
             rprint("[2] Matar todos os Roblox")
             x = Prompt.ask("Opção", choices=["1", "2"])
             if x == "1":
                 ADB.run("settings put system accelerometer_rotation 0")
                 ADB.run("settings put system user_rotation 0")
                 rprint("[green]Tela travada em pé![/green]")
                 time.sleep(1)
             if x == "2":
                 ADB.run("am kill-all")
                 rprint("[red]Comando enviado.[/red]")
                 time.sleep(1)

        elif opt == "0":
            break

if __name__ == "__main__":
    main()
