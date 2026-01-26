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
from rich.prompt import Prompt, Confirm
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.align import Align
from rich.progress import BarColumn, Progress, TextColumn
from rich.box import DOUBLE, ROUNDED, HEAVY, SIMPLE
from rich.style import Style
from rich import print as rprint

# Configurações Globais
console = Console()
CONFIG_FILE = "config.json"
CHECK_INTERVAL = 1.5  # Intervalo super rápido
COOLDOWN_TIME = 120
APP_CHECK_INTERVAL = 0.5  # Verificação de app em foreground muito rápida

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except: 
            pass
    return {"vip_link": "", "webhook_url": ""}

def save_config(config_data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f, indent=4)

_config = load_config()
VIP_LINK = _config.get("vip_link", "")
WEBHOOK_URL = _config.get("webhook_url", "")

class InstanceVigilante:
    """Vigilante ultra-rápido com detecção de foreground"""
    def __init__(self, package, manager):
        self.package = package
        self.manager = manager
        self.pid = None
        self.cpu = 0.0
        self.mem_mb = 0.0
        self.net_kb = 0.0
        self.last_bytes = 0
        self.status = "INITIALIZING"
        self.color = "cyan"
        self.error_count = 0
        self.cooldown_until = time.time() + 10
        self.is_running = True
        self.lock = threading.Lock()
        self.last_update = 0
        self.update_cache = {}
        self.uptime_start = time.time()
        self.restart_count = 0
        self.is_foreground = False
        self.home_count = 0

    def run_adb(self, command, cache_key=None, cache_time=1):
        """Executa comando ADB com sistema de cache opcional"""
        now = time.time()
        
        if cache_key and cache_key in self.update_cache:
            cached_time, cached_value = self.update_cache[cache_key]
            if now - cached_time < cache_time:
                return cached_value
        
        try:
            result = subprocess.run(
                f"adb shell {command}", 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=1.5
            )
            output = result.stdout.strip()
            
            if cache_key:
                self.update_cache[cache_key] = (now, output)
            
            return output
        except:
            return ""

    def check_foreground(self):
        """Verifica se o app está em foreground rapidamente"""
        try:
            # Método rápido: dumpsys window
            window = self.run_adb("dumpsys window windows | grep -E 'mCurrentFocus|mFocusedApp'")
            
            if self.package in window:
                self.is_foreground = True
                self.home_count = 0
                return True
            else:
                self.is_foreground = False
                self.home_count += 1
                return False
        except:
            return False

    def update(self):
        """Atualização ultra-otimizada"""
        now = time.time()
        
        # 1. PID Check
        new_pid = self.run_adb(f"pidof {self.package}")
        
        with self.lock:
            # Se perdeu PID
            if not new_pid and self.pid:
                self.manager.add_log(f"⚠️ {self.package.split('.')[-1].upper()}: App crashed/closed", "bold red")
                self.pid = None
                self.cpu = 0.0
                self.mem_mb = 0.0
                self.net_kb = 0.0
                self.status = "CRASHED"
                self.color = "red"
                self.last_update = now
                
                # Reboot imediato se não está em cooldown
                if time.time() > self.cooldown_until:
                    threading.Thread(target=lambda: self.reboot("App Closed"), daemon=True).start()
                return
            
            self.pid = new_pid
            if not self.pid:
                self.cpu = 0.0
                self.mem_mb = 0.0
                self.net_kb = 0.0
                self.status = "OFFLINE"
                self.color = "red"
                self.last_update = now
                return

            # 2. CPU e Memory Check
            top = self.run_adb(f"top -n 1 -p {self.pid} | grep {self.pid}")
            if top:
                try:
                    parts = top.split()
                    for i, p in enumerate(parts):
                        if "%" in p: 
                            self.cpu = float(p.replace("%", "").replace(",", "."))
                            break
                    for i, p in enumerate(parts):
                        if 'M' in p or 'K' in p:
                            try:
                                if 'M' in p:
                                    self.mem_mb = float(p.replace('M', ''))
                                elif 'K' in p:
                                    self.mem_mb = float(p.replace('K', '')) / 1024
                            except:
                                pass
                except:
                    pass

            # 3. Network Check
            uid_out = self.run_adb(
                f"dumpsys package {self.package} | grep userId=", 
                cache_key=f"uid_{self.package}",
                cache_time=2
            )
            if uid_out:
                try:
                    uid = uid_out.split('=')[1].split()[0]
                    net = self.run_adb(f"cat /proc/net/xt_qtaguid/stats | grep {uid}")
                    if net:
                        curr = sum(int(l.split()[5]) for l in net.splitlines() if len(l.split()) > 5)
                        if self.last_bytes > 0:
                            delta_time = now - self.last_update if self.last_update > 0 else CHECK_INTERVAL
                            self.net_kb = (curr - self.last_bytes) / 1024 / delta_time
                        self.last_bytes = curr
                except:
                    pass

            # 4. Status Logic Aprimorado
            if time.time() < self.cooldown_until:
                self.status = "STABILIZING"
                self.color = "blue"
            elif not self.is_foreground and self.home_count > 2:
                self.status = "BACKGROUND"
                self.color = "yellow"
            elif self.cpu > 15.0:
                self.status = "ACTIVE"
                self.color = "green"
                self.error_count = 0
            elif self.cpu > 5.0:
                self.status = "IDLE"
                self.color = "yellow"
            else:
                self.status = "STUCK"
                self.color = "red"
            
            self.last_update = now

    def monitor_app_state(self):
        """Monitor dedicado para estado do app (foreground/background)"""
        while self.is_running and self.manager.global_running:
            if self.pid and time.time() > self.cooldown_until:
                is_fg = self.check_foreground()
                
                # Se está em background/home por mais de 3 verificações (1.5s)
                if not is_fg and self.home_count > 3:
                    self.manager.add_log(f"🏠 {self.package.split('.')[-1].upper()}: Detected in background/home", "bold yellow")
                    self.reboot("App in Background")
            
            time.sleep(APP_CHECK_INTERVAL)

    def monitor(self):
        """Loop principal de monitoramento"""
        # Inicia monitor de foreground em thread separada
        threading.Thread(target=self.monitor_app_state, daemon=True).start()
        
        while self.is_running and self.manager.global_running:
            self.update()
            
            if time.time() > self.cooldown_until:
                if not self.pid:
                    # Já foi tratado no update()
                    pass
                elif self.cpu < 5.0 and self.net_kb < 0.5:
                    self.error_count += 1
                    if self.error_count >= 8:  # ~12 segundos
                        self.reboot("System Freeze")
                else:
                    # Verificação de UI
                    if self.error_count % 4 == 0 and self.error_count > 0:
                        ui = self.run_adb("uiautomator dump /sdcard/view.xml > /dev/null 2>&1 && cat /sdcard/view.xml").lower()
                        if any(x in ui for x in ["disconnected", "desconectado", "reconnect", "erro", "error"]):
                            self.reboot("Connection Lost")
            
            time.sleep(CHECK_INTERVAL)

    def reboot(self, reason):
        """Reinicialização ultra-rápida"""
        self.restart_count += 1
        self.manager.add_log(f"🔄 {self.package.split('.')[-1].upper()}: {reason} (#{self.restart_count})", "bold red")
        self.manager.send_webhook(f"🚨 **RE_PHONE v7**: `{self.package}` → `{reason}` (Restart #{self.restart_count})")
        
        # Force stop rápido
        self.run_adb(f"am force-stop {self.package}")
        time.sleep(1)  # Reduzido de 2 para 1 segundo
        
        # Restart imediato
        self.run_adb(f"am start -a android.intent.action.VIEW -d '{VIP_LINK}' {self.package}")
        
        # Força trazer para foreground
        time.sleep(0.5)
        self.run_adb(f"am start {self.package}")
        
        self.cooldown_until = time.time() + COOLDOWN_TIME
        self.error_count = 0
        self.home_count = 0
        self.uptime_start = time.time()

    def get_uptime(self):
        """Retorna tempo de atividade formatado"""
        if not self.pid:
            return "00:00:00"
        uptime_sec = int(time.time() - self.uptime_start)
        hours = uptime_sec // 3600
        minutes = (uptime_sec % 3600) // 60
        seconds = uptime_sec % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

