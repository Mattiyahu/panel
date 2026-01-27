#!/usr/bin/env python3
"""
RE_PHONE RETRO v2.0 🌸
Sistema de Monitoramento para Roblox - VSPhone

Tema: Gradiente Vermelho → Rosa (Retro/Synthwave)
- Interface Rich melhorada
- Monitoramento em tempo real funcional
- Detecção de tela de key via CPU/RAM
- Envio de screenshot via webhook
"""
import os
import subprocess
import time
import requests
import datetime
import json
import threading
import re
import sys
from io import BytesIO
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.align import Align
from rich.box import ROUNDED, DOUBLE, HEAVY
from rich.style import Style
from rich.progress import SpinnerColumn, Progress
from rich import print as rprint

# ═══════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES GLOBAIS
# ═══════════════════════════════════════════════════════════════════
console = Console()
CONFIG_FILE = "config_retro.json"

# Thresholds de monitoramento
CPU_PLAYING = 15.0          # CPU acima = jogando
CPU_KEY_SCREEN = 5.0        # CPU abaixo = possível tela de key
CHECK_INTERVAL = 2          # Intervalo entre verificações
KEY_DETECT_COUNT = 4        # Verificações consecutivas para detectar key
COOLDOWN_TIME = 120         # Cooldown após restart

# Estilos do tema Retro (Vermelho → Rosa)
STYLE_RED = Style(color="red", bold=True)
STYLE_PINK = Style(color="magenta", bold=True)
STYLE_ROSE = Style(color="bright_magenta")
STYLE_HOT = Style(color="bright_red")
STYLE_GRADIENT = ["red", "bright_red", "magenta", "bright_magenta"]

# ═══════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO
# ═══════════════════════════════════════════════════════════════════
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except: pass
    return {"webhook_url": "", "server_link": ""}

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=4)

CONFIG = load_config()

# ═══════════════════════════════════════════════════════════════════
# FUNÇÕES ADB
# ═══════════════════════════════════════════════════════════════════
def adb(cmd, timeout=5):
    """Executa comando ADB com timeout"""
    try:
        result = subprocess.check_output(
            f"adb shell {cmd}",
            shell=True,
            stderr=subprocess.DEVNULL,
            timeout=timeout
        ).decode(errors='ignore').strip()
        return result
    except:
        return ""

def get_packages():
    """Obtém pacotes Roblox instalados"""
    out = adb("pm list packages roblox")
    pkgs = [l.replace("package:", "").strip() for l in out.splitlines() if "roblox" in l.lower()]
    return pkgs

def get_pid(pkg):
    """Obtém PID de um pacote"""
    return adb(f"pidof {pkg}")

def get_cpu(pid):
    """Obtém uso de CPU de um processo"""
    if not pid:
        return 0.0
    try:
        # Método mais confiável usando top
        top = adb(f"top -n 1 -b | grep {pid}", timeout=3)
        if top:
            for line in top.splitlines():
                if pid in line:
                    parts = line.split()
                    for p in parts:
                        if '%' in p or (p.replace('.', '').replace(',', '').isdigit() and float(p.replace(',', '.')) < 100):
                            try:
                                val = float(p.replace('%', '').replace(',', '.'))
                                if val < 100:
                                    return val
                            except:
                                continue
        # Fallback
        top2 = adb(f"top -n 1 -p {pid}", timeout=3)
        if top2:
            for p in top2.split():
                if "%" in p:
                    try:
                        return float(p.replace("%", "").replace(",", "."))
                    except:
                        pass
    except:
        pass
    return 0.0

def get_ram(pid):
    """Obtém uso de RAM em MB"""
    if not pid:
        return 0
    try:
        out = adb(f"dumpsys meminfo {pid} 2>/dev/null | grep 'TOTAL PSS'", timeout=3)
        if not out:
            out = adb(f"dumpsys meminfo {pid} 2>/dev/null | grep 'TOTAL'", timeout=3)
        match = re.search(r'(\d+)', out)
        if match:
            return int(match.group(1)) // 1024  # KB para MB
    except:
        pass
    return 0

