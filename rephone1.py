#!/usr/bin/env python3
"""
RE_PHONE v8.2 by MSA
Sistema de Monitoramento e Automação para Roblox
Com Verificação Individual de Key por Janela
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
def adb(cmd, timeout=5):
    try:
        return subprocess.check_output(f"adb shell {cmd}", shell=True, stderr=subprocess.DEVNULL, timeout=timeout).decode().strip()
    except: return ""

def adb_tap(x, y):
    adb(f"input tap {x} {y}")

def adb_text(txt):
    safe_txt = txt.replace("'", "").replace('"', '')
    adb(f"input text '{safe_txt}'")

def adb_keyevent(key):
    adb(f"input keyevent {key}")

def get_ui_xml():
    adb("uiautomator dump /sdcard/ui.xml > /dev/null 2>&1", timeout=10)
    return adb("cat /sdcard/ui.xml", timeout=5)

def find_element_bounds(xml, text):
    """Encontra coordenadas de um elemento pelo texto (case insensitive)"""
    pattern = rf'text="([^"]*{re.escape(text)}[^"]*)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
    match = re.search(pattern, xml, re.IGNORECASE)
    if match:
        x1, y1, x2, y2 = map(int, match.groups()[1:])
        return (x1 + x2) // 2, (y1 + y2) // 2
    return None

def find_clickable_link(xml):
    """Encontra um link clicável na UI"""
    # Procura por URLs ou botões que parecem links
    pattern = r'text="(https?://[^"]+)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
    match = re.search(pattern, xml, re.IGNORECASE)
    if match:
        url = match.group(1)
        x1, y1, x2, y2 = map(int, match.groups()[1:])
        return url, ((x1 + x2) // 2, (y1 + y2) // 2)
    return None, None

def click_element_by_text(text, xml=None):
    """Clica em um elemento pelo texto"""
    if xml is None:
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

def bring_to_front(pkg):
    """Traz o app para frente (tela cheia)"""
    # Método 1: Usar monkey para abrir o app
    adb(f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1 > /dev/null 2>&1")
    time.sleep(1)

def maximize_window(pkg):
    """Tenta maximizar a janela do app"""
    # Primeiro traz para frente
    bring_to_front(pkg)
    time.sleep(0.5)
    # Tenta maximizar via wm
    adb(f"am start --activity-task-on-home -n {pkg}/.MainActivity 2>/dev/null")

def send_webhook(url, msg, screenshot=False):
    if not url:
        return
    try:
        if screenshot:
            # Tira screenshot e envia
            adb("screencap -p /sdcard/screen.png")
            subprocess.run("adb pull /sdcard/screen.png /tmp/screen.png", shell=True, capture_output=True)
            with open("/tmp/screen.png", "rb") as f:
                requests.post(url, files={"file": ("screenshot.png", f)}, data={"content": msg}, timeout=10)
        else:
            requests.post(url, json={"content": msg}, timeout=5)
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
        self.key_cooldown = 0
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
# VERIFICADOR DE KEY INDIVIDUAL
# ═══════════════════════════════════════════════════════════════════
class KeyChecker:
    """Verifica key em cada janela individualmente"""
    def __init__(self, monitor):
        self.monitor = monitor
        self.running = False
        self.checking = False
        self.current_pkg = ""

    def detect_key_screen(self, xml):
        """Detecta se a tela de key está visível"""
        xml_lower = xml.lower()
        key_indicators = [
            "receive key", "get key", "checkpoint", "key system",
            "obter key", "pegar key", "continue key", "enter key"
        ]
        return any(ind in xml_lower for ind in key_indicators)

    def process_key_for_package(self, pkg):
        """Processa a key para um pacote específico"""
        self.current_pkg = pkg
        name = pkg.split('.')[-1].upper()
        self.monitor.log(f"🔍 Verificando key: {name}")

        # Passo 1: Trazer a janela para frente
        bring_to_front(pkg)
        time.sleep(2)

        # Passo 2: Capturar a UI
        xml = get_ui_xml()

        # Passo 3: Verificar se tem tela de key
        if not self.detect_key_screen(xml):
            self.monitor.log(f"✓ {name}: Sem key")
            return False

        self.monitor.log(f"🔑 {name}: KEY DETECTADA!")
        send_webhook(CONFIG.get("webhook_url", ""), f"🔑 **{name}**: Key detectada, iniciando bypass...", screenshot=True)

        # Passo 4: Clicar em "Receive Key" ou similar
        key_buttons = ["receive key", "get key", "obter key", "pegar key", "continue"]
        clicked = False
        for btn in key_buttons:
            if click_element_by_text(btn, xml):
                self.monitor.log(f"✓ Clicou: {btn}")
                clicked = True
                break

        if not clicked:
            # Tenta coordenadas padrão (centro inferior da tela)
            adb_tap(540, 1400)
            self.monitor.log("✓ Clicou coordenada padrão")

        time.sleep(3)

        # Passo 5: Verificar se abriu link/navegador
        xml = get_ui_xml()
        
        # Procurar por botões de continuar no navegador/linkvertise
        continue_buttons = ["continue", "proceed", "prosseguir", "next", "verificar", "free access", "direct link"]
        for btn in continue_buttons:
            if click_element_by_text(btn, xml):
                self.monitor.log(f"✓ Navegador: {btn}")
                time.sleep(3)
                xml = get_ui_xml()
                break

        # Passo 6: Tentar copiar a key
        time.sleep(2)
        xml = get_ui_xml()
        
        copy_buttons = ["copy", "copiar", "copy key", "get key"]
        for btn in copy_buttons:
            if click_element_by_text(btn, xml):
                self.monitor.log(f"✓ Key copiada!")
                time.sleep(1)
                break

        # Passo 7: Voltar para o app e colar
        adb_keyevent(4)  # Back
        time.sleep(1)
        adb_keyevent(4)  # Back novamente se necessário
        time.sleep(1)

        # Trazer o Roblox de volta
        bring_to_front(pkg)
        time.sleep(2)

        # Tentar colar a key
        xml = get_ui_xml()
        
        # Procurar campo de entrada
        if "enter key" in xml.lower() or "input" in xml.lower():
            # Clicar no campo de entrada
            if click_element_by_text("enter key", xml) or click_element_by_text("key", xml):
                time.sleep(0.5)
            adb_keyevent(279)  # Paste
            time.sleep(1)

        # Clicar em confirmar/play
        confirm_buttons = ["confirm", "submit", "play", "execute", "continuar", "ok"]
        for btn in confirm_buttons:
            if click_element_by_text(btn):
                self.monitor.log(f"✓ Confirmado: {btn}")
                break

        send_webhook(CONFIG.get("webhook_url", ""), f"✅ **{name}**: Bypass concluído!")
        self.monitor.log(f"✅ {name}: Bypass completo!")
        
        return True

    def check_all_packages(self):
        """Verifica key em todos os pacotes, um por vez"""
        if self.checking:
            return
        
        self.checking = True
        pkgs = get_packages()
        
        for pkg in pkgs:
            if not self.running:
                break
            
            inst = self.monitor.instances.get(pkg)
            if inst:
                # Só verifica se passou o cooldown de key
                if time.time() > inst.key_cooldown:
                    try:
                        if self.process_key_for_package(pkg):
                            inst.key_cooldown = time.time() + 300  # 5 min cooldown após key
                    except Exception as e:
                        self.monitor.log(f"⚠️ Erro key {pkg.split('.')[-1]}: {str(e)[:20]}")
            
            time.sleep(2)  # Pausa entre verificações
        
        self.checking = False

    def worker(self):
        """Thread de verificação periódica"""
        while self.running:
            if CONFIG.get("auto_key", True):
                self.check_all_packages()
            time.sleep(30)  # Verifica a cada 30 segundos

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
        self.key_checker = KeyChecker(self)

    def log(self, msg):
        t = datetime.datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{t}] {msg}")
        if len(self.logs) > 8: self.logs.pop(0)

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

        # Inicia o verificador de key
        if CONFIG.get("auto_key", True):
            self.key_checker.start()
            self.log("🔑 Auto-Key ATIVADO (Verificação Individual)")

        with Live(self.render(), refresh_per_second=2, screen=True) as live:
            try:
                while self.running:
                    live.update(self.render())
                    time.sleep(0.5)
            except KeyboardInterrupt:
                self.running = False
                self.key_checker.stop()

    def render(self):
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=5),
            Layout(name="main", size=12),
            Layout(name="logs", size=10)
        )

        auto_key_status = "[green]ON[/green]" if CONFIG.get("auto_key", True) else "[red]OFF[/red]"
        checking = f" [yellow](Verificando: {self.key_checker.current_pkg.split('.')[-1]})[/yellow]" if self.key_checker.checking else ""
        
        header = Text()
        header.append("╔══════════════════════════════════════════════════════════╗\n", style="bright_red")
        header.append("║          ", style="bright_red")
        header.append("RE_PHONE", style="bold white on red")
        header.append("  v8.2  ", style="bold bright_red")
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

        table.add_row("", "", "", "")
        table.add_row(f"[bright_red]🔑 AUTO-KEY[/bright_red]", "", auto_key_status, f"[dim]Verifica cada janela{checking}[/dim]")

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
    [white]                   v8.2 INDIVIDUAL KEY by MSA[/white]"""
        rprint(banner)
        
        vip_ok = "✓" if CONFIG.get("vip_link") else "✗"
        wh_ok = "✓" if CONFIG.get("webhook_url") else "✗"
        ak_ok = "✓" if CONFIG.get("auto_key", True) else "✗"
        status_line = f"[bright_red]VIP:[/bright_red] [{('green' if vip_ok == '✓' else 'red')}]{vip_ok}[/] | [bright_red]WEBHOOK:[/bright_red] [{('green' if wh_ok == '✓' else 'red')}]{wh_ok}[/] | [bright_red]AUTO-KEY:[/bright_red] [{('green' if ak_ok == '✓' else 'red')}]{ak_ok}[/]"
        rprint(Panel(Align.center(status_line), border_style="red"))

        menu = Table.grid(expand=True, padding=1)
        menu.add_column(ratio=1)
        menu.add_column(ratio=1)
        menu.add_row(
            Panel("[bold white][1] 🚀 INICIAR MONITOR[/bold white]\n[dim]Verifica key em cada janela[/dim]", border_style="bright_red"),
            Panel("[bold white][2] ⚙️ CONFIGURAÇÕES[/bold white]", border_style="red")
        )
        menu.add_row(
            Panel("[bold white][3] 🔑 VERIFICAR KEYS AGORA[/bold white]\n[dim]Executa verificação manual[/dim]", border_style="red"),
            Panel("[bold white][4] 🛠️ FERRAMENTAS[/bold white]", border_style="red")
        )
        menu.add_row(
            Panel("[bold white][0] ❌ SAIR[/bold white]", border_style="dark_red"),
            Panel("[dim]RE_PHONE v8.2 by MSA[/dim]", border_style="dark_red")
        )
        rprint(menu)

        choice = Prompt.ask("\n[bold bright_red]Selecione[/bold bright_red]", choices=["1", "2", "3", "4", "0"])

        if choice == "1":
            monitor.start()
        elif choice == "2":
            config_menu()
        elif choice == "3":
            manual_key_check()
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