class CyberManager:
    def __init__(self):
        self.vigilantes = {}
        self.global_running = False
        self.logs = []
        self.stats = {
            "total_reboots": 0,
            "start_time": None,
            "active_count": 0,
            "offline_count": 0
        }

    def add_log(self, msg, style="white"):
        t = datetime.datetime.now().strftime("%H:%M:%S")
        self.logs.append((f"[{t}] {msg}", style))
        if len(self.logs) > 15:
            self.logs.pop(0)

    def send_webhook(self, msg):
        if WEBHOOK_URL:
            try:
                requests.post(WEBHOOK_URL, json={"content": msg}, timeout=5)
            except:
                pass

    def start(self):
        if not VIP_LINK:
            rprint("[red]❌ VIP LINK REQUIRED[/red]")
            time.sleep(2)
            return
        
        self.global_running = True
        self.stats["start_time"] = time.time()
        
        out = subprocess.run("adb shell pm list packages roblox", shell=True, capture_output=True, text=True).stdout
        pkgs = [l.replace("package:", "").strip() for l in out.splitlines() if "roblox" in l]
        
        if not pkgs:
            rprint("[red]❌ No Roblox packages found[/red]")
            time.sleep(2)
            return
        
        self.add_log(f"🚀 System initialized with {len(pkgs)} instances", "bold green")
        
        for p in pkgs:
            v = InstanceVigilante(p, self)
            self.vigilantes[p] = v
            threading.Thread(target=v.monitor, daemon=True).start()
        
        with Live(self.make_layout(), refresh_per_second=3, screen=True) as live:
            try:
                while self.global_running:
                    live.update(self.make_layout())
                    time.sleep(0.33)
            except KeyboardInterrupt:
                self.global_running = False
                self.add_log("⚠️ System shutdown requested", "bold yellow")

    def make_layout(self):
        """Layout com gradientes e design moderno"""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=6),
            Layout(name="stats", size=3),
            Layout(name="main", ratio=2),
            Layout(name="footer", size=12)
        )
        
        # ═══════════════════════════════════════════════════════════
        # HEADER - Banner Gradiente
        # ═══════════════════════════════════════════════════════════
        now = datetime.datetime.now().strftime("%H:%M:%S")
        
        # Texto com gradiente simulado usando cores progressivas
        header_lines = [
            Text("█ ", style="cyan") + Text("R E _ P H O N E ", style="bold bright_cyan") + Text(" █", style="cyan"),
            Text("▓ ", style="bright_cyan") + Text("v 7 . 0   U L T R A ", style="bold white") + Text(" ▓", style="bright_cyan"),
            Text("▒ ", style="white") + Text("C Y B E R   E D I T I O N ", style="italic bright_white") + Text(" ▒", style="white"),
            Text(f"░ {now} ░", style="dim white")
        ]
        
        header_content = Text()
        for line in header_lines:
            header_content.append("                    ")
            header_content.append(line)
            header_content.append("\n")
        
        layout["header"].update(
            Panel(
                Align.center(header_content), 
                border_style="bright_cyan",
                box=DOUBLE,
                subtitle="[dim italic]by MSA - Next-Gen Multi-Instance System[/dim italic]"
            )
        )
        
        # ═══════════════════════════════════════════════════════════
        # STATS - Com gradiente de cores
        # ═══════════════════════════════════════════════════════════
        active = sum(1 for v in self.vigilantes.values() if v.status == "ACTIVE")
        offline = sum(1 for v in self.vigilantes.values() if v.status == "OFFLINE")
        total_reboots = sum(v.restart_count for v in self.vigilantes.values())
        
        if self.stats["start_time"]:
            runtime = int(time.time() - self.stats["start_time"])
            runtime_str = f"{runtime//3600:02d}:{(runtime%3600)//60:02d}:{runtime%60:02d}"
        else:
            runtime_str = "00:00:00"
        
        stats_table = Table.grid(expand=True, padding=(0, 2))
        stats_table.add_column(justify="center", ratio=1)
        stats_table.add_column(justify="center", ratio=1)
        stats_table.add_column(justify="center", ratio=1)
        stats_table.add_column(justify="center", ratio=1)
        
        stats_table.add_row(
            f"[bold green on grey15] ✓ ACTIVE: {active} [/]",
            f"[bold red on grey15] ✗ OFFLINE: {offline} [/]",
            f"[bold yellow on grey15] 🔄 REBOOTS: {total_reboots} [/]",
            f"[bold cyan on grey15] ⏱ UPTIME: {runtime_str} [/]"
        )
        
        layout["stats"].update(Panel(stats_table, border_style="bright_black", box=SIMPLE))
        
        # ═══════════════════════════════════════════════════════════
        # MAIN - Tabela com gradiente de status
        # ═══════════════════════════════════════════════════════════
        table = Table(
            expand=True, 
            border_style="bright_cyan", 
            box=HEAVY,
            show_header=True,
            header_style="bold bright_white on grey23"
        )
        
        table.add_column("INSTANCE", style="bold white", width=20, no_wrap=True)
        table.add_column("CPU", justify="center", width=18)
        table.add_column("MEM", justify="center", width=12)
        table.add_column("NET", justify="center", width=14)
        table.add_column("UPTIME", justify="center", width=12)
        table.add_column("STATUS", justify="center", width=18)
        
        for p, v in sorted(self.vigilantes.items()):
            name = p.split('.')[-1].upper()[:15]
            
            with v.lock:
                cpu, mem, net = v.cpu, v.mem_mb, v.net_kb
                status, color = v.status, v.color
                uptime = v.get_uptime()
                restart_count = v.restart_count
                is_fg = v.is_foreground
            
            # Progress bar gradiente para CPU
            if cpu > 70:
                cpu_color = "bright_red"
            elif cpu > 50:
                cpu_color = "red"
            elif cpu > 30:
                cpu_color = "yellow"
            elif cpu > 15:
                cpu_color = "green"
            else:
                cpu_color = "bright_black"
                
            cpu_bar = Progress(
                BarColumn(bar_width=8, complete_style=cpu_color, finished_style=cpu_color),
                TextColumn(f"[bold {cpu_color}]{cpu:5.1f}%[/]")
            )
            cpu_bar.add_task("", total=100, completed=min(cpu, 100))
            
            # Status com gradiente e ícones
            if status == "ACTIVE":
                status_display = f"[bold green on grey15] ● {status} [/]"
            elif status == "OFFLINE" or status == "CRASHED":
                status_display = f"[bold red on grey15] ✗ {status} [/]"
            elif status == "BACKGROUND":
                status_display = f"[bold yellow on grey15] ◐ {status} [/]"
            elif status == "STABILIZING":
                status_display = f"[bold blue on grey15] ◌ {status} [/]"
            else:
                status_display = f"[bold {color} on grey15] ○ {status} [/]"
            
            # Nome com badge de foreground
            fg_badge = "[green]▲[/]" if is_fg else "[dim]▼[/]"
            instance_name = f"{fg_badge} {name}"
            
            if restart_count > 0:
                instance_name += f" [dim red]({restart_count})[/]"
            
            table.add_row(
                instance_name,
                cpu_bar,
                f"[bold magenta]{mem:.0f}MB[/]" if mem > 0 else "[dim]--[/dim]",
                f"[bold cyan]{net:6.1f}KB/s[/]" if net > 0 else "[dim]0.0 KB/s[/dim]",
                f"[bold white]{uptime}[/]",
                status_display
            )
        
        layout["main"].update(
            Panel(
                table, 
                title="[bold bright_cyan]━━━ REAL-TIME SYSTEM MONITORING ━━━[/bold bright_cyan]",
                border_style="bright_cyan",
                box=DOUBLE,
                subtitle="[dim]▲ Foreground | ▼ Background[/dim]"
            )
        )
        
        # ═══════════════════════════════════════════════════════════
        # FOOTER - Logs com gradiente
        # ═══════════════════════════════════════════════════════════
        log_content = Text()
        for msg, style in self.logs:
            log_content.append(msg + "\n", style=style)
        
        layout["footer"].update(
            Panel(
                log_content,
                title="[bold yellow]━━━ NEURAL ACTIVITY LOGS ━━━[/bold yellow]",
                border_style="yellow",
                box=DOUBLE,
                subtitle=f"[dim]Last update: {datetime.datetime.now().strftime('%H:%M:%S')} | Monitoring: {len(self.vigilantes)} instances[/dim]"
            )
        )
        
        return layout

