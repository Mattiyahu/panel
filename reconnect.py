#!/usr/bin/env python3
"""
SHEROLINE v1.1 - CORRIGIDO
Sistema Autônomo de Monitoramento Roblox

Autor: MSA
Correções: Interface dinâmica, timeouts ADB, detecção robusta de pacotes
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
from typing import Dict
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
    os.system(f"{sys.executable} -m pip install -q rich")
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
    adb_timeout: int = 8  # Timeout global para comandos ADB

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

def adb_cmd(cmd, timeout=CFG.adb_timeout):
    try:
        r = subprocess.run(
            ["adb"] + cmd,
            capture_output=True,
            timeout=timeout,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        return r.stdout.strip()
    except subprocess.TimeoutExpired:
        console.print(f"[red]⚠ Timeout ADB: {' '.join(cmd)}[/red]")
        return ""
    except Exception as e:
        console.print(f"[red]⚠ Erro ADB: {e}[/red]")
        return ""

def adb_available():
    return shutil.which("adb") is not None

def adb_autosetup():
    rprint("[cyan]Verificando ADB...[/cyan]")

    if not adb_available():
        rprint("[red]❌ ADB não encontrado no sistema.[/red]")
        rprint("[yellow]Solução: Instale Android Platform Tools e reinicie o script.[/yellow]")
        sys.exit(1)

    subprocess.run(["adb", "kill-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["adb", "start-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    rprint("[green]✓ Servidor ADB iniciado[/green]")

    # Aguarda no máximo 30 segundos pelo dispositivo
    for _ in range(15):
        out = subprocess.run(["adb", "devices"], capture_output=True, text=True).stdout
        lines = [l for l in out.strip().splitlines() if "device" in l and not l.startswith("List")]
        if lines:
            rprint(f"[green]✓ Dispositivo conectado: {lines[0].split()[0]}[/green]")
            return
        rprint("[yellow]⏳ Aguardando dispositivo ADB... (pressione Ctrl+C para cancelar)[/yellow]")
        time.sleep(2)
    
    rprint("[red]❌ Tempo esgotado: Nenhum dispositivo encontrado[/red]")
    sys.exit(1)

# ==========================================================
# ADB UTILS (com timeouts rigorosos)
# ==========================================================

def adb_shell(cmd, timeout=CFG.adb_timeout):
    return adb_cmd(["shell"] + cmd + ["2>/dev/null"], timeout=timeout)

def get_packages():
    out = adb_shell(["pm", "list", "packages"], timeout=10)
    packages = []
    for line in out.splitlines():
        pkg = line.replace("package:", "").strip()
        # Detecção robusta: case-insensitive + nomes alternativos
        if any(k in pkg.lower() for k in ["roblox", "rbx", "com.roblox"]):
            packages.append(pkg)
    return packages

def get_pid(pkg):
    return adb_shell(["pidof", pkg], timeout=3)

def get_cpu(pid):
    if not pid or not pid.strip().isdigit():
        return 0.0
    out = adb_shell(["top", "-n", "1", "-p", pid], timeout=4)
    for p in out.split():
        if "%" in p:
            try:
                return float(p.replace("%", "").replace(",", "."))
            except:
                pass
    return 0.0

def get_ram(pid):
    if not pid or not pid.strip().isdigit():
        return 0
    out = adb_shell(["dumpsys", "meminfo", pid], timeout=5)
    m = re.search(r"TOTAL\s+(\d+)", out)
    return int(m.group(1)) // 1024 if m else 0

def stop_app(pkg):
    adb_shell(["am", "force-stop", pkg], timeout=3)

def start_app_link(pkg, link):
    adb_shell(["am", "start", "-a", "android.intent.action.VIEW", "-d", f'"{link}"'], timeout=4)

# ==========================================================
# SCREENSHOT
# ==========================================================

def capture_screenshot(path):
    try:
        remote = f"/sdcard/sc_{int(time.time()*1000)}.png"
        subprocess.run(["adb", "shell", "screencap", "-p", remote], timeout=4, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["adb", "pull", remote, path], timeout=6, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["adb", "shell", "rm", remote], timeout=2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return Path(path).exists()
    except Exception as e:
        console.print(f"[red]⚠ Falha no screenshot: {e}[/red]")
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
            try:
                with open(img, "rb") as f:
                    files = {"file": ("screen.png", f.read(), "image/png")}
            except:
                files = None

    payload = {"content": msg}

    try:
        if files:
            requests.post(url, data={"payload_json": json.dumps(payload)}, files=files, timeout=8)
        else:
            requests.post(url, json=payload, timeout=8)
    except Exception as e:
        console.print(f"[red]⚠ Falha no webhook: {e}[/red]")

    if img and img.exists():
        try:
            img.unlink()
        except:
            pass

# ==========================================================
# INSTÂNCIA
# ==========================================================

class Instance:
    def __init__(self, pkg):
        self.pkg = pkg
        self.name = pkg.split(".")[-1].upper()[:10]  # Nome curto para exibição
        self.pid = ""
        self.cpu = 0.0
        self.ram = 0
        self.state = RobloxState.CLOSED
        self.cooldown = 0
        self.lock = threading.Lock()

    def update(self):
        with self.lock:
            try:
                self.pid = get_pid(self.pkg)
                self.cpu = get_cpu(self.pid) if self.pid else 0.0
                self.ram = get_ram(self.pid) if self.pid else 0
                self.state = detect_state(self.cpu, self.ram)
            except Exception as e:
                console.print(f"[red]Erro na atualização {self.name}: {e}[/red]")

    def restart(self, reason):
        with self.lock:
            self.cooldown = time.time() + 120
            stop_app(self.pkg)
            time.sleep(1.0)
            send_webhook(f"🔄 **{self.name}**: {reason}", True)
            if LINKS.get("server_link"):
                start_app_link(self.pkg, LINKS["server_link"])
            else:
                console.print("[yellow]⚠ Server Link não configurado - iniciando app normalmente[/yellow]")
                adb_shell(["monkey", "-p", self.pkg, "-c", "android.intent.category.LAUNCHER", "1"], timeout=3)

# ==========================================================
# MONITOR
# ==========================================================

class Monitor:
    def __init__(self):
        self.instances: Dict[str, Instance] = {}
        self.logs = []
        self.running = False
        self.lock = threading.Lock()

    def log(self, m):
        t = datetime.now().strftime("%H:%M:%S")
        with self.lock:
            self.logs.append(f"[{t}] {m}")
            self.logs = self.logs[-15:]  # Mantém últimos 15 logs

    def worker(self, inst):
        while self.running:
            try:
                inst.update()
                if time.time() > inst.cooldown:
                    if inst.state in (RobloxState.CLOSED, RobloxState.HOME):
                        self.log(f"{inst.name}: reiniciando ({inst.state.value})")
                        inst.restart(inst.state.value)
            except Exception as e:
                self.log(f"Erro worker {inst.name}: {e}")
            time.sleep(CFG.check_interval)

    def start(self):
        pkgs = get_packages()
        if not pkgs:
            rprint("[yellow]⚠ Nenhum pacote do Roblox encontrado no dispositivo[/yellow]")
            rprint("[dim]Dica: Verifique se o Roblox está instalado e o dispositivo está autorizado[/dim]")
            time.sleep(3)
            return

        self.running = True
        self.instances.clear()
        
        for p in pkgs:
            i = Instance(p)
            i.cooldown = time.time() + 60  # Cooldown inicial para evitar reinícios imediatos
            self.instances[p] = i
            threading.Thread(target=self.worker, args=(i,), daemon=True, name=f"Worker-{p}").start()
            self.log(f"Monitorando: {i.name}")

        send_webhook("🚀 Monitor SHEROLINE iniciado")

        # Listener para tecla 'Q' sair do monitor
        def listen_quit():
            if os.name == 'nt':
                import msvcrt
                while self.running:
                    if msvcrt.kbhit():
                        key = msvcrt.getch()
                        if key in [b'q', b'Q']:
                            self.log("Saindo do monitor (tecla Q)...")
                            self.running = False
                    time.sleep(0.1)
            else:
                import sys, select
                while self.running:
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        if sys.stdin.read(1) in ('q', 'Q'):
                            self.log("Saindo do monitor (tecla Q)...")
                            self.running = False

        threading.Thread(target=listen_quit, daemon=True, name="QuitListener").start()

        # Interface DINÂMICA com atualização automática
        with Live(
            renderable=lambda: self.render(),  # ← CORREÇÃO PRINCIPAL: callable para atualização contínua
            refresh_per_second=2,
            screen=True,
            transient=False
        ) as live:
            self.log(f"Iniciado com {len(pkgs)} instância(s)")
            while self.running:
                time.sleep(0.3)  # Pequeno delay para não sobrecarregar CPU
            
        # Pós-monitoramento
        for inst in self.instances.values():
            stop_app(inst.pkg)
        self.log("Monitor finalizado")
        time.sleep(1)

    def render(self):
        title = Text(
            """
