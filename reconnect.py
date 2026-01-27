#!/usr/bin/env python3
"""
SHORELINE v1
Sistema Profissional de Monitoramento para Roblox

Autor: MSA
"""

import os
import json
import time
import subprocess
import threading
import re
from pathlib import Path
from typing import Dict, List
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import requests

# ═══════════════════════════════════════════════════════════════
# RICH
# ═══════════════════════════════════════════════════════════════

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt
    from rich.live import Live
    from rich.text import Text
    from rich.align import Align
    from rich.box import ROUNDED
    from rich.layout import Layout
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
    from rich.box import ROUNDED
    from rich.layout import Layout
    from rich import print as rprint

console = Console()

# ═══════════════════════════════════════════════════════════════
# ESTADOS
# ═══════════════════════════════════════════════════════════════

class RobloxState(Enum):
    CLOSED = "Fechado"
    HOME = "Inicial"
    LOADING = "Carregando"
    IN_GAME = "Ativo"
    UNKNOWN = "Indefinido"


# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

@dataclass
class MonitorConfig:
    webhook_url: str = ""
    server_link: str = ""
    check_interval: int = 3
    cpu_idle_max: float = 3.0
    ram_active_min: int = 1200  # REGRA DE OURO

CONFIG_FILE = "shoreline_config.json"


def load_config() -> MonitorConfig:
    if Path(CONFIG_FILE).exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return MonitorConfig(**json.load(f))
        except:
            pass
    return MonitorConfig()