def take_screenshot():
    """Captura screenshot e retorna como bytes"""
    try:
        adb("screencap -p /sdcard/screen_retro.png", timeout=5)
        time.sleep(0.3)
        subprocess.run(
            "adb pull /sdcard/screen_retro.png /tmp/screen_retro.png",
            shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL, timeout=5
        )
        if os.path.exists("/tmp/screen_retro.png"):
            with open("/tmp/screen_retro.png", "rb") as f:
                return f.read()
    except:
        pass
    return None

def send_webhook(message, screenshot_bytes=None):
    """Envia mensagem para webhook com screenshot opcional"""
    webhook = CONFIG.get("webhook_url", "")
    if not webhook:
        return False
    try:
        if screenshot_bytes:
            files = {"file": ("screenshot.png", BytesIO(screenshot_bytes), "image/png")}
            response = requests.post(webhook, data={"content": message}, files=files, timeout=10)
        else:
            response = requests.post(webhook, json={"content": message, "username": "RE_PHONE RETRO 🌸"}, timeout=10)
        return response.status_code in [200, 204]
    except:
        return False

def force_portrait():
    """Força modo retrato"""
    adb("settings put system accelerometer_rotation 0")
    adb("settings put system user_rotation 0")

def stop_app(pkg):
    """Para um app"""
    adb(f"am force-stop {pkg}")

def start_app(pkg, link=""):
    """Inicia um app com link opcional"""
    if link:
        adb(f"am start -a android.intent.action.VIEW -d '{link}' {pkg}")
    else:
        activity = f"{pkg}/com.roblox.client.startup.ActivitySplash"
        adb(f"am start -n {activity}")

# ═══════════════════════════════════════════════════════════════════
# CLASSE DE INSTÂNCIA
# ═══════════════════════════════════════════════════════════════════
class Instance:
    def __init__(self, pkg, manager):
        self.pkg = pkg
        self.manager = manager
        self.name = pkg.split('.')[-1].upper()
        self.pid = ""
        self.cpu = 0.0
        self.ram = 0
        self.status = "INIT"
        self.low_cpu_count = 0
        self.cooldown_until = 0
        self.last_action = "Nenhuma"
        self.key_notified = False
        self.lock = threading.Lock()
    
    def update_metrics(self):
        """Atualiza métricas de CPU e RAM"""
        with self.lock:
            self.pid = get_pid(self.pkg)
            
            if not self.pid:
                self.status = "MORTO"
                self.cpu = 0.0
                self.ram = 0
                return
            
            # Obtém CPU e RAM
            new_cpu = get_cpu(self.pid)
            new_ram = get_ram(self.pid)
            
            # Suaviza a leitura de CPU
            if self.cpu > 0:
                self.cpu = (self.cpu + new_cpu) / 2
            else:
                self.cpu = new_cpu
            
            self.ram = new_ram
            
            # Verifica cooldown
            if time.time() < self.cooldown_until:
                self.status = "COOLDOWN"
                self.low_cpu_count = 0
                return
            
            # Determina status baseado em CPU
            if self.cpu >= CPU_PLAYING:
                self.status = "JOGANDO"
                self.low_cpu_count = 0
                self.key_notified = False
            elif self.cpu <= CPU_KEY_SCREEN:
                self.low_cpu_count += 1
                if self.low_cpu_count >= KEY_DETECT_COUNT:
                    self.status = "🔑 KEY?"
                    # Notifica apenas uma vez
                    if not self.key_notified:
                        self.key_notified = True
                        self.manager.notify_key_detected(self)
                else:
                    self.status = "BAIXO"
            else:
                self.status = "IDLE"
                self.low_cpu_count = max(0, self.low_cpu_count - 1)
    
    def restart(self, reason):
        """Reinicia a instância"""
        with self.lock:
            self.last_action = reason
            self.manager.log(f"🔄 {self.name}: {reason}")
            
            stop_app(self.pkg)
            time.sleep(1)
            
            link = CONFIG.get("server_link", "")
            start_app(self.pkg, link)
            
            self.cooldown_until = time.time() + COOLDOWN_TIME
            self.low_cpu_count = 0
            self.key_notified = False
            
            send_webhook(f"🔄 **{self.name}**: Reiniciado - {reason}")

