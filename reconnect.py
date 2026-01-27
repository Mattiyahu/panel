#!/usr/bin/env python3
"""
SHEROLINE v1
Sistema Autônomo de Monitoramento Roblox

Autor: MSA
"""

import os
import sys
import json
import time
import shutil
import subprocess
import threading
import re
from pathlib import Path
from typing import Dict, List
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
import requests

# ==========================================================
# RICH
# ==========================================================

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt
    from rich.live import Live
    from rich.text import Text
    from rich.align import Align
    from rich.layout import Layout
    from rich.box import ROUNDED
    from rich import print as rprint
except ImportError:
    os.system("pip install rich")
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt
    from rich.live import Live
    from rich.text import Text
    from rich.align import Align
    from rich.layout import Layout
    from rich.box import ROUNDED
    from rich import print as rprint

console = Console()

# ==========================================================
# ARQUIVOS
# ==========================================================

BASE_DIR = Path(__file__).parent
LINKS_FILE = BASE_DIR / "links.json"

# ==========================================================
# ESTADOS
# ==========================================================

class RobloxState(Enum):
    CLOSED = "Fechado"
    HOME = "Inicial"
    LOADING = "Carregando"
    IN_GAME = "Ativo"

# ==========================================================
# CONFIG
# ==========================================================

@dataclass
class Config:
    check_interval: int = 3
    ram_active_min: int = 1200
    cpu_idle_max: float = 3.0

CFG = Config()

# ==========================================================
# LINKS
# ==========================================================

