#!/usr/bin/env python3
"""
RE_PHONE v10.0 by MSA
Sistema Profissional de Monitoramento para Roblox

Funcionalidades:
- Detecção de estado via CPU, RAM e Threads (sem uiautomator)
- Inicialização limpa: abre todos, espera, depois envia links
- Isolamento total: cada instância é independente
- Notificações via Discord Webhook
- Interface profissional com Rich

Autor: MSA
"""

import os
import sys
import json
import time
import subprocess
import threading
import re
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import requests

# Rich para interface bonita
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt
    from rich.live import Live
    from rich.text import Text
    from rich.align import Align
    from rich.box import ROUNDED, DOUBLE
    from rich import print as rprint
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Instalando rich...")
    os.system("pip install rich")
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt
    from rich.live import Live
    from rich.text import Text
    from rich.align import Align
    from rich.box import ROUNDED, DOUBLE
    from rich import print as rprint

console = Console()

# ═══════════════════════════════════════════════════════════════════
# ESTADOS E CONFIGURAÇÕES
# ═══════════════════════════════════════════════════════════════════

class RobloxState(Enum):
    """Estados possíveis do Roblox"""
    CLOSED = "Fechado"
    HOME = "Tela Inicial"
    LOADING = "Carregando"
    IN_GAME = "Em Jogo"
    UNKNOWN = "Desconhecido"


@dataclass
class MonitorConfig:
    """Configuração do monitor"""
    webhook_url: str = ""
    server_link: str = ""
    check_interval: int = 3
    enable_notifications: bool = True
    
    # Thresholds para detecção de estado (baseado em CPU/RAM)
    cpu_in_game_min: float = 25.0    # CPU > 15% = Em jogo
    cpu_loading_min: float = 5.0       # CPU 5-15% = Carregando
    cpu_idle_max: float = 3.0          # CPU < 3% = Parado
    ram_in_game_min: int = 400         # RAM > 400MB = Em jogo
    ram_home_typical: int = 200        # RAM ~200MB = Home


CONFIG_FILE = "monitor_config.json"


def load_config() -> MonitorConfig:
    """Carrega configuração do arquivo"""
    if Path(CONFIG_FILE).exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return MonitorConfig(**data)
        except Exception:
            pass
    return MonitorConfig()