def manual_key_check():
    """Verifica keys manualmente em todos os pacotes"""
    console.clear()
    rprint(Panel("[bold]VERIFICAÇÃO MANUAL DE KEYS[/bold]", border_style="bright_red"))
    
    pkgs = get_packages()
    if not pkgs:
        rprint("[red]Nenhum pacote Roblox encontrado![/red]")
        Prompt.ask("Enter para voltar")
        return

    rprint(f"[yellow]Encontrados {len(pkgs)} pacotes. Verificando cada um...[/yellow]\n")
    
    checker = KeyChecker(type('obj', (object,), {'log': lambda self, x: rprint(x), 'instances': {}})())
    
    for pkg in pkgs:
        name = pkg.split('.')[-1].upper()
        rprint(f"\n[bright_red]═══ {name} ═══[/bright_red]")
        
        try:
            result = checker.process_key_for_package(pkg)
            if result:
                rprint(f"[green]✓ Key processada para {name}[/green]")
            else:
                rprint(f"[blue]✓ {name} não precisa de key[/blue]")
        except Exception as e:
            rprint(f"[red]✗ Erro em {name}: {e}[/red]")
        
        time.sleep(2)
    
    rprint("\n[bold green]Verificação concluída![/bold green]")
    Prompt.ask("Enter para voltar")