███████╗██╗  ██╗███████╗██████╗  ██████╗ ██╗     ██╗███╗   ██╗███████╗
██╔════╝██║  ██║██╔════╝██╔══██╗██╔═══██╗██║     ██║████╗  ██║██╔════╝
███████╗███████║█████╗  ██████╔╝██║   ██║██║     ██║██╔██╗ ██║█████╗  
╚════██║██╔══██║██╔══╝  ██╔══██╗██║   ██║██║     ██║██║╚██╗██║██╔══╝  
███████║██║  ██║███████╗██║  ██║╚██████╔╝███████╗██║██║ ╚████║███████╗
╚══════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝╚═╝  ╚═══╝╚══════╝
        v1.1 - CORRIGIDO
""",
            style="bold cyan",
            justify="center"
        )

        table = Table(box=ROUNDED, expand=True, border_style="cyan", title="INSTÂNCIAS ROBLOX", title_style="bold yellow")
        table.add_column("INSTÂNCIA", style="bold green")
        table.add_column("CPU", justify="right")
        table.add_column("RAM", justify="right")
        table.add_column("ESTADO", style="bold cyan")

        with self.lock:
            if not self.instances:
                table.add_row("[dim]Nenhuma instância[/dim]", "", "", "")
            else:
                for i in self.instances.values():
                    with i.lock:
                        cpu_color = "green" if i.cpu < 30 else "yellow" if i.cpu < 70 else "red"
                        ram_color = "green" if i.ram < 800 else "yellow" if i.ram < 1500 else "red"
                        state_style = {
                            RobloxState.CLOSED: "red",
                            RobloxState.HOME: "yellow",
                            RobloxState.LOADING: "blue",
                            RobloxState.IN_GAME: "green"
                        }.get(i.state, "white")
                        
                        table.add_row(
                            i.name,
                            f"[{cpu_color}]{i.cpu:.1f}%[/{cpu_color}]",
                            f"[{ram_color}]{i.ram} MB[/{ram_color}]",
                            f"[{state_style}]{i.state.value}[/{state_style}]"
                        )

        with self.lock:
            logs_text = "\n".join(self.logs) if self.logs else "[dim]Aguardando eventos...[/dim]"
        logs_panel = Panel(
            logs_text,
            title="LOGS (pressione Q para sair)",
            border_style="cyan",
            height=10
        )

        layout = Layout()
        layout.split_column(
            Layout(Align.center(title), size=11),
            Layout(table, size=8 + len(self.instances)),
            Layout(logs_panel, size=11)
        )
        return layout

# ==========================================================
# MAIN
# ==========================================================

def main():
    try:
        adb_autosetup()
    except KeyboardInterrupt:
        rprint("\n[yellow]Cancelado pelo usuário[/yellow]")
        sys.exit(0)
    
    mon = Monitor()

    while True:
        os.system("cls" if os.name == "nt" else "clear")
        rprint("[bold cyan]SHEROLINE v1.1[/bold cyan] - Sistema de Monitoramento Roblox\n")
        rprint("1 - Iniciar monitoramento")
        rprint("2 - Configurar Webhook Discord")
        rprint("3 - Configurar Server Link")
        rprint("4 - Testar conexão ADB")
        rprint("0 - Sair\n")
        
        try:
            c = Prompt.ask("[bold green]Escolha uma opção[/bold green]", choices=["0", "1", "2", "3", "4"], default="1")
        except KeyboardInterrupt:
            break

        if c == "1":
            if not LINKS.get("server_link"):
                rprint("[red]⚠ Server Link não configurado! Configure na opção 3.[/red]")
                time.sleep(2)
                continue
            mon.start()
        elif c == "2":
            url = Prompt.ask("Cole a URL do Webhook Discord", default=LINKS.get("webhook_url", ""))
            if url.startswith("https://discord.com/api/webhooks/"):
                LINKS["webhook_url"] = url
                save_links(LINKS)
                rprint("[green]✓ Webhook salvo com sucesso[/green]")
            else:
                rprint("[red]⚠ URL inválida (deve começar com https://discord.com/api/webhooks/)[/red]")
            time.sleep(2)
        elif c == "3":
            link = Prompt.ask("Cole o Server Link do Roblox", default=LINKS.get("server_link", ""))
            if "roblox.com" in link or "rbx" in link:
                LINKS["server_link"] = link
                save_links(LINKS)
                rprint("[green]✓ Server Link salvo com sucesso[/green]")
            else:
                rprint("[yellow]⚠ Link pode não ser válido (deve conter 'roblox.com' ou 'rbx')[/yellow]")
            time.sleep(2)
        elif c == "4":
            rprint("[cyan]Testando conexão ADB...[/cyan]")
            pkgs = get_packages()
            if pkgs:
                rprint(f"[green]✓ Dispositivo conectado[/green]")
                rprint(f"[green]✓ Pacotes encontrados: {', '.join(pkgs)}[/green]")
            else:
                rprint("[red]✗ Nenhum pacote Roblox encontrado[/red]")
                rprint("[dim]Verifique se o Roblox está instalado no dispositivo[/dim]")
            time.sleep(3)
        elif c == "0":
            break

    rprint("\n[bold cyan]SHEROLINE finalizado[/bold cyan]")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        rprint("\n[yellow]Encerrado pelo usuário[/yellow]")
        sys.exit(0)
    except Exception as e:
        rprint(f"\n[red]❌ Erro fatal: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)