manager = CyberManager()

def configure_links():
    """Interface intuitiva para configuração de links"""
    global VIP_LINK, WEBHOOK_URL
    
    console.clear()
    
    # Banner de configuração
    config_banner = Text()
    config_banner.append("╔══════════════════════════════════════════════╗\n", style="bright_magenta")
    config_banner.append("║        ", style="bright_magenta")
    config_banner.append("⚙️  CONFIGURATION PANEL  ⚙️", style="bold bright_white")
    config_banner.append("         ║\n", style="bright_magenta")
    config_banner.append("╚══════════════════════════════════════════════╝", style="bright_magenta")
    
    rprint(Align.center(config_banner))
    rprint()
    
    # Status atual
    current_status = Table.grid(expand=True, padding=1)
    current_status.add_column(style="dim", ratio=1)
    current_status.add_column(style="bold", ratio=2)
    
    current_status.add_row(
        "📡 VIP Link:",
        f"[green]{VIP_LINK[:50]}...[/]" if VIP_LINK else "[red]Not configured[/]"
    )
    current_status.add_row(
        "⚓ Webhook:",
        f"[green]{WEBHOOK_URL[:50]}...[/]" if WEBHOOK_URL else "[yellow]Not configured (optional)[/]"
    )
    
    rprint(Panel(current_status, title="[bold]Current Configuration[/bold]", border_style="bright_black"))
    rprint()
    
    # Menu de opções
    rprint("[bold bright_cyan]What would you like to configure?[/bold bright_cyan]\n")
    rprint("[cyan][1][/cyan] Set VIP Link (Required)")
    rprint("[cyan][2][/cyan] Set Discord Webhook (Optional)")
    rprint("[cyan][3][/cyan] Configure Both")
    rprint("[cyan][4][/cyan] Test Current Configuration")
    rprint("[cyan][0][/cyan] Back to Main Menu")
    rprint()
    
    choice = Prompt.ask("[bold]Select option[/bold]", choices=["1", "2", "3", "4", "0"], default="1")
    
    if choice in ["1", "3"]:
        rprint("\n[bold bright_cyan]═══ VIP LINK CONFIGURATION ═══[/bold bright_cyan]")
        rprint("[dim]This is the link that will open in Roblox instances[/dim]\n")
        
        new_vip = Prompt.ask(
            "[cyan]Enter VIP Link[/cyan]",
            default=VIP_LINK if VIP_LINK else ""
        )
        
        if new_vip and new_vip.strip():
            VIP_LINK = new_vip.strip()
            rprint("[green]✓ VIP Link saved successfully![/green]")
        else:
            rprint("[yellow]⚠ VIP Link was not changed[/yellow]")
        
        time.sleep(1)
    
    if choice in ["2", "3"]:
        rprint("\n[bold bright_cyan]═══ WEBHOOK CONFIGURATION ═══[/bold bright_cyan]")
        rprint("[dim]Discord webhook for notifications (optional)[/dim]\n")
        
        new_webhook = Prompt.ask(
            "[cyan]Enter Webhook URL[/cyan]",
            default=WEBHOOK_URL if WEBHOOK_URL else ""
        )
        
        if new_webhook and new_webhook.strip():
            WEBHOOK_URL = new_webhook.strip()
            rprint("[green]✓ Webhook saved successfully![/green]")
            
            # Teste do webhook
            if Confirm.ask("[yellow]Would you like to send a test message?[/yellow]", default=False):
                try:
                    requests.post(WEBHOOK_URL, json={"content": "✅ RE_PHONE v7.0 - Webhook test successful!"}, timeout=5)
                    rprint("[green]✓ Test message sent![/green]")
                except:
                    rprint("[red]✗ Failed to send test message. Check your webhook URL.[/red]")
        else:
            rprint("[yellow]⚠ Webhook was not changed[/yellow]")
        
        time.sleep(1)
    
    if choice == "4":
        rprint("\n[bold bright_cyan]═══ TESTING CONFIGURATION ═══[/bold bright_cyan]\n")
        
        # Testa VIP Link
        if VIP_LINK:
            rprint("[green]✓[/green] VIP Link is configured")
            rprint(f"  [dim]{VIP_LINK[:60]}...[/dim]")
        else:
            rprint("[red]✗[/red] VIP Link is NOT configured")
        
        rprint()
        
        # Testa Webhook
        if WEBHOOK_URL:
            rprint("[green]✓[/green] Webhook is configured")
            if Confirm.ask("[yellow]Send test message?[/yellow]", default=True):
                try:
                    requests.post(WEBHOOK_URL, json={"content": "✅ RE_PHONE v7.0 - Configuration test"}, timeout=5)
                    rprint("[green]✓ Test message sent successfully![/green]")
                except:
                    rprint("[red]✗ Failed to send test message[/red]")
        else:
            rprint("[yellow]⚠[/yellow] Webhook is not configured (optional)")
        
        rprint()
        Prompt.ask("[dim]Press Enter to continue[/dim]")
    
    # Salva configurações
    if choice in ["1", "2", "3"]:
        save_config({"vip_link": VIP_LINK, "webhook_url": WEBHOOK_URL})
        rprint("\n[bold green]✓ All changes saved to config.json[/bold green]")
        time.sleep(1.5)