def save_config(cfg: MonitorConfig):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(asdict(cfg), f, indent=4, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# ADB
# ═══════════════════════════════════════════════════════════════

def adb(cmd: list, timeout=5) -> str:
    try:
        r = subprocess.run(
            ["adb", "shell"] + cmd,
            capture_output=True,
            timeout=timeout,
            text=True
        )
        return r.stdout.strip()
    except:
        return ""


def adb_ok() -> bool:
    try:
        r = subprocess.run(["adb", "devices"], capture_output=True, text=True)
        return "device" in r.stdout.splitlines()[-1]
    except:
        return False


def get_packages() -> List[str]:
    out = adb(["pm", "list", "packages"])
    return [
        l.replace("package:", "")
        for l in out.splitlines()
        if "roblox" in l.lower()
    ]


def get_pid(pkg: str) -> str:
    return adb(["pidof", pkg])


def get_cpu(pid: str) -> float:
    if not pid:
        return 0.0
    out = adb(["top", "-n", "1", "-p", pid])
    for p in out.split():
        if "%" in p:
            try:
                return float(p.replace("%", "").replace(",", "."))
            except:
                pass
    return 0.0


def get_ram(pid: str) -> int:
    if not pid:
        return 0
    out = adb(["dumpsys", "meminfo", pid])
    m = re.search(r"TOTAL\s+(\d+)", out)
    return int(m.group(1)) // 1024 if m else 0


def stop_app(pkg: str):
    adb(["am", "force-stop", pkg])


def start_app(pkg: str):
    adb(["monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1"])


def start_app_link(pkg: str, link: str):
    adb([
        "am", "start",
        "-a", "android.intent.action.VIEW",
        "-d", link
    ])


# ═══════════════════════════════════════════════════════════════
# SCREENSHOT (SAFE)
# ═══════════════════════════════════════════════════════════════

def capture_screenshot(path: str) -> bool:
    try:
        remote = f"/sdcard/sc_{int(time.time()*1000)}.png"

        subprocess.run(
            ["adb", "shell", "screencap", "-p", remote],
            timeout=3,
            check=True
        )
        subprocess.run(
            ["adb", "pull", remote, path],
            timeout=5,
            check=True
        )
        subprocess.run(
            ["adb", "shell", "rm", remote],
            timeout=2
        )
        return Path(path).exists()
    except:
        return False


# ═══════════════════════════════════════════════════════════════
# DETECTOR
# ═══════════════════════════════════════════════════════════════

def detect_state(cpu: float, ram: int, cfg: MonitorConfig) -> RobloxState:
    if ram == 0:
        return RobloxState.CLOSED

    if ram >= cfg.ram_active_min:
        return RobloxState.IN_GAME

    if cpu <= cfg.cpu_idle_max:
        return RobloxState.HOME

    return RobloxState.LOADING


# ═══════════════════════════════════════════════════════════════
# WEBHOOK
# ═══════════════════════════════════════════════════════════════

def send_webhook(url: str, msg: str, screenshot=False):
    if not url:
        return

    files = None
    path = None

    if screenshot:
        path = f"/tmp/sc_{int(time.time())}.png"
        if capture_screenshot(path):
            with open(path, "rb") as f:
                files = {"file": ("screen.png", f.read(), "image/png")}

    payload = {"content": msg}

    try:
        if files:
            requests.post(
                url,
                data={"payload_json": json.dumps(payload)},
                files=files,
                timeout=10
            )
        else:
            requests.post(url, json=payload, timeout=10)
    except:
        pass

    if path and Path(path).exists():
        os.remove(path)


# ═══════════════════════════════════════════════════════════════
# INSTÂNCIA
# ═══════════════════════════════════════════════════════════════

class Instance:
    def __init__(self, pkg: str, cfg: MonitorConfig):
        self.pkg = pkg
        self.name = pkg.split(".")[-1].upper()
        self.cfg = cfg
        self.pid = ""
        self.cpu = 0.0
        self.ram = 0
        self.state = RobloxState.UNKNOWN
        self.cooldown = 0
        self.lock = threading.Lock()

    def update(self):
        with self.lock:
            self.pid = get_pid(self.pkg)
            self.cpu = get_cpu(self.pid)
            self.ram = get_ram(self.pid)
            self.state = detect_state(self.cpu, self.ram, self.cfg)

    def restart(self, reason: str):
        self.cooldown = time.time() + 120
        stop_app(self.pkg)
        time.sleep(0.5)
        send_webhook(self.cfg.webhook_url, f"🔄 **{self.name}**: {reason}", True)
        start_app_link(self.pkg, self.cfg.server_link)


# ═══════════════════════════════════════════════════════════════
# MONITOR
# ═══════════════════════════════════════════════════════════════

class Monitor:
    def __init__(self):
        self.cfg = load_config()
        self.instances: Dict[str, Instance] = {}
        self.running = False
        self.logs: List[str] = []

    def log(self, msg: str):
        t = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{t}] {msg}")
        self.logs = self.logs[-10:]

    def worker(self, inst: Instance):
        while self.running:
            inst.update()
            if time.time() > inst.cooldown:
                if inst.state in (RobloxState.CLOSED, RobloxState.HOME):
                    self.log(f"{inst.name}: reiniciando")
                    inst.restart(inst.state.value)
            time.sleep(self.cfg.check_interval)

    def start(self):
        if not adb_ok():
            rprint("[red]ADB não conectado[/red]")
            return

        pkgs = get_packages()
        if not pkgs:
            rprint("[yellow]Nenhum Roblox encontrado[/yellow]")
            return

        self.running = True
        for p in pkgs:
            inst = Instance(p, self.cfg)
            inst.cooldown = time.time() + 60
            self.instances[p] = inst
            threading.Thread(target=self.worker, args=(inst,), daemon=True).start()

        send_webhook(self.cfg.webhook_url, "🚀 Monitor iniciado")

        with Live(self.render(), refresh_per_second=2, screen=True) as live:
            try:
                while self.running:
                    live.update(self.render())
                    time.sleep(0.5)
            except KeyboardInterrupt:
                self.running = False

        send_webhook(self.cfg.webhook_url, "⏹️ Monitor finalizado")

    def render(self):
        header = Text("SHORELINE v1", style="bold white on cyan", justify="center")

        table = Table(box=ROUNDED, expand=True, border_style="cyan")
        table.add_column("INST", style="bold")
        table.add_column("CPU")
        table.add_column("RAM")
        table.add_column("ESTADO")

        for inst in self.instances.values():
            with inst.lock:
                table.add_row(
                    inst.name,
                    f"{inst.cpu:.1f}%",
                    f"{inst.ram} MB",
                    inst.state.value
                )

        logs = Panel("\n".join(self.logs) or "...", border_style="cyan")

        layout = Layout()
        layout.split_column(
            Layout(Align.center(header), size=3),
            Layout(table, size=12),
            Layout(logs, size=8)
        )
        return layout


# ═══════════════════════════════════════════════════════════════
# MENU
# ═══════════════════════════════════════════════════════════════

def menu():
    mon = Monitor()
    cfg = mon.cfg

    while True:
        os.system("cls" if os.name == "nt" else "clear")
        rprint("[bold cyan]SHORELINE v1[/bold cyan]\n")
        rprint("1 - Iniciar")
        rprint("2 - Configurar Webhook")
        rprint("3 - Configurar Link")
        rprint("0 - Sair\n")

        c = Prompt.ask(">", choices=["0", "1", "2", "3"])

        if c == "1":
            mon.start()
        elif c == "2":
            cfg.webhook_url = Prompt.ask("Webhook URL")
            save_config(cfg)
        elif c == "3":
            cfg.server_link = Prompt.ask("Server Link")
            save_config(cfg)
        elif c == "0":
            break


if __name__ == "__main__":
    menu()