def tools_menu():
    console.clear()
    rprint(Panel("[bold]FERRAMENTAS[/bold]", border_style="bright_red"))
    
    rprint("[1] Forçar Modo Retrato")
    rprint("[2] Parar Todos os Roblox")
    rprint("[3] Listar Pacotes")
    rprint("[4] Testar ADB")
    rprint("[5] Trazer Janela para Frente")
    rprint("[0] Voltar")
    
    opt = Prompt.ask("Opção", choices=["1", "2", "3", "4", "5", "0"])
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
        for i, p in enumerate(pkgs, 1):
            rprint(f"[green]{i}. {p}[/green]")
        Prompt.ask("Enter")
    elif opt == "4":
        out = subprocess.run("adb devices", shell=True, capture_output=True, text=True).stdout
        rprint(out)
        Prompt.ask("Enter")
    elif opt == "5":
        pkgs = get_packages()
        for i, p in enumerate(pkgs, 1):
            rprint(f"[green]{i}. {p.split('.')[-1]}[/green]")
        idx = Prompt.ask("Número do pacote", default="1")
        try:
            pkg = pkgs[int(idx) - 1]
            bring_to_front(pkg)
            rprint(f"[green]Janela {pkg.split('.')[-1]} trazida para frente![/green]")
        except:
            rprint("[red]Índice inválido[/red]")
        time.sleep(2)

if __name__ == "__main__":
    main_menu()
