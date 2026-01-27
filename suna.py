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
VERSION = "1.0.1"
CONFIG_FILE = "suna_config.json"
CHECK_INTERVAL = 3
COOLDOWN_TIME = 60 # Tempo para estabilizar após abrir

# Limites dinâmicos (serão calibrados)
MIN_RAM_MB = 150.0  # Mínimo de RAM para considerar o jogo aberto
MIN_CPU_PERCENT = 2.0 # Mínimo de CPU para considerar ativo

console = Console()

# --- ARTE ASCII SUNA ---
SUNA_ART = """
[bold yellow]
      \\   |   /
    .--.     .--.   [bold white]SUNA HUB[/bold white]
  - (          ) -  [bold white]MANAGER[/bold white]
    '--'     '--'
      /   |   \\     [dim]v{}[/dim]
[/bold yellow]""".format(VERSION)

# --- GERENCIAMENTO DE CONFIGURAÇÃO ---
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

config = load_config()
VIP_LINK = config.get("vip_link", "")
WEBHOOK_URL = config.get("webhook_url", "")

# --- FUNÇÕES ADB OTIMIZADAS ---
class ADB:
    @staticmethod
    def run(cmd):
        try:
            return subprocess.check_output(f"adb shell {cmd}", shell=True, stderr=subprocess.STDOUT, timeout=5).decode().strip()
        except: return ""

    @staticmethod
    def get_device_info():
        """Calibra baseando no hardware do dispositivo"""
        try:
            mem_info = ADB.run("cat /proc/meminfo")
            total_mem = int(re.search(r"MemTotal:\s+(\d+)", mem_info).group(1)) / 1024 # MB
            
            # Ajuste de sensibilidade baseado na RAM total
            global MIN_RAM_MB
            if total_mem > 6000: # Celular 6GB+
                MIN_RAM_MB = 350.0
            elif total_mem > 3000: # Celular 3GB+
                MIN_RAM_MB = 250.0
            else:
                MIN_RAM_MB = 150.0
                
            return total_mem
        except:
            return 2048.0 # Fallback 2GB

    @staticmethod
    def get_focused_app():
        """Verifica qual app está na tela sem usar uiautomator (rápido)"""
        try:
            # Método compatível com Android 8-14
            dump = ADB.run("dumpsys window windows | grep -E 'mCurrentFocus|mFocusedApp'")
            return dump
        except: return ""

# --- CLASSE DE INSTÂNCIA ---
class Instance:
    def __init__(self, package, manager):
        self.package = package
        self.manager = manager
        self.pid = None
        self.cpu = 0.0
        self.ram = 0.0
        self.status = "STARTING"
        self.last_action = "Init"
        self.cooldown_until = time.time() + 10
        self.error_streak = 0
        self.is_running = True

    def get_stats(self):
        """Pega CPU e RAM usando top e processamento de texto"""
        self.pid = ADB.run(f"pidof {self.package}")
        
        if not self.pid:
            self.cpu = 0.0
            self.ram = 0.0
            self.status = "DEAD"
            return

        try:
            # Top otimizado: mostra threads, apenas do PID específico
            top_data = ADB.run(f"top -n 1 -b -p {self.pid}")
            
            # Regex para pegar CPU% e RAM (RES/RSS)
            lines = top_data.splitlines()
            for line in lines:
                if str(self.pid) in line:
                    parts = line.split()
                    for p in parts:
                        if "%" in p: 
                            self.cpu = float(p.replace("%", ""))
                        if "M" in p and not "%" in p:
                            self.ram = float(p.replace("M", ""))
                    
                    if self.ram == 0.0 and len(parts) > 5:
                        try:
                            # Tenta achar valores numéricos grandes que pareçam RAM (em K)
                            # Normalmente RSS é a coluna 5 ou 6
                            val = int(parts[-4].replace("K", "")) / 1024
                            self.ram = val
                        except: pass
                    break
        except: pass

    def check_health(self):
        if time.time() < self.cooldown_until:
            self.status = "COOLDOWN"
            return

        # 1. Checa se o processo morreu
        if not self.pid:
            self.relaunch("Processo morreu")
            return

        # 2. Checa se está travado (0 CPU) ou em tela branca (baixa RAM)
        if self.ram < MIN_RAM_MB:
            self.error_streak += 1
            self.status = "LOW MEM"
        elif self.cpu < MIN_CPU_PERCENT:
            self.error_streak += 1
            self.status = "IDLE/FROZEN"
        else:
            self.error_streak = 0
            self.status = "RUNNING"

        # 3. Checa se está em Background (Home)
        if self.error_streak > 2:
            focused = ADB.get_focused_app()
            # Se não estiver focado e não for o Launcher (Home), pode ser anúncio ou crash
            if self.package not in focused and "Launcher" in focused:
                 self.relaunch("App em Background")
                 return

        # Ação baseada em streak de erros
        if self.error_streak >= 10: # ~30 segundos com problema
            self.relaunch("Crash/Lag Detectado")

    def relaunch(self, reason):
        self.last_action = reason
        self.manager.log(f"[{self.package}] {reason}")
        self.manager.webhook(f"☀️ **SUNA**: `{self.package}` reiniciado. Motivo: {reason}")
        
        ADB.run(f"am force-stop {self.package}")
        time.sleep(1)
        # Abre direto no link VIP
        ADB.run(f"am start -a android.intent.action.VIEW -d '{VIP_LINK}' {self.package}")
        
        self.cooldown_until = time.time() + COOLDOWN_TIME
        self.error_streak = 0
        self.status = "RESTARTING"

    def loop(self):
        while self.is_running and self.manager.running:
            self.get_stats()
            self.check_health()
            time.sleep(CHECK_INTERVAL)

