#!/usr/bin/env python3
"""
RE_PHONE v8.1 by MSA
Sistema de Monitoramento e Automação para Roblox
Com Auto-Detect de Key do Delta
"""
import os
import subprocess
import time
import requests
import datetime
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
from rich.box import HEAVY, DOUBLE, ROUNDED
from rich import print as rprint

console = Console()
CONFIG_FILE = "config.json"

# ═══════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES
# ═══════════════════════════════════════════════════════════════════
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except: pass
    return {"vip_link": "", "webhook_url": "", "auto_key": True}

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=4)

CONFIG = load_config()

# ═══════════════════════════════════════════════════════════════════
# FUNÇÕES ADB OTIMIZADAS
# ═══════════════════════════════════════════════════════════════════
def adb(cmd, timeout=3):
    try:
        return subprocess.check_output(f"adb shell {cmd}", shell=True, stderr=subprocess.DEVNULL, timeout=timeout).decode().strip()
    except: return ""

def adb_tap(x, y):
    adb(f"input tap {x} {y}")

def adb_text(txt):
    safe_txt = txt.replace("'", "")
    adb(f"input text '{safe_txt}'")

def adb_keyevent(key):
    adb(f"input keyevent {key}")

def get_ui_xml():
    adb("uiautomator dump /sdcard/ui.xml > /dev/null 2>&1")
    return adb("cat /sdcard/ui.xml").lower()

def find_element_bounds(xml, text):
    pattern = rf'text="[^"]*{text.lower()}[^"]*"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
    match = re.search(pattern, xml, re.IGNORECASE)
    if match:
        x1, y1, x2, y2 = map(int, match.groups())
        return (x1 + x2) // 2, (y1 + y2) // 2
    return None

def click_element_by_text(text):
    xml = get_ui_xml()
    coords = find_element_bounds(xml, text)
    if coords:
        adb_tap(coords[0], coords[1])
        return True
    return False

def force_portrait():
    adb("settings put system accelerometer_rotation 0")
    adb("settings put system user_rotation 0")

def get_packages():
    out = adb("pm list packages roblox")
    return [l.replace("package:", "").strip() for l in out.splitlines() if "roblox" in l]

def get_pid(pkg):
    return adb(f"pidof {pkg}")

def get_cpu(pid):
    if not pid: return 0.0
    top = adb(f"top -n 1 -p {pid} | grep {pid}")
    if top:
        for p in top.split():
            if "%" in p:
                try: return float(p.replace("%", "").replace(",", "."))
                except: pass
    return 0.0

def stop_app(pkg):
    adb(f"am force-stop {pkg}")

def start_vip(pkg, link):
    adb(f"am start -a android.intent.action.VIEW -d '{link}' {pkg}")

def send_webhook(url, msg):
    if url:
        try: requests.post(url, json={"content": msg}, timeout=3)
        except: pass

# ═══════════════════════════════════════════════════════════════════
# CLASSE DE INSTÂNCIA ISOLADA
# ═══════════════════════════════════════════════════════════════════
class Instance:
    def __init__(self, pkg):
        self.pkg = pkg
        self.name = pkg.split('.')[-1].upper()
        self.pid = ""
        self.cpu = 0.0
        self.status = "INIT"
        self.last_event = "Starting..."
        self.errors = 0
        self.cooldown = 0
        self.active = True
        self.lock = threading.Lock()

    def update(self):
        with self.lock:
            self.pid = get_pid(self.pkg)
            self.cpu = get_cpu(self.pid) if self.pid else 0.0
            
            if time.time() < self.cooldown:
                self.status = "SYNC"
            elif not self.pid:
                self.status = "DEAD"
            elif self.cpu > 15:
                self.status = "OK"
                self.errors = 0
            else:
                self.status = "LOW"

    def should_restart(self):
        if time.time() < self.cooldown:
            return False
        if not self.pid:
            return True
        if self.cpu < 5:
            self.errors += 1
            if self.errors >= 10:
                return True
        return False

    def restart(self, reason, vip, webhook):
        with self.lock:
            self.last_event = reason
            self.errors = 0
            self.cooldown = time.time() + 120
        
        send_webhook(webhook, f"🔄 `{self.name}` -> {reason}")
        stop_app(self.pkg)
        time.sleep(1)
        start_vip(self.pkg, vip)