# ═══════════════════════════════════════════════════════════════════
# MONITOR PRINCIPAL
# ═══════════════════════════════════════════════════════════════════
class RetroMonitor:
    def __init__(self):
        self.instances = {}
        self.running = False
        self.logs = []
        self.start_time = None
    
    def log(self, msg):
        """Adiciona log com timestamp"""
        t = datetime.datetime.now().strftime("%H:%M:%S")
        entry = f"[{t}] {msg}"
        self.logs.append(entry)
        if len(self.logs) > 10:
            self.logs.pop(0)
    
    def notify_key_detected(self, inst):
        """Notifica quando tela de key é detectada"""
        self.log(f"🔑 {inst.name}: Possível tela de KEY!")
        
        # Captura e envia screenshot
        screenshot = take_screenshot()
        message = f"🔑 **{inst.name}** - Possível tela de KEY detectada!\n" \
                  f"📊 CPU: {inst.cpu:.1f}% | RAM: {inst.ram}MB"
        
        if send_webhook(message, screenshot):
            self.log(f"📸 Screenshot enviado!")
        else:
            self.log(f"⚠️ Falha no webhook")
    
    def monitor_worker(self, inst):
        """Worker de monitoramento para uma instância"""
        while self.running:
            try:
                inst.update_metrics()
                
                # Verifica se precisa reiniciar
                with inst.lock:
                    if time.time() > inst.cooldown_until:
                        if inst.status == "MORTO":
                            inst.restart("Processo morto")
            except Exception as e:
                self.log(f"⚠️ Erro em {inst.name}: {str(e)[:30]}")
            
            time.sleep(CHECK_INTERVAL)
    
    def get_uptime(self):
        """Retorna tempo de execução formatado"""
        if not self.start_time:
            return "00:00:00"
        delta = datetime.datetime.now() - self.start_time
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def render(self):
        """Renderiza o HUD com tema retro"""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=7),
            Layout(name="main", size=14),
            Layout(name="logs", size=12)
        )
        
        # ═══════════════════════════════════════════════════════════
        # HEADER COM GRADIENTE
        # ═══════════════════════════════════════════════════════════
        header = Text()
        header.append("╔══════════════════════════════════════════════════════════╗\n", style="red")
        header.append("║  ", style="red")
        header.append("██████╗ ███████╗", style="red")
        header.append("      ", style="red")
        header.append("██████╗ ██╗  ██╗ ██████╗ ███╗   ██╗███████╗", style="bright_magenta")
        header.append("  ║\n", style="red")
        header.append("║  ", style="bright_red")
        header.append("RETRO", style="bold bright_magenta")
        header.append(" EDITION ", style="magenta")
        header.append("🌸", style="bright_magenta")
        header.append("                    Uptime: ", style="white")
        header.append(self.get_uptime(), style="bold cyan")
        header.append("       ║\n", style="bright_red")
        header.append("╚══════════════════════════════════════════════════════════╝", style="magenta")
        
        layout["header"].update(Panel(
            Align.center(header),
            border_style="bright_red",
            box=DOUBLE
        ))
        
        # ═══════════════════════════════════════════════════════════
        # TABELA DE INSTÂNCIAS
        # ═══════════════════════════════════════════════════════════
        table = Table(
            box=ROUNDED,
            border_style="magenta",
            expand=True,
            show_header=True,
            header_style="bold white on red",
            row_styles=["", "dim"]
        )
        
        table.add_column("🎮 INSTÂNCIA", justify="left", style="bold", width=14)
        table.add_column("⚡ CPU", justify="center", width=10)
        table.add_column("💾 RAM", justify="center", width=10)
        table.add_column("📊 STATUS", justify="center", width=14)
        table.add_column("🔧 AÇÃO", justify="center", width=16)
        
        for pkg, inst in self.instances.items():
            with inst.lock:
                # CPU com cores gradiente
                if inst.cpu >= CPU_PLAYING:
                    cpu_style = "bold green"
                    cpu_icon = "🟢"
                elif inst.cpu >= CPU_KEY_SCREEN:
                    cpu_style = "bold yellow"
                    cpu_icon = "🟡"
                else:
                    cpu_style = "bold red"
                    cpu_icon = "🔴"
                
                cpu_text = Text(f"{cpu_icon} {inst.cpu:.1f}%", style=cpu_style)
                
                # RAM
                ram_text = f"{inst.ram}MB" if inst.ram > 0 else "N/A"
                
                # Status com cores
                status_styles = {
                    "JOGANDO": ("bold green", "▶"),
                    "🔑 KEY?": ("bold yellow blink", "🔑"),
                    "MORTO": ("bold red", "💀"),
                    "COOLDOWN": ("bold blue", "⏳"),
                    "BAIXO": ("yellow", "◐"),
                    "IDLE": ("dim", "◌"),
                    "INIT": ("dim cyan", "⟳")
                }
                
                style, icon = status_styles.get(inst.status, ("white", "?"))
                status_text = Text(f"{icon} {inst.status}", style=style)
                
                # Nome com estilo
                name_text = Text(inst.name, style="bold bright_magenta")
                
                table.add_row(
                    name_text,
                    cpu_text,
                    Text(ram_text, style="cyan"),
                    status_text,
                    Text(inst.last_action[:14], style="dim")
                )
        
        # Adiciona linha de legenda
        table.add_row("", "", "", "", "")
        legend = Text()
        legend.append("🟢 Jogando  ", style="green")
        legend.append("🟡 Idle  ", style="yellow")
        legend.append("🔴 Key/Morto", style="red")
        
        layout["main"].update(Panel(
            table,
            title="[bold white on magenta] 📡 MONITORAMENTO EM TEMPO REAL [/bold white on magenta]",
            border_style="bright_red",
            box=HEAVY
        ))
        
        # ═══════════════════════════════════════════════════════════
        # LOGS
        # ═══════════════════════════════════════════════════════════
        log_content = Text()
        if self.logs:
            for i, log in enumerate(self.logs):
                # Alterna cores para visual retro
                color = STYLE_GRADIENT[i % len(STYLE_GRADIENT)]
                log_content.append(f"{log}\n", style=color)
        else:
            log_content.append("Aguardando eventos...", style="dim")
        
        layout["logs"].update(Panel(
            log_content,
            title="[bold white on red] 📜 LOGS [/bold white on red]",
            border_style="red",
            box=ROUNDED
        ))
        
        return layout
    
    def start(self):
        """Inicia o monitor"""
        webhook = CONFIG.get("webhook_url", "")
        server = CONFIG.get("server_link", "")
        
        if not webhook:
            rprint("[bold red]⚠️ Configure o Webhook primeiro![/bold red]")
            time.sleep(2)
            return
        
        # Força modo retrato
        force_portrait()
        
        self.running = True
        self.start_time = datetime.datetime.now()
        self.logs = []
        self.instances = {}
        
        # Obtém pacotes
        pkgs = get_packages()
        if not pkgs:
            rprint("[bold red]⚠️ Nenhum pacote Roblox encontrado![/bold red]")
            time.sleep(2)
            return
        
        self.log(f"🚀 Iniciando com {len(pkgs)} instâncias")
        
        # Cria instâncias e inicia workers
        for pkg in pkgs:
            inst = Instance(pkg, self)
            self.instances[pkg] = inst
            t = threading.Thread(target=self.monitor_worker, args=(inst,), daemon=True)
            t.start()
            self.log(f"+ {inst.name} monitorando")
        
        # Notifica início
        send_webhook(f"🚀 **RE_PHONE RETRO** iniciado!\n📊 Monitorando {len(pkgs)} instâncias")
        
        # Loop de renderização com Live
        try:
            with Live(self.render(), refresh_per_second=2, screen=True, console=console) as live:
                while self.running:
                    live.update(self.render())
                    time.sleep(0.5)
        except KeyboardInterrupt:
            self.running = False
            self.log("⏹️ Monitor encerrado pelo usuário")
            send_webhook("⏹️ **RE_PHONE RETRO** encerrado")
        
        rprint("\n[bold magenta]Monitor encerrado.[/bold magenta]")
        time.sleep(1)