def save_config(config: MonitorConfig) -> bool:
    """Salva configuração no arquivo"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(asdict(config), f, indent=4, ensure_ascii=False)
        return True
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════
# UTILITÁRIOS ADB
# ═══════════════════════════════════════════════════════════════════

def adb(command: str, timeout: int = 5) -> str:
    """Executa comando ADB e retorna output"""
    try:
        result = subprocess.run(
            f"adb shell {command}",
            shell=True,
            capture_output=True,
            timeout=timeout,
            text=True
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return ""
    except Exception:
        return ""


def adb_check_connection() -> bool:
    """Verifica se há dispositivo conectado"""
    try:
        result = subprocess.run(
            "adb devices",
            shell=True,
            capture_output=True,
            timeout=3,
            text=True
        )
        lines = result.stdout.strip().split('\n')
        return len(lines) > 1 and 'device' in lines[1]
    except:
        return False


def get_packages() -> List[str]:
    """Retorna lista de pacotes Roblox instalados"""
    output = adb("pm list packages")
    packages = []
    for line in output.split('\n'):
        if 'roblox' in line.lower():
            pkg = line.replace('package:', '').strip()
            if pkg:
                packages.append(pkg)
    return packages


def get_pid(package: str) -> str:
    """Retorna PID do pacote"""
    return adb(f"pidof {package}")


def get_cpu(pid: str) -> float:
    """Obtém uso de CPU de um processo"""
    if not pid:
        return 0.0
    top_output = adb(f"top -n 1 -p {pid} | grep {pid}")
    if top_output:
        for part in top_output.split():
            if '%' in part:
                try:
                    return float(part.replace('%', '').replace(',', '.'))
                except:
                    pass
    return 0.0


def get_ram(pid: str) -> int:
    """Obtém uso de RAM em MB de um processo"""
    if not pid:
        return 0
    mem_output = adb(f"dumpsys meminfo {pid} | grep 'TOTAL'")
    match = re.search(r'TOTAL\s+(\d+)', mem_output)
    if match:
        return int(match.group(1)) // 1024  # KB para MB
    return 0


def get_threads(pid: str) -> int:
    """Obtém número de threads de um processo"""
    if not pid:
        return 0
    status = adb(f"cat /proc/{pid}/status | grep Threads")
    match = re.search(r'Threads:\s+(\d+)', status)
    if match:
        return int(match.group(1))
    return 0


def stop_app(package: str):
    """Para um app completamente"""
    adb(f"am force-stop {package}")


def start_app(package: str):
    """Inicia um app (apenas abre, sem link)"""
    activity = f"{package}/com.roblox.client.startup.ActivitySplash"
    adb(f"am start -n {activity}")


def start_app_with_link(package: str, link: str):
    """Inicia um app com um link VIP"""
    activity = f"{package}/com.roblox.client.ActivityProtocolLaunch"
    adb(f"am start -n {activity} -a android.intent.action.VIEW -d '{link}'")


def force_portrait():
    """Força o modo retrato"""
    adb("settings put system accelerometer_rotation 0")
    adb("settings put system user_rotation 0")


def capture_screenshot(output_path: str = "/tmp/roblox_screenshot.png") -> bool:
    """Captura screenshot do dispositivo"""
    try:
        adb("screencap -p /sdcard/temp_screen.png")
        time.sleep(0.3)
        result = subprocess.run(
            f"adb pull /sdcard/temp_screen.png {output_path}",
            shell=True,
            capture_output=True,
            timeout=10
        )
        adb("rm /sdcard/temp_screen.png")
        return result.returncode == 0 and Path(output_path).exists()
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════
# DETECTOR DE ESTADO (SEM UIAUTOMATOR)
# ═══════════════════════════════════════════════════════════════════

def detect_state(cpu: float, ram: int, config: MonitorConfig) -> RobloxState:
    """
    Detecta o estado do Roblox baseado APENAS em CPU e RAM.
    Sem uiautomator ou detecção de tela.
    """
    # Sem processo = Fechado
    if cpu == 0 and ram == 0:
        return RobloxState.CLOSED
    
    # CPU alta + RAM alta = Em jogo
    if cpu >= config.cpu_in_game_min and ram >= config.ram_in_game_min:
        return RobloxState.IN_GAME
    
    # CPU média = Carregando
    if cpu >= config.cpu_loading_min:
        return RobloxState.LOADING
    
    # CPU muito baixa + RAM baixa = Home ou parado
    if cpu <= config.cpu_idle_max:
        if ram < config.ram_home_typical:
            return RobloxState.HOME
        return RobloxState.UNKNOWN
    
    # RAM típica de home
    if ram >= config.ram_home_typical and ram < config.ram_in_game_min:
        return RobloxState.HOME
    
    return RobloxState.UNKNOWN


# ═══════════════════════════════════════════════════════════════════
# NOTIFICADOR DISCORD
# ═══════════════════════════════════════════════════════════════════

def send_webhook(webhook_url: str, message: str, screenshot: bool = False) -> bool:
    """Envia mensagem para Discord webhook"""
    if not webhook_url:
        return False
    
    try:
        screenshot_path = None
        files = None
        
        if screenshot:
            screenshot_path = f"/tmp/screenshot_{int(time.time())}.png"
            if capture_screenshot(screenshot_path):
                with open(screenshot_path, 'rb') as f:
                    files = {"file": ("screenshot.png", f.read(), "image/png")}
        
        payload = {"content": message}
        
        if files:
            response = requests.post(
                webhook_url,
                data={"payload_json": json.dumps(payload)},
                files=files,
                timeout=10
            )
        else:
            response = requests.post(webhook_url, json=payload, timeout=10)
        
        # Limpa screenshot
        if screenshot_path and Path(screenshot_path).exists():
            try:
                os.remove(screenshot_path)
            except:
                pass
        
        return response.status_code in [200, 204]
    
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════
# INSTÂNCIA DE MONITORAMENTO
# ═══════════════════════════════════════════════════════════════════

class RobloxInstance:
    """Representa uma instância do Roblox sendo monitorada"""
    
    def __init__(self, package: str, config: MonitorConfig):
        self.package = package
        self.name = package.split('.')[-1].upper()
        self.config = config
        
        # Métricas
        self.pid = ""
        self.cpu = 0.0
        self.ram = 0
        self.threads = 0
        
        # Estado
        self.state = RobloxState.UNKNOWN
        self.previous_state = RobloxState.UNKNOWN
        self.state_changes = 0
        self.last_update = datetime.now()
        
        # Controle
        self.lock = threading.Lock()
        self.running = False
        self.cooldown_until = 0
        self.last_event = ""
    
    def update_metrics(self):
        """Atualiza métricas do processo"""
        with self.lock:
            self.pid = get_pid(self.package)
            
            if self.pid:
                self.cpu = get_cpu(self.pid)
                self.ram = get_ram(self.pid)
                self.threads = get_threads(self.pid)
            else:
                self.cpu = 0.0
                self.ram = 0
                self.threads = 0
            
            # Detecta estado
            new_state = detect_state(self.cpu, self.ram, self.config)
            
            if new_state != self.state:
                self.previous_state = self.state
                self.state = new_state
                self.state_changes += 1
            
            self.last_update = datetime.now()
    
    def restart(self, reason: str, link: str, webhook_url: str):
        """Reinicia APENAS esta instância"""
        with self.lock:
            self.last_event = reason
            self.cooldown_until = time.time() + 120  # 2 min cooldown
        
        # Notifica
        send_webhook(webhook_url, f"🔄 **{self.name}**: {reason}", screenshot=True)
        
        # Reinicia
        stop_app(self.package)
        time.sleep(1)
        start_app_with_link(self.package, link)


# ═══════════════════════════════════════════════════════════════════
# MONITOR PRINCIPAL
# ═══════════════════════════════════════════════════════════════════

class RobloxMonitor:
    """Monitor principal que gerencia todas as instâncias"""
    
    def __init__(self):
        self.config = load_config()
        self.instances: Dict[str, RobloxInstance] = {}
        self.running = False
        self.logs: List[str] = []
    
    def log(self, msg: str):
        """Adiciona mensagem ao log"""
        t = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{t}] {msg}")
        if len(self.logs) > 15:
            self.logs.pop(0)
    
    def initialize_clean(self):
        """
        Inicialização limpa:
        1. Fecha todos os Roblox
        2. Abre cada um (só abre, sem link)
        3. Espera 5 segundos
        4. Envia o link VIP em cada um
        """
        pkgs = get_packages()
        if not pkgs:
            rprint("[bold red]Nenhum pacote Roblox encontrado![/bold red]")
            return False
        
        link = self.config.server_link
        if not link:
            rprint("[bold red]Configure o Server Link primeiro![/bold red]")
            return False
        
        rprint("\n[bold yellow]═══ INICIALIZAÇÃO LIMPA ═══[/bold yellow]\n")
        
        # Passo 1: Fecha todos
        rprint("[red]Fechando todos os Roblox...[/red]")
        for pkg in pkgs:
            stop_app(pkg)
            name = pkg.split('.')[-1].upper()
            rprint(f"  [dim]✗ {name}[/dim]")
            time.sleep(0.3)
        time.sleep(1)
        
        # Passo 2: Abre cada um (só abre)
        rprint("\n[cyan]Abrindo cada instância...[/cyan]")
        for pkg in pkgs:
            name = pkg.split('.')[-1].upper()
            start_app(pkg)
            rprint(f"  [green]✓ {name} aberto[/green]")
            time.sleep(1)
        
        # Passo 3: Espera 5 segundos
        rprint("\n[yellow]Aguardando 5 segundos...[/yellow]")
        time.sleep(5)
        
        # Passo 4: Envia o link VIP em cada um
        rprint("\n[magenta]Enviando link VIP...[/magenta]")
        for pkg in pkgs:
            name = pkg.split('.')[-1].upper()
            start_app_with_link(pkg, link)
            rprint(f"  [green]✓ {name} -> VIP enviado[/green]")
            time.sleep(1)
        
        rprint("\n[bold green]═══ INICIALIZAÇÃO COMPLETA ═══[/bold green]")
        time.sleep(2)
        
        return True
    
    def monitor_worker(self, inst: RobloxInstance):
        """Worker de monitoramento para uma instância"""
        while self.running and inst.package in self.instances:
            inst.update_metrics()
            
            # Verifica se precisa reiniciar (apenas esta instância)
            if time.time() >= inst.cooldown_until:
                with inst.lock:
                    state = inst.state
                    cpu = inst.cpu
                
                # Se fechou, reinicia
                if state == RobloxState.CLOSED:
                    self.log(f"💀 {inst.name}: Fechado, reiniciando...")
                    inst.restart("Processo fechado", self.config.server_link, self.config.webhook_url)
                
                # Se está na Home por muito tempo, reinicia
                elif state == RobloxState.HOME and cpu < 3:
                    self.log(f"🏠 {inst.name}: Na Home, reiniciando...")
                    inst.restart("Tela inicial", self.config.server_link, self.config.webhook_url)
            
            time.sleep(self.config.check_interval)
    
    def start(self):
        """Inicia o monitor"""
        if not adb_check_connection():
            rprint("[bold red]Nenhum dispositivo ADB conectado![/bold red]")
            time.sleep(2)
            return
        
        force_portrait()
        
        # Inicialização limpa
        if not self.initialize_clean():
            return
        
        self.running = True
        self.logs = []
        self.log("Monitor iniciado")
        
        # Cria instâncias
        pkgs = get_packages()
        for pkg in pkgs:
            inst = RobloxInstance(pkg, self.config)
            inst.cooldown_until = time.time() + 60  # 1 min cooldown inicial
            self.instances[pkg] = inst
            
            # Inicia worker
            threading.Thread(target=self.monitor_worker, args=(inst,), daemon=True).start()
            self.log(f"+ {inst.name} monitorando")
        
        # Notifica início
        send_webhook(
            self.config.webhook_url,
            f"🚀 **RE_PHONE Monitor Iniciado**\nMonitorando {len(pkgs)} instância(s)"
        )
        
        # Loop de renderização
        with Live(self.render(), refresh_per_second=2, screen=True) as live:
            try:
                while self.running:
                    live.update(self.render())
                    time.sleep(0.5)
            except KeyboardInterrupt:
                self.running = False
        
        # Notifica parada
        send_webhook(self.config.webhook_url, "⏹️ **RE_PHONE Monitor Parado**")
    
    def render(self):
        """Renderiza o HUD"""
        # Header
        header = Text()
        header.append("╔══════════════════════════════════════════════════════════╗\n", style="bright_red")
        header.append("║              ", style="bright_red")
        header.append("RE_PHONE", style="bold white on red")
        header.append("  v10.0  ", style="bold bright_red")
        header.append("by MSA", style="italic white")
        header.append("              ║\n", style="bright_red")
        header.append("╚══════════════════════════════════════════════════════════╝", style="bright_red")
        
        # Tabela de instâncias
        table = Table(box=ROUNDED, border_style="bright_red", expand=True,
                     show_header=True, header_style="bold white on red")
        table.add_column("INSTÂNCIA", justify="left", style="bold", width=12)
        table.add_column("CPU", justify="center", width=8)
        table.add_column("RAM", justify="center", width=10)
        table.add_column("THREADS", justify="center", width=8)
        table.add_column("ESTADO", justify="center", width=14)
        
        state_icons = {
            RobloxState.IN_GAME: ("🎮", "green"),
            RobloxState.LOADING: ("⏳", "yellow"),
            RobloxState.HOME: ("🏠", "blue"),
            RobloxState.CLOSED: ("❌", "red"),
            RobloxState.UNKNOWN: ("❓", "dim"),
        }
        
        for pkg, inst in self.instances.items():
            with inst.lock:
                cpu = inst.cpu
                ram = inst.ram
                threads = inst.threads
                state = inst.state
                name = inst.name
            
            # Formatação de CPU
            if cpu >= 15:
                cpu_txt = f"[green]{cpu:.1f}%[/green]"
            elif cpu >= 5:
                cpu_txt = f"[yellow]{cpu:.1f}%[/yellow]"
            else:
                cpu_txt = f"[red]{cpu:.1f}%[/red]"
            
            # Formatação de RAM
            if ram >= 400:
                ram_txt = f"[green]{ram} MB[/green]"
            elif ram >= 200:
                ram_txt = f"[yellow]{ram} MB[/yellow]"
            else:
                ram_txt = f"[red]{ram} MB[/red]"
            
            # Estado
            icon, color = state_icons.get(state, ("❓", "dim"))
            state_txt = f"[{color}]{icon} {state.value}[/{color}]"
            
            table.add_row(name, cpu_txt, ram_txt, str(threads), state_txt)
        
        # Logs
        logs_text = "\n".join(self.logs[-10:]) if self.logs else "[dim]Aguardando eventos...[/dim]"
        logs_panel = Panel(logs_text, title="[bold red]LOGS[/bold red]", border_style="red")
        
        # Layout final
        from rich.layout import Layout
        layout = Layout()
        layout.split_column(
            Layout(Align.center(header), size=5),
            Layout(table, size=12),
            Layout(logs_panel, size=12)
        )
        
        return layout


# ═══════════════════════════════════════════════════════════════════
# INTERFACE DE LINHA DE COMANDO
# ═══════════════════════════════════════════════════════════════════

def clear_screen():
    os.system('clear' if os.name == 'posix' else 'cls')


def print_header():
    clear_screen()
    rprint("[bold red]╔════════════════════════════════════════════════════════════╗[/bold red]")
    rprint("[bold red]║[/bold red]              [bold white on red]RE_PHONE[/bold white on red]  [bold red]v10.0[/bold red]  [italic]by MSA[/italic]              [bold red]║[/bold red]")
    rprint("[bold red]╚════════════════════════════════════════════════════════════╝[/bold red]")
    rprint()


def main_menu():
    config = load_config()
    monitor = RobloxMonitor()
    
    while True:
        print_header()
        
        # Status
        webhook_status = "✅" if config.webhook_url else "❌"
        server_status = "✅" if config.server_link else "❌"
        
        rprint(f"  Webhook: {webhook_status}  |  Server Link: {server_status}")
        rprint()
        rprint("  [bold red]┌────────────────────────────────────────────────────┐[/bold red]")
        rprint("  [bold red]│[/bold red]  [bold][1][/bold] 🚀 Iniciar Monitor                            [bold red]│[/bold red]")
        rprint("  [bold red]│[/bold red]  [bold][2][/bold] ⚙️  Configurações                              [bold red]│[/bold red]")
        rprint("  [bold red]│[/bold red]  [bold][3][/bold] 📸 Testar Screenshot                          [bold red]│[/bold red]")
        rprint("  [bold red]│[/bold red]  [bold][4][/bold] 📋 Ver Pacotes Instalados                     [bold red]│[/bold red]")
        rprint("  [bold red]│[/bold red]  [bold][0][/bold] ❌ Sair                                        [bold red]│[/bold red]")
        rprint("  [bold red]└────────────────────────────────────────────────────┘[/bold red]")
        rprint()
        
        choice = Prompt.ask("  Selecione", choices=["0", "1", "2", "3", "4"], default="1")
        
        if choice == "1":
            monitor.config = config
            monitor.start()
        elif choice == "2":
            config = configure_menu(config)
        elif choice == "3":
            test_screenshot(config)
        elif choice == "4":
            show_packages()
        elif choice == "0":
            rprint("\n  [bold]👋 Até logo![/bold]\n")
            break


def configure_menu(config: MonitorConfig) -> MonitorConfig:
    while True:
        print_header()
        
        rprint("  [bold red]⚙️  CONFIGURAÇÕES[/bold red]")
        rprint("  " + "─" * 56)
        rprint(f"  Webhook URL: {config.webhook_url[:40] + '...' if len(config.webhook_url) > 40 else config.webhook_url or 'Não configurado'}")
        rprint(f"  Server Link: {config.server_link[:40] + '...' if len(config.server_link) > 40 else config.server_link or 'Não configurado'}")
        rprint(f"  Intervalo: {config.check_interval}s")
        rprint("  " + "─" * 56)
        rprint()
        rprint("  [1] Configurar Webhook URL")
        rprint("  [2] Configurar Server Link")
        rprint("  [3] Ajustar Intervalo")
        rprint("  [0] Voltar")
        rprint()
        
        choice = Prompt.ask("  Selecione", choices=["0", "1", "2", "3"], default="0")
        
        if choice == "1":
            webhook = Prompt.ask("\n  Cole o Webhook URL")
            if webhook:
                config.webhook_url = webhook
                save_config(config)
                rprint("  [green]✅ Webhook salvo![/green]")
                time.sleep(1)
        
        elif choice == "2":
            server = Prompt.ask("\n  Cole o Server Link")
            if server:
                config.server_link = server
                save_config(config)
                rprint("  [green]✅ Server link salvo![/green]")
                time.sleep(1)
        
        elif choice == "3":
            try:
                interval = int(Prompt.ask("\n  Intervalo em segundos", default="3"))
                if 1 <= interval <= 60:
                    config.check_interval = interval
                    save_config(config)
                    rprint("  [green]✅ Intervalo atualizado![/green]")
                else:
                    rprint("  [yellow]⚠️ Valor deve estar entre 1 e 60[/yellow]")
                time.sleep(1)
            except:
                rprint("  [yellow]⚠️ Valor inválido![/yellow]")
                time.sleep(1)
        
        elif choice == "0":
            break
    
    return config


def test_screenshot(config: MonitorConfig):
    print_header()
    rprint("  [bold]📸 TESTE DE SCREENSHOT[/bold]\n")
    
    if not config.webhook_url:
        rprint("  [yellow]⚠️ Configure o webhook primeiro![/yellow]")
        Prompt.ask("\n  Pressione Enter para continuar")
        return
    
    rprint("  Capturando screenshot...")
    screenshot_path = "/tmp/test_screenshot.png"
    
    if capture_screenshot(screenshot_path):
        rprint("  [green]✅ Screenshot capturado![/green]")
        rprint("  Enviando para webhook...")
        
        if send_webhook(config.webhook_url, "🧪 **Teste de Screenshot**", screenshot=False):
            # Envia com arquivo
            try:
                with open(screenshot_path, 'rb') as f:
                    files = {"file": ("screenshot.png", f.read(), "image/png")}
                    requests.post(
                        config.webhook_url,
                        data={"payload_json": json.dumps({"content": "📸 Screenshot de teste"})},
                        files=files,
                        timeout=10
                    )
                rprint("  [green]✅ Screenshot enviado com sucesso![/green]")
            except:
                rprint("  [red]❌ Falha ao enviar screenshot[/red]")
        else:
            rprint("  [red]❌ Falha ao enviar para webhook[/red]")
        
        try:
            os.remove(screenshot_path)
        except:
            pass
    else:
        rprint("  [red]❌ Falha ao capturar screenshot[/red]")
    
    Prompt.ask("\n  Pressione Enter para continuar")


def show_packages():
    print_header()
    rprint("  [bold]📋 PACOTES ROBLOX INSTALADOS[/bold]\n")
    
    if not adb_check_connection():
        rprint("  [red]❌ Nenhum dispositivo ADB conectado![/red]")
        Prompt.ask("\n  Pressione Enter para continuar")
        return
    
    pkgs = get_packages()
    
    if not pkgs:
        rprint("  [yellow]⚠️ Nenhum pacote Roblox encontrado[/yellow]")
    else:
        for i, pkg in enumerate(pkgs, 1):
            name = pkg.split('.')[-1].upper()
            pid = get_pid(pkg)
            status = "[green]Rodando[/green]" if pid else "[red]Parado[/red]"
            rprint(f"  {i}. {name} ({pkg}) - {status}")
    
    Prompt.ask("\n  Pressione Enter para continuar")


# ═══════════════════════════════════════════════════════════════════
# PONTO DE ENTRADA
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        rprint("\n\n  [bold]👋 Programa encerrado pelo usuário[/bold]\n")
    except Exception as e:
        rprint(f"\n  [red]❌ Erro fatal: {e}[/red]\n")