# ═══════════════════════════════════════════════════════════════════
# AUTO-DETECT E AUTOMAÇÃO DE KEY DO DELTA
# ═══════════════════════════════════════════════════════════════════
class KeyAutoDetect:
    """Sistema de detecção automática de tela de key"""
    def __init__(self, monitor):
        self.monitor = monitor
        self.running = False
        self.last_key_time = 0
        self.key_cooldown = 60  # Espera 60s entre tentativas de key

    def detect_key_screen(self, xml):
        """Detecta se a tela de key está visível"""
        key_indicators = [
            "get key", "receive key", "checkpoint", "key system",
            "obter key", "pegar key", "verificação", "linkvertise",
            "lootlink", "delta key"
        ]
        return any(ind in xml for ind in key_indicators)

    def process_key(self):
        """Processa automaticamente a key do Delta"""
        self.monitor.log("🔑 KEY DETECTADA - Iniciando bypass...")
        send_webhook(CONFIG.get("webhook_url", ""), "🔑 **RE_PHONE**: Key do Delta detectada, iniciando bypass...")

        # Passo 1: Clicar no botão de key
        buttons = ["get key", "receive key", "checkpoint", "obter key", "pegar key", "continue"]
        for btn in buttons:
            if click_element_by_text(btn):
                self.monitor.log(f"✓ Clicou: {btn}")
                break
        
        time.sleep(4)

        # Passo 2: Verificar se abriu página de verificação
        xml = get_ui_xml()
        if "continue" in xml or "proceed" in xml or "prosseguir" in xml:
            for btn in ["continue", "proceed", "prosseguir", "next", "verificar"]:
                if click_element_by_text(btn):
                    self.monitor.log(f"✓ Verificação: {btn}")
                    break
            time.sleep(5)

        # Passo 3: Tentar pegar a key
        xml = get_ui_xml()
        if "copy" in xml or "copiar" in xml:
            for btn in ["copy", "copiar", "copy key"]:
                if click_element_by_text(btn):
                    self.monitor.log("✓ Key copiada!")
                    break
            
            time.sleep(2)
            adb_keyevent(4)  # Back
            time.sleep(1)
            adb_keyevent(279)  # Paste
            
            for btn in ["play", "execute", "continuar", "confirm", "submit"]:
                if click_element_by_text(btn):
                    self.monitor.log(f"✓ Finalizado: {btn}")
                    break

        self.last_key_time = time.time()
        send_webhook(CONFIG.get("webhook_url", ""), "✅ **RE_PHONE**: Bypass de key concluído!")

    def worker(self):
        """Thread de monitoramento contínuo para detectar key"""
        while self.running:
            if CONFIG.get("auto_key", True):
                # Só verifica se passou o cooldown
                if time.time() - self.last_key_time > self.key_cooldown:
                    try:
                        xml = get_ui_xml()
                        if self.detect_key_screen(xml):
                            self.process_key()
                    except: pass
            time.sleep(5)  # Verifica a cada 5 segundos

    def start(self):
        self.running = True
        threading.Thread(target=self.worker, daemon=True).start()

    def stop(self):
        self.running = False