# Instância global do monitor
monitor = RetroMonitor()

# ═══════════════════════════════════════════════════════════════════
# MENU PRINCIPAL
# ═══════════════════════════════════════════════════════════════════
def show_banner():
    """Mostra banner com gradiente"""
    banner = """[bold red]
    ██████╗ ███████╗[/bold red][bold bright_red]      ██████╗ ██╗  ██╗[/bold bright_red][bold magenta] ██████╗ ███╗   ██╗[/bold magenta][bold bright_magenta]███████╗[/bold bright_magenta]
    [bold red]██╔══██╗██╔════╝[/bold red][bold bright_red]      ██╔══██╗██║  ██║[/bold bright_red][bold magenta]██╔═══██╗████╗  ██║[/bold magenta][bold bright_magenta]██╔════╝[/bold bright_magenta]
    [bold red]██████╔╝█████╗  [/bold red][bold bright_red]█████╗██████╔╝███████║[/bold bright_red][bold magenta]██║   ██║██╔██╗ ██║[/bold magenta][bold bright_magenta]█████╗  [/bold bright_magenta]
    [bold red]██╔══██╗██╔══╝  [/bold red][bold bright_red]╚════╝██╔═══╝ ██╔══██║[/bold bright_red][bold magenta]██║   ██║██║╚██╗██║[/bold magenta][bold bright_magenta]██╔══╝  [/bold bright_magenta]
    [bold red]██║  ██║███████╗[/bold red][bold bright_red]      ██║     ██║  ██║[/bold bright_red][bold magenta]╚██████╔╝██║ ╚████║[/bold magenta][bold bright_magenta]███████╗[/bold bright_magenta]
    [bold red]╚═╝  ╚═╝╚══════╝[/bold red][bold bright_red]      ╚═╝     ╚═╝  ╚═╝[/bold bright_red][bold magenta] ╚═════╝ ╚═╝  ╚═══╝[/bold magenta][bold bright_magenta]╚══════╝[/bold bright_magenta]
    [bright_magenta]                    ✧ RETRO EDITION v2.0 ✧[/bright_magenta]
    [dim white]              Synthwave Monitor for VSPhone[/dim white]"""
    rprint(Align.center(banner))