# --- GERENCIADOR PRINCIPAL ---
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
        if not WEBHOOK_URL: return
        try: requests.post(WEBHOOK_URL, json={"content": content}, timeout=2)
        except: pass

    def auto_setup(self):
        rprint("[bold yellow]☀️ Calibrando dispositivo...[/bold yellow]")
        self.device_ram = ADB.get_device_info()
        rprint(f"[cyan]ℹ️ RAM Total Detectada: {self.device_ram:.0f} MB[/cyan]")
        rprint(f"[cyan]ℹ️ Trigger de Crash: < {MIN_RAM_MB} MB RAM[/cyan]")
        time.sleep(2)

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
                    table.add_column("RAM (MB)", justify="right")
                    table.add_column("CPU (%)", justify="right")
                    table.add_column("STATUS", justify="center")
                    table.add_column("ULT. AÇÃO")

                    for p, inst in self.instances.items():
                        if inst.status == "RUNNING": s_style = "bold green"
                        elif inst.status == "COOLDOWN": s_style = "blue"
                        elif "IDLE" in inst.status: s_style = "bold red"
                        else: s_style = "yellow"

                        name = p.split('.')[-1].upper()
                        table.add_row(
                            name,
                            f"{inst.ram:.1f}",
                            f"{inst.cpu:.1f}%",
                            f"[{s_style}]{inst.status}[/{s_style}]",
                            inst.last_action
                        )

                    layout["body"].update(Panel(table, title=f"[bold yellow]MONITORAMENTO (Total RAM: {self.device_ram:.0f}MB)[/bold yellow]", border_style="yellow"))
                    
                    log_text = "\n".join(self.logs)
                    layout["footer"].update(Panel(log_text, title="LOGS", border_style="white"))
                    
                    time.sleep(0.5)
            except KeyboardInterrupt:
                self.running = False

# --- MENU ---
import datetime
def main():
    # CORREÇÃO AQUI: As variáveis globais devem ser declaradas no início da função
    global VIP_LINK, WEBHOOK_URL
    
    while True:
        console.clear()
        rprint(Align.center(SUNA_ART))
        rprint(Panel(f"[yellow]VIP:[/yellow] {VIP_LINK[:30]}...\n[yellow]WEBHOOK:[/yellow] {'Ativo' if WEBHOOK_URL else 'Off'}", border_style="yellow"))
        
        rprint("[1] ☀️ INICIAR SUNA HUB")
        rprint("[2] ⚙️ CONFIGURAR")
        rprint("[3] 🛠️ FERRAMENTAS EXTRAS")
        rprint("[0] ❌ SAIR")
        
        opt = Prompt.ask("\n[bold yellow]Escolha[/bold yellow]", choices=["1", "2", "3", "0"])
        
        if opt == "1":
            if not VIP_LINK:
                rprint("[red]Configure o Link VIP primeiro![/red]")
                time.sleep(2)
            else:
                mgr = SunaManager()
                mgr.start()
        
        elif opt == "2":
            VIP_LINK = Prompt.ask("Link do Servidor VIP", default=VIP_LINK)
            WEBHOOK_URL = Prompt.ask("Webhook Discord (Opcional)", default=WEBHOOK_URL)
            save_config({"vip_link": VIP_LINK, "webhook_url": WEBHOOK_URL})
            
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