# ═══════════════════════════════════════════════════════════════════
# MONITOR PRINCIPAL
# ═══════════════════════════════════════════════════════════════════
class Monitor:
    def __init__(self):
        self.instances = {}
        self.running = False
        self.logs = []
        self.key_detector = KeyAutoDetect(self)

    def log(self, msg):
        t = datetime.datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{t}] {msg}")
        if len(self.logs) > 6: self.logs.pop(0)

    def worker(self, inst):
        while self.running and inst.active:
            inst.update()
            if inst.should_restart():
                reason = "Process Dead" if not inst.pid else "Low Activity"
                inst.restart(reason, CONFIG.get("vip_link", ""), CONFIG.get("webhook_url", ""))
                self.log(f"{inst.name}: {reason}")
            time.sleep(3)

    def start(self):
        vip = CONFIG.get("vip_link", "")
        if not vip:
            rprint("[bold red]Configure o VIP Link primeiro![/bold red]")
            time.sleep(2)
            return

        force_portrait()
        self.running = True
        pkgs = get_packages()
        
        if not pkgs:
            rprint("[bold red]Nenhum pacote Roblox encontrado![/bold red]")
            time.sleep(2)
            return

        for p in pkgs:
            inst = Instance(p)
            self.instances[p] = inst
            threading.Thread(target=self.worker, args=(inst,), daemon=True).start()

        # Inicia o detector de key automaticamente
        if CONFIG.get("auto_key", True):
            self.key_detector.start()
            self.log("🔑 Auto-Key ATIVADO")

        with Live(self.render(), refresh_per_second=2, screen=True) as live:
            try:
                while self.running:
                    live.update(self.render())
                    time.sleep(0.5)
            except KeyboardInterrupt:
                self.running = False
                self.key_detector.stop()

    def render(self):
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=5),
            Layout(name="main", size=14),
            Layout(name="logs", size=8)
        )

        # Header com indicador de Auto-Key
        auto_key_status = "[green]ON[/green]" if CONFIG.get("auto_key", True) else "[red]OFF[/red]"
        header = Text()
        header.append("╔══════════════════════════════════════════════════════════╗\n", style="bright_red")
        header.append("║          ", style="bright_red")
        header.append("RE_PHONE", style="bold white on red")
        header.append("  v8.1  ", style="bold bright_red")
        header.append("by MSA", style="italic white")
        header.append("               ║\n", style="bright_red")
        header.append("╚══════════════════════════════════════════════════════════╝", style="bright_red")
        layout["header"].update(Align.center(header))

        # Tabela de instâncias
        table = Table(box=ROUNDED, border_style="bright_red", expand=True, show_header=True, header_style="bold white on red")
        table.add_column("INSTÂNCIA", justify="left", style="bold")
        table.add_column("CPU", justify="center", width=10)
        table.add_column("STATUS", justify="center", width=12)
        table.add_column("EVENTO", justify="left")

        for pkg, inst in self.instances.items():
            with inst.lock:
                cpu = inst.cpu
                status = inst.status
                event = inst.last_event
                name = inst.name

            if status == "OK":
                status_txt = "[bold green]● ONLINE[/bold green]"
                cpu_txt = f"[green]{cpu:.1f}%[/green]"
            elif status == "SYNC":
                status_txt = "[bold blue]◐ SYNC[/bold blue]"
                cpu_txt = f"[blue]{cpu:.1f}%[/blue]"
            elif status == "LOW":
                status_txt = "[bold yellow]◑ LOW[/bold yellow]"
                cpu_txt = f"[yellow]{cpu:.1f}%[/yellow]"
            else:
                status_txt = "[bold red]○ DEAD[/bold red]"
                cpu_txt = f"[red]{cpu:.1f}%[/red]"

            table.add_row(f"[white]{name}[/white]", cpu_txt, status_txt, f"[dim]{event}[/dim]")

        # Adiciona linha de status do Auto-Key
        table.add_row("", "", "", "")
        table.add_row(f"[bright_red]🔑 AUTO-KEY[/bright_red]", "", auto_key_status, "[dim]Detecta key automaticamente[/dim]")

        layout["main"].update(Panel(table, title="[bold white on red] MONITORAMENTO [/bold white on red]", border_style="bright_red", box=DOUBLE))

        # Logs
        log_text = "\n".join(self.logs) if self.logs else "[dim]Aguardando eventos...[/dim]"
        layout["logs"].update(Panel(log_text, title="[bold white on red] LOGS [/bold white on red]", border_style="red", box=ROUNDED))

        return layout