def main_menu():
    """Menu principal"""
    while True:
        console.clear()
        show_banner()
        
        # Status
        webhook_ok = "✓ Configurado" if CONFIG.get("webhook_url") else "✗ Pendente"
        server_ok = "✓ Configurado" if CONFIG.get("server_link") else "✗ Pendente"
        
        webhook_style = "green" if "✓" in webhook_ok else "red"
        server_style = "green" if "✓" in server_ok else "red"
        
        status_panel = Panel(
            f"[bright_magenta]Webhook:[/bright_magenta] [{webhook_style}]{webhook_ok}[/{webhook_style}]    "
            f"[bright_magenta]Server:[/bright_magenta] [{server_style}]{server_ok}[/{server_style}]",
            border_style="magenta",
            box=ROUNDED
        )
        rprint(status_panel)
        
        # Menu grid
        menu = Table.grid(expand=True, padding=1)
        menu.add_column(ratio=1)
        menu.add_column(ratio=1)
        
        menu.add_row(
            Panel(
                "[bold white][1] 🚀 INICIAR MONITOR[/bold white]\n[dim]Monitoramento em tempo real[/dim]",
                border_style="red",
                box=ROUNDED
            ),
            Panel(
                "[bold white][2] 🔗 CONFIGURAR WEBHOOK[/bold white]\n[dim]Discord/Slack webhook[/dim]",
                border_style="bright_red",
                box=ROUNDED
            )
        )
        menu.add_row(
            Panel(
                "[bold white][3] 🌐 LINK DO SERVIDOR[/bold white]\n[dim]VIP/Private server[/dim]",
                border_style="magenta",
                box=ROUNDED
            ),
            Panel(
                "[bold white][4] 📸 TESTAR WEBHOOK[/bold white]\n[dim]Enviar screenshot teste[/dim]",
                border_style="bright_magenta",
                box=ROUNDED
            )
        )
        menu.add_row(
            Panel(
                "[bold white][5] 🛠️ FERRAMENTAS[/bold white]\n[dim]Utilitários extras[/dim]",
                border_style="bright_magenta",
                box=ROUNDED
            ),
            Panel(
                "[bold white][0] ❌ SAIR[/bold white]",
                border_style="dark_red",
                box=ROUNDED
            )
        )
        
        rprint(menu)
        
        choice = Prompt.ask(
            "\n[bold bright_magenta]Selecione[/bold bright_magenta]",
            choices=["1", "2", "3", "4", "5", "0"],
            default="1"
        )
        
        if choice == "1":
            monitor.start()
        
        elif choice == "2":
            console.clear()
            show_banner()
            rprint(Panel("[bold]🔗 CONFIGURAR WEBHOOK[/bold]", border_style="magenta"))
            rprint(f"\n[dim]Atual: {CONFIG.get('webhook_url', 'Não configurado')[:50]}...[/dim]\n")
            webhook = Prompt.ask("[bright_magenta]Cole o URL do Webhook[/bright_magenta]")
            if webhook.strip():
                CONFIG["webhook_url"] = webhook.strip()
                save_config(CONFIG)
                rprint("[green]✓ Webhook salvo![/green]")
            time.sleep(1)
        
        elif choice == "3":
            console.clear()
            show_banner()
            rprint(Panel("[bold]🌐 LINK DO SERVIDOR[/bold]", border_style="magenta"))
            rprint(f"\n[dim]Atual: {CONFIG.get('server_link', 'Não configurado')[:50]}...[/dim]\n")
            link = Prompt.ask("[bright_magenta]Cole o Link do Servidor (VIP)[/bright_magenta]")
            if link.strip():
                CONFIG["server_link"] = link.strip()
                save_config(CONFIG)
                rprint("[green]✓ Link salvo![/green]")
            time.sleep(1)
        
        elif choice == "4":
            console.clear()
            show_banner()
            rprint(Panel("[bold]📸 TESTAR WEBHOOK[/bold]", border_style="magenta"))
            
            webhook = CONFIG.get("webhook_url", "")
            if not webhook:
                rprint("[red]⚠️ Configure o webhook primeiro![/red]")
            else:
                rprint("[yellow]Capturando screenshot...[/yellow]")
                screenshot = take_screenshot()
                
                if screenshot:
                    rprint("[yellow]Enviando para webhook...[/yellow]")
                    if send_webhook("🧪 **Teste de Screenshot**\nSe você está vendo isso, funcionou! 🌸", screenshot):
                        rprint("[green]✓ Screenshot enviado com sucesso![/green]")
                    else:
                        rprint("[red]✗ Falha ao enviar[/red]")
                else:
                    rprint("[red]✗ Falha ao capturar screenshot[/red]")
            
            Prompt.ask("\n[dim]Pressione Enter para continuar[/dim]")
        
        elif choice == "5":
            tools_menu()
        
        elif choice == "0":
            rprint("\n[bright_magenta]Até mais! ✧[/bright_magenta]\n")
            break

