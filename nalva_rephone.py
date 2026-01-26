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
from rich.progress import BarColumn, Progress, TextColumn, SpinnerColumn
from rich.box import DOUBLE, ROUNDED, HEAVY
from rich.columns import Columns
from rich import print as rprint

# Configurações Globais
console = Console()
CONFIG_FILE = "config.json"
CHECK_INTERVAL = 2  # Reduzido de 4 para 2 segundos para updates mais rápidos
COOLDOWN_TIME = 150
FAST_UPDATE_MODE = True  # Modo de atualização rápida

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
    """Vigilante individual otimizado com cache inteligente"""
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

    def run_adb(self, command, cache_key=None, cache_time=1):
        """Executa comando ADB com sistema de cache opcional"""
        now = time.time()
        
        # Verifica cache se habilitado
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
                timeout=2  # Timeout reduzido
            )
            output = result.stdout.strip()
            
            # Atualiza cache
            if cache_key:
                self.update_cache[cache_key] = (now, output)
            
            return output
        except:
            return ""

    def update(self):
        """Atualização otimizada com processamento paralelo de dados"""
        now = time.time()
        
        # 1. PID Check (sem cache - crítico)
        new_pid = self.run_adb(f"pidof {self.package}")
        
        with self.lock:
            self.pid = new_pid
            if not self.pid:
                self.cpu = 0.0
                self.mem_mb = 0.0
                self.net_kb = 0.0
                self.status = "OFFLINE"
                self.color = "red"
                self.last_update = now
                return

            # 2. CPU e Memory Check (otimizado)
            top = self.run_adb(f"top -n 1 -p {self.pid} | grep {self.pid}")
            if top:
                try:
                    parts = top.split()
                    # CPU
                    for i, p in enumerate(parts):
                        if "%" in p: 
                            self.cpu = float(p.replace("%", "").replace(",", "."))
                            break
                    # Memória (geralmente está em MB ou KB)
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

            # 3. Network Check (UID) - com cache de 2s para UID
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

    def monitor(self):
        """Loop de monitoramento com intervalo adaptativo"""
        while self.is_running and self.manager.global_running:
            self.update()
            
            if time.time() > self.cooldown_until:
                # Ação isolada - Só mexe neste pacote
                if not self.pid:
                    self.reboot("Process Lost")
                elif self.cpu < 5.0 and self.net_kb < 0.5:
                    self.error_count += 1
                    if self.error_count >= 10:  # Reduzido para resposta mais rápida
                        self.reboot("System Freeze")
                else:
                    # Verificação de UI (Link Break) - apenas a cada 4 ciclos
                    if self.error_count % 4 == 0 and self.error_count > 0:
                        ui = self.run_adb("uiautomator dump /sdcard/view.xml > /dev/null 2>&1 && cat /sdcard/view.xml").lower()
                        if any(x in ui for x in ["disconnected", "desconectado", "reconnect", "erro", "error"]):
                            self.reboot("Connection Lost")
            
            time.sleep(CHECK_INTERVAL)

    def reboot(self, reason):
        """Reinicialização com contadores e logs melhorados"""
        self.restart_count += 1
        self.manager.add_log(f"🔄 {self.package.split('.')[-1].upper()}: {reason} (#{self.restart_count})", "bold red")
        self.manager.send_webhook(f"🚨 **RE_PHONE v7**: `{self.package}` → `{reason}` (Restart #{self.restart_count})")
        
        self.run_adb(f"am force-stop {self.package}")
        time.sleep(2)
        self.run_adb(f"am start -a android.intent.action.VIEW -d '{VIP_LINK}' {self.package}")
        
        self.cooldown_until = time.time() + COOLDOWN_TIME
        self.error_count = 0
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
        if len(self.logs) > 15:  # Aumentado de 10 para 15
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
        
        # Busca pacotes Roblox
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
        
        with Live(self.make_layout(), refresh_per_second=2, screen=True) as live:  # Aumentado de 4 para 2 FPS
            try:
                while self.global_running:
                    live.update(self.make_layout())
                    time.sleep(0.5)  # Atualização visual mais suave
            except KeyboardInterrupt:
                self.global_running = False
                self.add_log("⚠️ System shutdown requested", "bold yellow")

    def make_layout(self):
        """Layout melhorado com mais informações e estética aprimorada"""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=5),
            Layout(name="stats", size=3),
            Layout(name="main", ratio=2),
            Layout(name="footer", size=12)
        )
        
        # ═══════════════════════════════════════════════════════════
        # HEADER - Banner Cyber Aprimorado
        # ═══════════════════════════════════════════════════════════
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        header_text = Text.assemble(
            ("  RE_PHONE  ", "bold black on bright_cyan"),
            (" v7.0 ", "bold bright_cyan on black"),
            (" CYBER ULTRA ", "bold cyan on black"),
            ("  by MSA  ", "italic bright_white on black"),
            f"\n{now}", "dim white"
        )
        layout["header"].update(
            Panel(
                Align.center(header_text), 
                border_style="bright_cyan",
                box=DOUBLE,
                subtitle="[dim italic]Next-Gen Multi-Instance Isolation System[/dim italic]"
            )
        )
        
        # ═══════════════════════════════════════════════════════════
        # STATS - Estatísticas Globais
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
            f"[bold green]✓ ACTIVE: {active}[/bold green]",
            f"[bold red]✗ OFFLINE: {offline}[/bold red]",
            f"[bold yellow]🔄 REBOOTS: {total_reboots}[/bold yellow]",
            f"[bold cyan]⏱ UPTIME: {runtime_str}[/bold cyan]"
        )
        
        layout["stats"].update(Panel(stats_table, border_style="bright_black", box=ROUNDED))
        
        # ═══════════════════════════════════════════════════════════
        # MAIN - Tabela de Instâncias Aprimorada
        # ═══════════════════════════════════════════════════════════
        table = Table(
            expand=True, 
            border_style="bright_black", 
            box=HEAVY,
            show_header=True,
            header_style="bold bright_white on grey23"
        )
        
        table.add_column("INSTANCE", style="bold white", width=18, no_wrap=True)
        table.add_column("CPU", justify="center", width=18)
        table.add_column("MEM", justify="center", width=12)
        table.add_column("NET", justify="center", width=14)
        table.add_column("UPTIME", justify="center", width=12)
        table.add_column("STATUS", justify="center", width=15)
        
        for p, v in sorted(self.vigilantes.items()):
            name = p.split('.')[-1].upper()[:15]
            
            with v.lock:
                cpu, mem, net = v.cpu, v.mem_mb, v.net_kb
                status, color = v.status, v.color
                uptime = v.get_uptime()
                restart_count = v.restart_count
            
            # Progress bar para CPU com gradiente
            if cpu > 50:
                cpu_color = "red"
            elif cpu > 20:
                cpu_color = "yellow"
            else:
                cpu_color = "green"
                
            cpu_bar = Progress(
                BarColumn(bar_width=8, complete_style=cpu_color, finished_style=cpu_color),
                TextColumn(f"[bold {cpu_color}]{cpu:5.1f}%[/]")
            )
            cpu_bar.add_task("", total=100, completed=min(cpu, 100))
            
            # Nome com ícone de status
            status_icon = "●" if status == "ACTIVE" else "○"
            instance_name = f"[{color}]{status_icon}[/] {name}"
            
            # Restarts badge
            if restart_count > 0:
                instance_name += f" [dim]({restart_count})[/dim]"
            
            table.add_row(
                instance_name,
                cpu_bar,
                f"[bold magenta]{mem:.0f}MB[/]" if mem > 0 else "[dim]--[/dim]",
                f"[bold cyan]{net:6.1f}KB/s[/]" if net > 0 else "[dim]0.0 KB/s[/dim]",
                f"[bold white]{uptime}[/]",
                f"[bold {color}]{status:^13}[/]"
            )
        
        layout["main"].update(
            Panel(
                table, 
                title="[bold bright_cyan]━━━ SYSTEM CORE MONITORING ━━━[/bold bright_cyan]",
                border_style="bright_cyan",
                box=DOUBLE
            )
        )
        
        # ═══════════════════════════════════════════════════════════
        # FOOTER - Logs Aprimorados
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
                subtitle=f"[dim]Last update: {datetime.datetime.now().strftime('%H:%M:%S')}[/dim]"
            )
        )
        
        return layout