monitor = Monitor()

# ═══════════════════════════════════════════════════════════════════
# INTERFACE PRINCIPAL
# ═══════════════════════════════════════════════════════════════════
def main_menu():
    while True:
        console.clear()
        
        banner = """[bold bright_red]
    ██████╗ ███████╗      ██████╗ ██╗  ██╗ ██████╗ ███╗   ██╗███████╗
    ██╔══██╗██╔════╝      ██╔══██╗██║  ██║██╔═══██╗████╗  ██║██╔════╝
    ██████╔╝█████╗  █████╗██████╔╝███████║██║   ██║██╔██╗ ██║█████╗  
    ██╔══██╗██╔══╝  ╚════╝██╔═══╝ ██╔══██║██║   ██║██║╚██╗██║██╔══╝  
    ██║  ██║███████╗      ██║     ██║  ██║╚██████╔╝██║ ╚████║███████╗
    ╚═╝  ╚═╝╚══════╝      ╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝[/bold bright_red]
    [white]                      v8.1 AUTO-KEY by MSA[/white]"""
        rprint(banner)
        
        # Status
        vip_ok = "✓" if CONFIG.get("vip_link") else "✗"
        wh_ok = "✓" if CONFIG.get("webhook_url") else "✗"
        ak_ok = "✓" if CONFIG.get("auto_key", True) else "✗"
        status_line = f"[bright_red]VIP:[/bright_red] [{('green' if vip_ok == '✓' else 'red')}]{vip_ok}[/] | [bright_red]WEBHOOK:[/bright_red] [{('green' if wh_ok == '✓' else 'red')}]{wh_ok}[/] | [bright_red]AUTO-KEY:[/bright_red] [{('green' if ak_ok == '✓' else 'red')}]{ak_ok}[/]"
        rprint(Panel(Align.center(status_line), border_style="red"))

        # Menu
        menu = Table.grid(expand=True, padding=1)
        menu.add_column(ratio=1)
        menu.add_column(ratio=1)
        menu.add_row(
            Panel("[bold white][1] 🚀 INICIAR MONITOR[/bold white]\n[dim]Com Auto-Key ativado[/dim]", border_style="bright_red"),
            Panel("[bold white][2] ⚙️ CONFIGURAÇÕES[/bold white]", border_style="red")
        )
        menu.add_row(
            Panel("[bold white][3] 🔑 KEY MANUAL[/bold white]\n[dim]Executar bypass agora[/dim]", border_style="red"),
            Panel("[bold white][4] 🛠️ FERRAMENTAS[/bold white]", border_style="red")
        )
        menu.add_row(
            Panel("[bold white][0] ❌ SAIR[/bold white]", border_style="dark_red"),
            Panel("[dim]RE_PHONE v8.1 by MSA[/dim]", border_style="dark_red")
        )
        rprint(menu)

        choice = Prompt.ask("\n[bold bright_red]Selecione[/bold bright_red]", choices=["1", "2", "3", "4", "0"])

        if choice == "1":
            monitor.start()
        elif choice == "2":
            config_menu()
        elif choice == "3":
            manual_key()
        elif choice == "4":
            tools_menu()
        elif choice == "0":
            break