def tools_menu():
    """Menu de ferramentas"""
    console.clear()
    show_banner()
    rprint(Panel("[bold]🛠️ FERRAMENTAS[/bold]", border_style="magenta"))
    
    rprint("[1] 📱 Forçar Modo Retrato")
    rprint("[2] ⏹️ Parar Todos os Roblox")
    rprint("[3] 📋 Listar Pacotes")
    rprint("[4] 🔄 Reiniciar Todos")
    rprint("[0] ↩️ Voltar")
    
    opt = Prompt.ask("\n[bright_magenta]Opção[/bright_magenta]", choices=["1", "2", "3", "4", "0"])
    
    if opt == "1":
        force_portrait()
        rprint("[green]✓ Modo retrato ativado![/green]")
        time.sleep(1)
    
    elif opt == "2":
        pkgs = get_packages()
        for pkg in pkgs:
            stop_app(pkg)
            name = pkg.split('.')[-1].upper()
            rprint(f"[red]✗ {name} parado[/red]")
        time.sleep(1)
    
    elif opt == "3":
        pkgs = get_packages()
        rprint(f"\n[bright_magenta]Pacotes encontrados ({len(pkgs)}):[/bright_magenta]")
        for i, pkg in enumerate(pkgs, 1):
            pid = get_pid(pkg)
            cpu = get_cpu(pid) if pid else 0
            name = pkg.split('.')[-1].upper()
            status = f"[green]Rodando (CPU: {cpu:.1f}%)[/green]" if pid else "[red]Parado[/red]"
            rprint(f"  {i}. [bold]{name}[/bold] - {status}")
        Prompt.ask("\n[dim]Enter para voltar[/dim]")
    
    elif opt == "4":
        pkgs = get_packages()
        link = CONFIG.get("server_link", "")
        for pkg in pkgs:
            stop_app(pkg)
            time.sleep(0.5)
            start_app(pkg, link)
            name = pkg.split('.')[-1].upper()
            rprint(f"[green]✓ {name} reiniciado[/green]")
            time.sleep(1)
        time.sleep(1)

if __name__ == "__main__":
    main_menu()