def load_links():
    if not LINKS_FILE.exists():
        LINKS_FILE.write_text(json.dumps({
            "server_link": "",
            "webhook_url": ""
        }, indent=4), encoding="utf-8")

    with open(LINKS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_links(data):
    with open(LINKS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

LINKS = load_links()

# ==========================================================
# AUTO SETUP ADB
# ==========================================================

def adb_cmd(cmd, timeout=5):
    try:
        r = subprocess.run(
            ["adb"] + cmd,
            capture_output=True,
            timeout=timeout,
            text=True
        )
        return r.stdout.strip()
    except:
        return ""

def adb_available():
    return shutil.which("adb") is not None

def adb_autosetup():
    rprint("[cyan]Verificando ADB...[/cyan]")

    if not adb_available():
        rprint("[red]ADB não encontrado no sistema.[/red]")
        rprint("[yellow]Instale Android Platform Tools e reinicie o script.[/yellow]")
        sys.exit(1)

    subprocess.run(["adb", "kill-server"], stdout=subprocess.DEVNULL)
    subprocess.run(["adb", "start-server"], stdout=subprocess.DEVNULL)

    rprint("[green]Servidor ADB iniciado.[/green]")

    while True:
        out = subprocess.run(["adb", "devices"], capture_output=True, text=True).stdout
        lines = out.strip().splitlines()
        if len(lines) > 1 and "device" in lines[1]:
            rprint("[green]Dispositivo conectado.[/green]")
            break
        rprint("[yellow]Aguardando dispositivo ADB...[/yellow]")
        time.sleep(2)

# ==========================================================
# ADB UTILS
# ==========================================================

def adb_shell(cmd):
    return adb_cmd(["shell"] + cmd)

def get_packages():
    out = adb_shell(["pm", "list", "packages"])
    return [l.replace("package:", "") for l in out.splitlines() if "roblox" in l.lower()]

def get_pid(pkg):
    return adb_shell(["pidof", pkg])

def get_cpu(pid):
    if not pid:
        return 0.0
    out = adb_shell(["top", "-n", "1", "-p", pid])
    for p in out.split():
        if "%" in p:
            try:
                return float(p.replace("%", "").replace(",", "."))
            except:
                pass
    return 0.0

def get_ram(pid):
    if not pid:
        return 0
    out = adb_shell(["dumpsys", "meminfo", pid])
    m = re.search(r"TOTAL\s+(\d+)", out)
    return int(m.group(1)) // 1024 if m else 0

def stop_app(pkg):
    adb_shell(["am", "force-stop", pkg])

def start_app(pkg):
    adb_shell(["monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1"])

def start_app_link(pkg, link):
    adb_shell(["am", "start", "-a", "android.intent.action.VIEW", "-d", link])

# ==========================================================
# SCREENSHOT
# ==========================================================

def capture_screenshot(path):
    try:
        remote = f"/sdcard/sc_{int(time.time()*1000)}.png"
        subprocess.run(["adb", "shell", "screencap", "-p", remote], timeout=3, check=True)
        subprocess.run(["adb", "pull", remote, path], timeout=5, check=True)
        subprocess.run(["adb", "shell", "rm", remote], timeout=2)
        return Path(path).exists()
    except:
        return False

# ==========================================================
# DETECTOR
# ==========================================================

def detect_state(cpu, ram):
    if ram == 0:
        return RobloxState.CLOSED
    if ram >= CFG.ram_active_min:
        return RobloxState.IN_GAME
    if cpu <= CFG.cpu_idle_max:
        return RobloxState.HOME
    return RobloxState.LOADING

# ==========================================================
# WEBHOOK
# ==========================================================

def send_webhook(msg, screenshot=False):
    url = LINKS.get("webhook_url")
    if not url:
        return

    files = None
    img = None

    if screenshot:
        img = BASE_DIR / f"sc_{int(time.time())}.png"
        if capture_screenshot(str(img)):
            with open(img, "rb") as f:
                files = {"file": ("screen.png", f.read(), "image/png")}

    payload = {"content": msg}

    try:
        if files:
            requests.post(url, data={"payload_json": json.dumps(payload)}, files=files, timeout=10)
        else:
            requests.post(url, json=payload, timeout=10)
    except:
        pass

    if img and img.exists():
        img.unlink()

# ==========================================================
# INSTÂNCIA
# ==========================================================

class Instance:
    def __init__(self, pkg):
        self.pkg = pkg
        self.name = pkg.split(".")[-1].upper()
        self.pid = ""
        self.cpu = 0.0
        self.ram = 0
        self.state = RobloxState.CLOSED
        self.cooldown = 0
        self.lock = threading.Lock()

    def update(self):
        with self.lock:
            self.pid = get_pid(self.pkg)
            self.cpu = get_cpu(self.pid)
            self.ram = get_ram(self.pid)
            self.state = detect_state(self.cpu, self.ram)

    def restart(self, reason):
        self.cooldown = time.time() + 120
        stop_app(self.pkg)
        time.sleep(0.5)
        send_webhook(f"🔄 **{self.name}**: {reason}", True)
        start_app_link(self.pkg, LINKS["server_link"])

# ==========================================================
# MONITOR
# ==========================================================

class Monitor:
    def __init__(self):
        self.instances: Dict[str, Instance] = {}
        self.logs = []
        self.running = False

    def log(self, m):
        t = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{t}] {m}")
        self.logs = self.logs[-10:]

    def worker(self, inst):
        while self.running:
            inst.update()
            if time.time() > inst.cooldown:
                if inst.state in (RobloxState.CLOSED, RobloxState.HOME):
                    self.log(f"{inst.name}: reinício")
                    inst.restart(inst.state.value)
            time.sleep(CFG.check_interval)

    def start(self):
        pkgs = get_packages()
        if not pkgs:
            rprint("[yellow]Nenhum Roblox encontrado[/yellow]")
            return

        self.running = True
        for p in pkgs:
            i = Instance(p)
            i.cooldown = time.time() + 60
            self.instances[p] = i
            threading.Thread(target=self.worker, args=(i,), daemon=True).start()

        send_webhook("🚀 Monitor iniciado")

        with Live(self.render(), refresh_per_second=2, screen=True):
            while self.running:
                time.sleep(0.5)

    def render(self):
        title = Text(
            """
███████╗██╗  ██╗███████╗██████╗  ██████╗ ██╗     ██╗███╗   ██╗███████╗
██╔════╝██║  ██║██╔════╝██╔══██╗██╔═══██╗██║     ██║████╗  ██║██╔════╝
███████╗███████║█████╗  ██████╔╝██║   ██║██║     ██║██╔██╗ ██║█████╗  
╚════██║██╔══██║██╔══╝  ██╔══██╗██║   ██║██║     ██║██║╚██╗██║██╔══╝  
███████║██║  ██║███████╗██║  ██║╚██████╔╝███████╗██║██║ ╚████║███████╗
╚══════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝╚═╝  ╚═══╝╚══════╝
""",
            style="bold cyan",
            justify="center"
        )

        table = Table(box=ROUNDED, expand=True, border_style="cyan")
        table.add_column("INST")
        table.add_column("CPU")
        table.add_column("RAM")
        table.add_column("ESTADO")

        for i in self.instances.values():
            with i.lock:
                table.add_row(i.name, f"{i.cpu:.1f}%", f"{i.ram} MB", i.state.value)

        logs = Panel("\n".join(self.logs) or "...", border_style="cyan")

        layout = Layout()
        layout.split_column(
            Layout(Align.center(title), size=9),
            Layout(table, size=12),
            Layout(logs, size=8)
        )
        return layout

# ==========================================================
# MAIN
# ==========================================================

def main():
    adb_autosetup()
    mon = Monitor()

    while True:
        os.system("cls" if os.name == "nt" else "clear")
        rprint("[bold cyan]SHEROLINE v1[/bold cyan]\n")
        rprint("1 - Iniciar monitor")
        rprint("2 - Configurar Webhook")
        rprint("3 - Configurar Server Link")
        rprint("0 - Sair\n")

        c = Prompt.ask(">", choices=["0", "1", "2", "3"])

        if c == "1":
            mon.start()
        elif c == "2":
            LINKS["webhook_url"] = Prompt.ask("Webhook URL")
            save_links(LINKS)
        elif c == "3":
            LINKS["server_link"] = Prompt.ask("Server Link")
            save_links(LINKS)
        elif c == "0":
            break

if __name__ == "__main__":
    main()