def config_menu():
    console.clear()
    rprint(Panel("[bold]CONFIGURAÇÕES[/bold]", border_style="bright_red"))
    
    auto_key_status = "[green]ATIVADO[/green]" if CONFIG.get("auto_key", True) else "[red]DESATIVADO[/red]"
    
    rprint(f"[1] VIP Link: [dim]{CONFIG.get('vip_link', 'Não configurado')[:50]}...[/dim]")
    rprint(f"[2] Webhook: [dim]{CONFIG.get('webhook_url', 'Não configurado')[:50]}...[/dim]")
    rprint(f"[3] Auto-Key: {auto_key_status}")
    rprint("[0] Voltar")
    
    opt = Prompt.ask("Opção", choices=["1", "2", "3", "0"])
    if opt == "1":
        CONFIG["vip_link"] = Prompt.ask("Cole o VIP Link")
        save_config(CONFIG)
    elif opt == "2":
        CONFIG["webhook_url"] = Prompt.ask("Cole o Webhook")
        save_config(CONFIG)
    elif opt == "3":
        CONFIG["auto_key"] = not CONFIG.get("auto_key", True)
        save_config(CONFIG)
        status = "ATIVADO" if CONFIG["auto_key"] else "DESATIVADO"
        rprint(f"[green]Auto-Key {status}![/green]")
        time.sleep(1)

def manual_key():
    """Executa o bypass de key manualmente"""
    console.clear()
    rprint(Panel("[bold]BYPASS DE KEY MANUAL[/bold]", border_style="bright_red"))
    rprint("[yellow]Iniciando automação...[/yellow]")
    
    xml = get_ui_xml()
    if "key" not in xml and "checkpoint" not in xml:
        rprint("[red]Tela de key não detectada. Abra o Delta primeiro.[/red]")
        Prompt.ask("Enter para voltar")
        return
    
    rprint("[green]✓ Tela de key detectada[/green]")
    
    buttons = ["get key", "receive key", "checkpoint", "obter key", "pegar key"]
    for btn in buttons:
        if click_element_by_text(btn):
            rprint(f"[green]✓ Clicou em '{btn}'[/green]")
            break
    
    time.sleep(4)
    
    xml = get_ui_xml()
    if "continue" in xml or "proceed" in xml:
        for btn in ["continue", "proceed", "prosseguir", "next"]:
            if click_element_by_text(btn):
                rprint(f"[green]✓ Clicou em '{btn}'[/green]")
                break
        time.sleep(5)
    
    xml = get_ui_xml()
    if "copy" in xml or "copiar" in xml:
        for btn in ["copy", "copiar", "copy key"]:
            if click_element_by_text(btn):
                rprint(f"[green]✓ Key copiada![/green]")
                break
        
        time.sleep(2)
        adb_keyevent(4)
        time.sleep(1)
        adb_keyevent(279)
        
        for btn in ["play", "execute", "continuar", "confirm"]:
            if click_element_by_text(btn):
                rprint(f"[green]✓ Finalizado![/green]")
                break
    
    rprint("\n[bold green]Automação concluída![/bold green]")
    Prompt.ask("Enter para voltar")

def tools_menu():
    console.clear()
    rprint(Panel("[bold]FERRAMENTAS[/bold]", border_style="bright_red"))
    
    rprint("[1] Forçar Modo Retrato")
    rprint("[2] Parar Todos os Roblox")
    rprint("[3] Listar Pacotes")
    rprint("[4] Testar ADB")
    rprint("[0] Voltar")
    
    opt = Prompt.ask("Opção", choices=["1", "2", "3", "4", "0"])
    if opt == "1":
        force_portrait()
        rprint("[green]Modo retrato ativado![/green]")
        time.sleep(1)
    elif opt == "2":
        for p in get_packages():
            stop_app(p)
        rprint("[red]Todos parados![/red]")
        time.sleep(1)
    elif opt == "3":
        pkgs = get_packages()
        for p in pkgs:
            rprint(f"[green]• {p}[/green]")
        Prompt.ask("Enter")
    elif opt == "4":
        out = subprocess.run("adb devices", shell=True, capture_output=True, text=True).stdout
        rprint(out)
        Prompt.ask("Enter")

if __name__ == "__main__":
    main_menu()