manager = CyberManager()

def main():
    global VIP_LINK, WEBHOOK_URL
    
    while True:
        console.clear()
        
        # Banner ASCII Art melhorado
        banner = """[bold bright_cyan]
╔══════════════════════════════════════════════════════════════════════════╗
║   ██████╗ ███████╗     ██████╗ ██╗  ██╗ ██████╗ ███╗   ██╗███████╗     ║
║   ██╔══██╗██╔════╝     ██╔══██╗██║  ██║██╔═══██╗████╗  ██║██╔════╝     ║
║   ██████╔╝█████╗       ██████╔╝███████║██║   ██║██╔██╗ ██║█████╗       ║
║   ██╔══██╗██╔══╝       ██╔═══╝ ██╔══██║██║   ██║██║╚██╗██║██╔══╝       ║
║   ██║  ██║███████╗     ██║     ██║  ██║╚██████╔╝██║ ╚████║███████╗     ║
║   ╚═╝  ╚═╝╚══════╝     ╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝     ║
╚══════════════════════════════════════════════════════════════════════════╝[/bold bright_cyan]
[italic bright_white]                 v7.0 CYBER ULTRA - Next-Gen Isolation by MSA[/italic bright_white]"""
        
        rprint(banner)
        
        # Status configuração com ícones
        vip_status = "[bold green]✓ CONFIGURED[/bold green]" if VIP_LINK else "[bold red]✗ NOT SET[/bold red]"
        webhook_status = "[bold green]✓ ACTIVE[/bold green]" if WEBHOOK_URL else "[bold yellow]⚠ INACTIVE[/bold yellow]"
        
        status_grid = Table.grid(expand=True, padding=1)
        status_grid.add_column(justify="center", ratio=1)
        status_grid.add_column(justify="center", ratio=1)
        status_grid.add_row(
            f"📡 VIP Link: {vip_status}",
            f"⚓ Webhook: {webhook_status}"
        )
        
        rprint(Panel(status_grid, border_style="bright_black", box=ROUNDED))
        
        # Menu aprimorado
        menu = Table.grid(expand=True, padding=1)
        menu.add_column(ratio=1)
        menu.add_column(ratio=1)
        
        menu.add_row(
            Panel(
                "[bold bright_cyan]⚡ [1] START CYBER HUD[/bold bright_cyan]\n[dim]Launch monitoring system[/dim]",
                border_style="bright_cyan",
                box=ROUNDED
            ),
            Panel(
                "[bold bright_magenta]⚙️ [2] SETTINGS[/bold bright_magenta]\n[dim]Configure VIP link & webhook[/dim]",
                border_style="bright_magenta",
                box=ROUNDED
            )
        )
        menu.add_row(
            Panel(
                "[bold bright_blue]🛠️ [3] SYSTEM TOOLS[/bold bright_blue]\n[dim]Auto-setup & utilities[/dim]",
                border_style="bright_blue",
                box=ROUNDED
            ),
            Panel(
                "[bold bright_red]❌ [0] EXIT[/bold bright_red]\n[dim]Shutdown system[/dim]",
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
            console.clear()
            rprint(Panel(
                "[bold bright_magenta]NEURAL SETTINGS CONFIGURATION[/bold bright_magenta]",
                border_style="bright_magenta",
                box=DOUBLE
            ))
            
            VIP_LINK = Prompt.ask(
                "[cyan]VIP Link[/cyan]",
                default=VIP_LINK if VIP_LINK else "https://"
            )
            WEBHOOK_URL = Prompt.ask(
                "[cyan]Webhook URL[/cyan]",
                default=WEBHOOK_URL if WEBHOOK_URL else "https://discord.com/api/webhooks/..."
            )
            
            save_config({"vip_link": VIP_LINK, "webhook_url": WEBHOOK_URL})
            rprint("\n[bold green]✓ Configuration saved successfully![/bold green]")
            time.sleep(1.5)
            
        elif choice == "3":
            console.clear()
            rprint(Panel(
                "[bold bright_blue]SYSTEM TOOLS & UTILITIES[/bold bright_blue]",
                border_style="bright_blue",
                box=DOUBLE
            ))
            
            tools_menu = """[cyan][1][/cyan] Run Auto-Setup Script
[cyan][2][/cyan] Force Stop All Instances
[cyan][3][/cyan] Clear ADB Cache
[cyan][0][/cyan] Back to Main Menu"""
            
            rprint(Panel(tools_menu, border_style="bright_black"))
            
            sub = Prompt.ask("[bold]Select tool[/bold]", choices=["1", "2", "3", "0"])
            
            if sub == "1":
                rprint("[yellow]Running setup.sh...[/yellow]")
                subprocess.run("bash setup.sh", shell=True)
                Prompt.ask("\n[green]Setup complete! Press Enter to continue[/green]")
                
            elif sub == "2":
                rprint("[yellow]Stopping all Roblox instances...[/yellow]")
                out = subprocess.run("adb shell pm list packages roblox", shell=True, capture_output=True, text=True).stdout
                pkgs = [l.replace("package:", "").strip() for l in out.splitlines() if "roblox" in l]
                
                for p in pkgs:
                    subprocess.run(f"adb shell am force-stop {p}", shell=True)
                    rprint(f"[red]✓[/red] Stopped: {p}")
                
                rprint("\n[bold green]All instances terminated![/bold green]")
                time.sleep(2)
                
            elif sub == "3":
                rprint("[yellow]Clearing ADB server cache...[/yellow]")
                subprocess.run("adb kill-server && adb start-server", shell=True)
                rprint("[bold green]✓ ADB cache cleared![/bold green]")
                time.sleep(1.5)
                
        elif choice == "0":
            rprint("\n[bold bright_cyan]Shutting down RE_PHONE v7.0...[/bold bright_cyan]")
            time.sleep(1)
            break

if __name__ == "__main__":
    main()