def main():
    global VIP_LINK, WEBHOOK_URL
    
    while True:
        console.clear()
        
        # Banner principal com gradiente
        banner_lines = [
            ("█████╗ ", "bright_cyan"),
            ("██╔══██╗", "bright_cyan"),
            ("███████║", "cyan"),
            ("██╔══██║", "cyan"),
            ("██║  ██║", "white"),
            ("╚═╝  ╚═╝", "white"),
        ]
        
        title_lines = [
            "██████╗ ███████╗    ██████╗ ██╗  ██╗ ██████╗ ███╗   ██╗███████╗",
            "██╔══██╗██╔════╝    ██╔══██╗██║  ██║██╔═══██╗████╗  ██║██╔════╝",
            "██████╔╝█████╗      ██████╔╝███████║██║   ██║██╔██╗ ██║█████╗  ",
            "██╔══██╗██╔══╝      ██╔═══╝ ██╔══██║██║   ██║██║╚██╗██║██╔══╝  ",
            "██║  ██║███████╗    ██║     ██║  ██║╚██████╔╝██║ ╚████║███████╗",
            "╚═╝  ╚═╝╚══════╝    ╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝",
        ]
        
        banner_text = Text()
        for i, line in enumerate(title_lines):
            if i < 2:
                banner_text.append(line + "\n", style="bold bright_cyan")
            elif i < 4:
                banner_text.append(line + "\n", style="bold cyan")
            else:
                banner_text.append(line + "\n", style="bold white")
        
        banner_text.append("\n                v7.0 ULTRA - Cyber Edition by MSA", style="italic bright_white")
        
        rprint(Panel(Align.center(banner_text), border_style="bright_cyan", box=DOUBLE))
        
        # Status com indicadores visuais
        vip_icon = "✓" if VIP_LINK else "✗"
        vip_color = "green" if VIP_LINK else "red"
        webhook_icon = "✓" if WEBHOOK_URL else "⚠"
        webhook_color = "green" if WEBHOOK_URL else "yellow"
        
        status_grid = Table.grid(expand=True, padding=1)
        status_grid.add_column(justify="center", ratio=1)
        status_grid.add_column(justify="center", ratio=1)
        
        status_grid.add_row(
            f"[{vip_color}]📡 VIP Link: {vip_icon} {('READY' if VIP_LINK else 'NOT SET')}[/]",
            f"[{webhook_color}]⚓ Webhook: {webhook_icon} {('ACTIVE' if WEBHOOK_URL else 'INACTIVE')}[/]"
        )
        
        rprint(Panel(status_grid, border_style="bright_black", box=ROUNDED))
        
        # Menu principal com gradiente
        menu = Table.grid(expand=True, padding=1)
        menu.add_column(ratio=1)
        menu.add_column(ratio=1)
        
        menu.add_row(
            Panel(
                Text.assemble(
                    ("⚡ ", "bold yellow"),
                    ("[1] START MONITORING", "bold bright_cyan"),
                    ("\n", ""),
                    ("Launch real-time system", "dim")
                ),
                border_style="bright_cyan",
                box=ROUNDED
            ),
            Panel(
                Text.assemble(
                    ("⚙️ ", "bold yellow"),
                    ("[2] CONFIGURATION", "bold bright_magenta"),
                    ("\n", ""),
                    ("Setup links & webhooks", "dim")
                ),
                border_style="bright_magenta",
                box=ROUNDED
            )
        )
        menu.add_row(
            Panel(
                Text.assemble(
                    ("🛠️ ", "bold yellow"),
                    ("[3] SYSTEM TOOLS", "bold bright_blue"),
                    ("\n", ""),
                    ("Utilities & maintenance", "dim")
                ),
                border_style="bright_blue",
                box=ROUNDED
            ),
            Panel(
                Text.assemble(
                    ("❌ ", "bold yellow"),
                    ("[0] EXIT SYSTEM", "bold bright_red"),
                    ("\n", ""),
                    ("Shutdown RE_PHONE", "dim")
                ),
                border_style="bright_red",
                box=ROUNDED
            )
        )
        
        rprint(menu)
        
        choice = Prompt.ask(
            "\n[bold bright_white]╰─→ Select Protocol[/bold bright_white]",
            choices=["1", "2", "3", "0"],
            default="1"
        )
        
        if choice == "1":
            manager.start()
            
        elif choice == "2":
            configure_links()
            
        elif choice == "3":
            console.clear()
            rprint(Panel(
                "[bold bright_blue]🛠️ SYSTEM TOOLS & UTILITIES[/bold bright_blue]",
                border_style="bright_blue",
                box=DOUBLE
            ))
            
            tools_menu = Text()
            tools_menu.append("[1] ", style="cyan")
            tools_menu.append("Run Auto-Setup Script\n", style="white")
            tools_menu.append("[2] ", style="cyan")
            tools_menu.append("Force Stop All Instances\n", style="white")
            tools_menu.append("[3] ", style="cyan")
            tools_menu.append("Restart ADB Server\n", style="white")
            tools_menu.append("[4] ", style="cyan")
            tools_menu.append("Launch All Instances Now\n", style="white")
            tools_menu.append("[0] ", style="cyan")
            tools_menu.append("Back to Main Menu", style="white")
            
            rprint(Panel(tools_menu, border_style="bright_black"))
            
            sub = Prompt.ask("[bold]Select tool[/bold]", choices=["1", "2", "3", "4", "0"])
            
            if sub == "1":
                rprint("[yellow]⚙️ Running setup.sh...[/yellow]")
                subprocess.run("bash setup.sh", shell=True)
                Prompt.ask("\n[green]✓ Setup complete! Press Enter to continue[/green]")
                
            elif sub == "2":
                rprint("[yellow]⚠️ Stopping all Roblox instances...[/yellow]")
                out = subprocess.run("adb shell pm list packages roblox", shell=True, capture_output=True, text=True).stdout
                pkgs = [l.replace("package:", "").strip() for l in out.splitlines() if "roblox" in l]
                
                for p in pkgs:
                    subprocess.run(f"adb shell am force-stop {p}", shell=True)
                    rprint(f"[red]✓[/red] Stopped: {p.split('.')[-1]}")
                
                rprint("\n[bold green]✓ All instances terminated![/bold green]")
                time.sleep(2)
                
            elif sub == "3":
                rprint("[yellow]🔄 Restarting ADB server...[/yellow]")
                subprocess.run("adb kill-server", shell=True)
                time.sleep(1)
                subprocess.run("adb start-server", shell=True)
                rprint("[bold green]✓ ADB server restarted![/bold green]")
                time.sleep(1.5)
            
            elif sub == "4":
                if not VIP_LINK:
                    rprint("[red]✗ VIP Link not configured! Configure it first.[/red]")
                    time.sleep(2)
                else:
                    rprint("[yellow]🚀 Launching all instances...[/yellow]")
                    out = subprocess.run("adb shell pm list packages roblox", shell=True, capture_output=True, text=True).stdout
                    pkgs = [l.replace("package:", "").strip() for l in out.splitlines() if "roblox" in l]
                    
                    for p in pkgs:
                        subprocess.run(f"adb shell am start -a android.intent.action.VIEW -d '{VIP_LINK}' {p}", shell=True)
                        rprint(f"[green]✓[/green] Launched: {p.split('.')[-1]}")
                        time.sleep(0.5)
                    
                    rprint("\n[bold green]✓ All instances launched![/bold green]")
                    time.sleep(2)
                
        elif choice == "0":
            rprint("\n[bold bright_cyan]╔══════════════════════════════════════╗[/bold bright_cyan]")
            rprint("[bold bright_cyan]║  Shutting down RE_PHONE v7.0...   ║[/bold bright_cyan]")
            rprint("[bold bright_cyan]╚══════════════════════════════════════╝[/bold bright_cyan]")
            time.sleep(1)
            break

if __name__ == "__main__":
    main()
