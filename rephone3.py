#!/usr/bin/env python3
"""
RE_PHONE v9.0 PRO by MSA
Sistema Profissional de Monitoramento para Roblox
- Monitoramento passivo (CPU/Rede)
- Focus Lock inteligente
- Fila sequencial de verificação
- am start com Activity correta
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
# CONSTANTES DE MONITORAMENTO
# ═══════════════════════════════════════════════════════════════════
CPU_THRESHOLD_ACTIVE = 15.0      # CPU acima disso = jogo ativo
CPU_THRESHOLD_SUSPECT = 5.0     # CPU abaixo disso = suspeito
SUSPECT_COUNT_LIMIT = 5         # Quantas verificações suspeitas antes de agir
CHECK_INTERVAL = 3              # Intervalo entre verificações (segundos)
FOCUS_DELAY = 1.0               # Delay entre focar janelas (segundos)
COOLDOWN_AFTER_RESTART = 120    # Segundos de cooldown após restart

# ═══════════════════════════════════════════════════════════════════
# FUNÇÕES ADB OTIMIZADAS
# ═══════════════════════════════════════════════════════════════════
def adb(cmd, timeout=5):
    """Executa comando ADB com timeout"""
    try:
        return subprocess.check_output(
            f"adb shell {cmd}", 
            shell=True, 
            stderr=subprocess.DEVNULL, 
            timeout=timeout
        ).decode().strip()
    except: 
        return ""

def adb_tap(x, y):
    """Toca na tela nas coordenadas especificadas"""
    adb(f"input tap {x} {y}")
    time.sleep(0.3)

def adb_keyevent(key):
    """Envia um keyevent"""
    adb(f"input keyevent {key}")

def adb_paste():
    """Cola o conteúdo da área de transferência"""
    adb("input keyevent 279")
    time.sleep(0.5)

def force_portrait():
    """Força o modo retrato"""
    adb("settings put system accelerometer_rotation 0")
    adb("settings put system user_rotation 0")

# ═══════════════════════════════════════════════════════════════════
# FUNÇÕES DE PACOTES E PROCESSOS
# ═══════════════════════════════════════════════════════════════════
def get_packages():
    """Obtém todos os pacotes Roblox instalados"""
    out = adb("pm list packages roblox")
    return [l.replace("package:", "").strip() for l in out.splitlines() if "roblox" in l.lower()]

def get_pid(pkg):
    """Obtém o PID de um pacote"""
    return adb(f"pidof {pkg}")

def get_cpu(pid):
    """Obtém o uso de CPU de um processo"""
    if not pid: 
        return 0.0
    top = adb(f"top -n 1 -p {pid} | grep {pid}")
    if top:
        for p in top.split():
            if "%" in p:
                try: 
                    return float(p.replace("%", "").replace(",", "."))
                except: 
                    pass
    return 0.0

def get_uid(pkg):
    """Obtém o UID de um pacote"""
    out = adb(f"dumpsys package {pkg} | grep userId")
    match = re.search(r'userId=(\d+)', out)
    return match.group(1) if match else None

def get_network_bytes(uid):
    """Obtém bytes de rede para um UID"""
    if not uid:
        return 0
    try:
        rx = adb(f"cat /proc/uid_stat/{uid}/tcp_rcv 2>/dev/null") or "0"
        tx = adb(f"cat /proc/uid_stat/{uid}/tcp_snd 2>/dev/null") or "0"
        return int(rx) + int(tx)
    except:
        return 0

# ═══════════════════════════════════════════════════════════════════
# FUNÇÕES DE CONTROLE DE APP (CORRETAS)
# ═══════════════════════════════════════════════════════════════════
def stop_app(pkg):
    """Para um app completamente"""
    adb(f"am force-stop {pkg}")

def start_app_with_vip(pkg, vip_link):
    """
    Inicia o Roblox com o link VIP usando a Activity correta.
    Usa am start -n com ActivityProtocolLaunch para foco limpo.
    """
    # Activity correta para abrir links do Roblox
    activity = f"{pkg}/com.roblox.client.ActivityProtocolLaunch"
    
    # Comando correto com Activity específica
    cmd = f"am start -n {activity} -a android.intent.action.VIEW -d '{vip_link}'"
    adb(cmd)

def bring_to_focus(pkg):
    """
    Traz um app para o foco de forma limpa.
    Usa am start com a Activity principal em vez de monkey.
    """
    # Tenta usar a Activity de launcher padrão
    activity = f"{pkg}/com.roblox.client.startup.ActivitySplash"
    cmd = f"am start -n {activity}"
    result = adb(cmd)
    
    # Se falhar, tenta com a Activity genérica
    if "Error" in result or not result:
        adb(f"am start -n {pkg}/.MainActivity")
    
    time.sleep(FOCUS_DELAY)

# ═══════════════════════════════════════════════════════════════════
# FUNÇÕES DE UI
# ═══════════════════════════════════════════════════════════════════
def get_ui_xml():
    """Captura a UI atual (só usar quando em foco!)"""
    adb("uiautomator dump /sdcard/ui.xml > /dev/null 2>&1", timeout=10)
    time.sleep(0.5)
    return adb("cat /sdcard/ui.xml", timeout=5)

def find_element_bounds(xml, text):
    """Encontra coordenadas de um elemento pelo texto"""
    pattern = rf'text="([^"]*)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
    for match in re.finditer(pattern, xml):
        found_text = match.group(1)
        if text.lower() in found_text.lower():
            x1, y1, x2, y2 = map(int, match.groups()[1:])
            return (x1 + x2) // 2, (y1 + y2) // 2
    return None

def click_element_by_text(text, xml=None):
    """Clica em um elemento pelo texto"""
    if xml is None:
        xml = get_ui_xml()
    coords = find_element_bounds(xml, text)
    if coords:
        adb_tap(coords[0], coords[1])
        return True
    return False

def detect_key_screen(xml):
    """Detecta se a tela de key está visível"""
    xml_lower = xml.lower()
    indicators = ["welcome back", "receive key", "enter key", "key_example", "key system"]
    return any(ind in xml_lower for ind in indicators)

def detect_disconnected(xml):
    """Detecta se o jogo está desconectado"""
    xml_lower = xml.lower()
    indicators = ["disconnected", "connection lost", "reconectar", "reconnect", "lost connection"]
    return any(ind in xml_lower for ind in indicators)

def detect_home_screen(xml):
    """
    Detecta se esta na tela inicial do Roblox (nao no jogo).
    Se detectar, precisa fechar e reabrir com o link VIP.
    """
    xml_lower = xml.lower()
    
    # Indicadores FORTES da tela home do Roblox (lobby/menu principal)
    home_indicators = [
        "home",
        "avatar",
        "charts",
        "friends",
        "criar conta",
        "check your age",
        "continue playing",
        "recommended",
        "recomendados",
        "discover",
        "search",
        "pesquisar",
        "destaques",
    ]
    
    # Indicadores de que esta DENTRO de um jogo (nao na home)
    game_indicators = [
        "backpack",
        "leaderboard",
        "leave",
        "reset character",
        "honey",
        "hive",
        "bee",
    ]
    
    # Conta quantos indicadores de home foram encontrados
    home_count = sum(1 for ind in home_indicators if ind in xml_lower)
    game_count = sum(1 for ind in game_indicators if ind in xml_lower)
    
    # Se tem 2+ indicadores de home e nenhum de jogo, esta na home
    return home_count >= 2 and game_count == 0

# ═══════════════════════════════════════════════════════════════════
# WEBHOOK
# ═══════════════════════════════════════════════════════════════════
def send_webhook(url, msg, screenshot=False):
    """Envia mensagem para webhook do Discord"""
    if not url:
        return
    try:
        if screenshot:
            adb("screencap -p /sdcard/screen.png")
            subprocess.run("adb pull /sdcard/screen.png /tmp/screen.png", 
                         shell=True, capture_output=True, timeout=10)
            if os.path.exists("/tmp/screen.png"):
                with open("/tmp/screen.png", "rb") as f:
                    requests.post(url, files={"file": ("screenshot.png", f)}, 
                                data={"content": msg}, timeout=10)
                return
        requests.post(url, json={"content": msg}, timeout=5)
    except: 
        pass

# ═══════════════════════════════════════════════════════════════════
# CLASSE DE INSTÂNCIA (ISOLADA)
# ═══════════════════════════════════════════════════════════════════
class Instance:
    """Representa uma instância isolada do Roblox"""
    def __init__(self, pkg):
        self.pkg = pkg
        self.name = pkg.split('.')[-1].upper()
        self.pid = ""
        self.cpu = 0.0
        self.uid = get_uid(pkg)
        self.last_bytes = 0
        self.current_bytes = 0
        self.network_speed = 0
        self.status = "INIT"
        self.suspect_count = 0      # Contador de verificações suspeitas
        self.cooldown_until = 0     # Timestamp até quando está em cooldown
        self.last_event = "Iniciando..."
        self.needs_check = False    # Flag: precisa verificar UI?
        self.lock = threading.Lock()

    def update_metrics(self):
        """Atualiza métricas de CPU e rede (passivo, sem foco)"""
        with self.lock:
            self.pid = get_pid(self.pkg)
            self.cpu = get_cpu(self.pid) if self.pid else 0.0
            
            # Atualiza rede
            self.last_bytes = self.current_bytes
            self.current_bytes = get_network_bytes(self.uid)
            self.network_speed = max(0, self.current_bytes - self.last_bytes)
            
            # Determina status baseado em métricas
            now = time.time()
            
            if now < self.cooldown_until:
                self.status = "SYNC"
                self.suspect_count = 0
            elif not self.pid:
                self.status = "DEAD"
                self.needs_check = True
            elif self.cpu >= CPU_THRESHOLD_ACTIVE:
                self.status = "OK"
                self.suspect_count = 0
                self.needs_check = False
            elif self.cpu < CPU_THRESHOLD_SUSPECT:
                self.suspect_count += 1
                if self.suspect_count >= SUSPECT_COUNT_LIMIT:
                    self.status = "SUSPECT"
                    self.needs_check = True
                else:
                    self.status = "LOW"
            else:
                self.status = "LOW"

    def mark_checked(self):
        """Marca que a verificação de UI foi feita"""
        with self.lock:
            self.needs_check = False

    def restart(self, reason, vip_link, webhook_url):
        """Reinicia esta instância específica"""
        with self.lock:
            self.last_event = reason
            self.suspect_count = 0
            self.needs_check = False
            self.cooldown_until = time.time() + COOLDOWN_AFTER_RESTART
        
        send_webhook(webhook_url, f"🔄 `{self.name}` -> {reason}")
        stop_app(self.pkg)
        time.sleep(1)
        start_app_with_vip(self.pkg, vip_link)

# ═══════════════════════════════════════════════════════════════════
# BYPASS DE KEY DO DELTA
# ═══════════════════════════════════════════════════════════════════
class DeltaKeyBypass:
    """
    Processa o bypass de key do Delta.
    Só é chamado quando a instância está em foco!
    """
    def __init__(self, log_func):
        self.log = log_func

    def process(self, pkg, xml):
        """
        Processa o bypass de key.
        Assume que o app já está em foco e xml já foi capturado.
        """
        name = pkg.split('.')[-1].upper()
        
        if not detect_key_screen(xml):
            return False
        
        self.log(f"🔑 {name}: KEY DETECTADA!")
        send_webhook(CONFIG.get("webhook_url", ""), f"🔑 **{name}**: Key detectada!", screenshot=True)

        # Passo 1: Clicar em "Receive Key"
        self.log(f"→ Clicando Receive Key...")
        if not click_element_by_text("Receive Key", xml):
            adb_tap(350, 515)
        time.sleep(2)

        # Passo 2: Clicar em "Checkpoint opened"
        xml = get_ui_xml()
        self.log(f"→ Procurando Checkpoint...")
        if not click_element_by_text("Checkpoint", xml):
            if not click_element_by_text("opened", xml):
                adb_tap(350, 600)
        time.sleep(2)

        # Passo 3: Abrir link no navegador (já deve estar na clipboard)
        self.log(f"→ Abrindo navegador...")
        time.sleep(4)

        # Passo 4: Clicar em "Copy" na página
        xml = get_ui_xml()
        self.log(f"→ Copiando key...")
        if not click_element_by_text("Copy", xml):
            adb_tap(540, 670)
        time.sleep(2)

        # Passo 5: Voltar para o jogo
        self.log(f"→ Voltando para o jogo...")
        adb_keyevent(4)  # Back
        time.sleep(1)
        bring_to_focus(pkg)
        time.sleep(2)

        # Passo 6: Clicar no campo de key
        xml = get_ui_xml()
        self.log(f"→ Focando campo...")
        if not click_element_by_text("KEY_example", xml):
            if not click_element_by_text("Enter key", xml):
                adb_tap(350, 330)
        time.sleep(1)

        # Passo 7: Colar a key
        self.log(f"→ Colando key...")
        adb_paste()
        time.sleep(1)

        # Passo 8: Clicar em "Continue"
        xml = get_ui_xml()
        self.log(f"→ Confirmando...")
        if not click_element_by_text("Continue", xml):
            adb_tap(350, 427)
        time.sleep(2)

        send_webhook(CONFIG.get("webhook_url", ""), f"✅ **{name}**: Bypass concluído!", screenshot=True)
        self.log(f"✅ {name}: BYPASS COMPLETO!")
        
        return True

# ═══════════════════════════════════════════════════════════════════
# MONITOR PRINCIPAL (FOCUS LOCK)
# ═══════════════════════════════════════════════════════════════════
class Monitor:
    """
    Monitor principal com Focus Lock.
    - Monitora CPU/rede passivamente (sem foco)
    - Só traz para foco quando detecta problema
    - Processa um clone por vez (fila sequencial)
    """
    def __init__(self):
        self.instances = {}
        self.running = False
        self.logs = []
        self.focus_lock = threading.Lock()  # Garante que só um clone está em foco por vez
        self.key_bypass = None
        self.checking_instance = ""

    def log(self, msg):
        """Adiciona mensagem ao log"""
        t = datetime.datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{t}] {msg}")
        if len(self.logs) > 12: 
            self.logs.pop(0)

    def passive_monitor_worker(self, inst):
        """
        Worker de monitoramento passivo para uma instância.
        Só atualiza métricas, não traz para foco.
        """
        while self.running and inst.pkg in self.instances:
            inst.update_metrics()
            time.sleep(CHECK_INTERVAL)

    def focus_check_worker(self):
        """
        Worker que processa instâncias que precisam de verificação.
        Usa Focus Lock para garantir uma por vez.
        """
        while self.running:
            # Encontra instâncias que precisam de verificação
            to_check = []
            for pkg, inst in self.instances.items():
                with inst.lock:
                    if inst.needs_check and time.time() >= inst.cooldown_until:
                        to_check.append(inst)
            
            # Processa uma por vez (fila sequencial)
            for inst in to_check:
                if not self.running:
                    break
                
                with self.focus_lock:  # Garante exclusividade de foco
                    self.check_instance_with_focus(inst)
                
                time.sleep(FOCUS_DELAY)  # Delay entre verificações
            
            time.sleep(CHECK_INTERVAL)

    def check_instance_with_focus(self, inst):
        """
        Verifica uma instância trazendo-a para foco.
        Chamado apenas quando há suspeita de problema.
        """
        self.checking_instance = inst.name
        self.log(f"🔍 Verificando {inst.name}...")
        
        vip = CONFIG.get("vip_link", "")
        webhook = CONFIG.get("webhook_url", "")
        
        # Se o processo morreu, reinicia direto
        if not inst.pid:
            inst.restart("Processo morto", vip, webhook)
            self.log(f"💀 {inst.name}: Reiniciado (morto)")
            inst.mark_checked()
            self.checking_instance = ""
            return
        
        # Traz para foco de forma limpa
        bring_to_focus(inst.pkg)
        time.sleep(1)
        
        # Captura UI (agora sim, com foco)
        xml = get_ui_xml()
        
        # Verifica estados problemáticos
        if detect_disconnected(xml):
            inst.restart("Desconectado", vip, webhook)
            self.log(f"📡 {inst.name}: Reiniciado (desconectado)")
            send_webhook(webhook, f"📡 **{inst.name}**: Desconectado!", screenshot=True)
        
        elif detect_home_screen(xml):
            inst.restart("Tela Home", vip, webhook)
            self.log(f"🏠 {inst.name}: Reiniciado (home)")
            send_webhook(webhook, f"🏠 **{inst.name}**: Voltou para Home!", screenshot=True)
        
        elif detect_key_screen(xml):
            # Processa bypass de key
            if CONFIG.get("auto_key", True):
                self.key_bypass.process(inst.pkg, xml)
            else:
                send_webhook(webhook, f"🔑 **{inst.name}**: Key detectada (auto-key OFF)", screenshot=True)
                self.log(f"🔑 {inst.name}: Key (auto-key OFF)")
        
        else:
            # Tudo OK, pode ter sido falso positivo
            self.log(f"✓ {inst.name}: OK")
        
        inst.mark_checked()
        self.checking_instance = ""

    def start(self):
        """Inicia o monitor"""
        vip = CONFIG.get("vip_link", "")
        if not vip:
            rprint("[bold red]Configure o VIP Link primeiro![/bold red]")
            time.sleep(2)
            return

        force_portrait()
        self.running = True
        self.key_bypass = DeltaKeyBypass(self.log)
        
        pkgs = get_packages()
        if not pkgs:
            rprint("[bold red]Nenhum pacote Roblox encontrado![/bold red]")
            time.sleep(2)
            return

        self.log(f"📦 {len(pkgs)} pacotes encontrados")

        # Cria instâncias e inicia workers de monitoramento passivo
        for pkg in pkgs:
            inst = Instance(pkg)
            self.instances[pkg] = inst
            threading.Thread(target=self.passive_monitor_worker, args=(inst,), daemon=True).start()
            self.log(f"✓ {inst.name} monitorando")

        # Inicia worker de verificação com foco
        threading.Thread(target=self.focus_check_worker, daemon=True).start()
        self.log("🔒 Focus Lock ativado")

        # Loop de renderização
        with Live(self.render(), refresh_per_second=2, screen=True) as live:
            try:
                while self.running:
                    live.update(self.render())
                    time.sleep(0.5)
            except KeyboardInterrupt:
                self.running = False

    def render(self):
        """Renderiza o HUD"""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=5),
            Layout(name="main", size=12),
            Layout(name="logs", size=10)
        )

        # Header
        header = Text()
        header.append("╔══════════════════════════════════════════════════════════╗\n", style="bright_red")
        header.append("║          ", style="bright_red")
        header.append("RE_PHONE", style="bold white on red")
        header.append("  v9.0 PRO  ", style="bold bright_red")
        header.append("by MSA", style="italic white")
        header.append("           ║\n", style="bright_red")
        header.append("╚══════════════════════════════════════════════════════════╝", style="bright_red")
        layout["header"].update(Align.center(header))

        # Tabela de instâncias
        table = Table(box=ROUNDED, border_style="bright_red", expand=True, 
                     show_header=True, header_style="bold white on red")
        table.add_column("INSTÂNCIA", justify="left", style="bold", width=15)
        table.add_column("CPU", justify="center", width=8)
        table.add_column("REDE", justify="center", width=10)
        table.add_column("STATUS", justify="center", width=12)
        table.add_column("SUSPEITO", justify="center", width=8)

        for pkg, inst in self.instances.items():
            with inst.lock:
                cpu = inst.cpu
                status = inst.status
                name = inst.name
                suspect = inst.suspect_count
                net = inst.network_speed

            # Formatação de CPU
            if cpu >= CPU_THRESHOLD_ACTIVE:
                cpu_txt = f"[green]{cpu:.1f}%[/green]"
            elif cpu >= CPU_THRESHOLD_SUSPECT:
                cpu_txt = f"[yellow]{cpu:.1f}%[/yellow]"
            else:
                cpu_txt = f"[red]{cpu:.1f}%[/red]"

            # Formatação de rede
            if net > 1000:
                net_txt = f"[green]{net/1024:.1f}KB[/green]"
            elif net > 0:
                net_txt = f"[yellow]{net}B[/yellow]"
            else:
                net_txt = f"[red]0[/red]"

            # Formatação de status
            status_map = {
                "OK": "[bold green]● ONLINE[/bold green]",
                "SYNC": "[bold blue]◐ SYNC[/bold blue]",
                "LOW": "[bold yellow]◑ LOW[/bold yellow]",
                "SUSPECT": "[bold red]⚠ SUSPECT[/bold red]",
                "DEAD": "[bold red]○ DEAD[/bold red]",
                "INIT": "[dim]◌ INIT[/dim]"
            }
            status_txt = status_map.get(status, f"[dim]{status}[/dim]")

            # Contador de suspeito
            suspect_txt = f"[yellow]{suspect}/{SUSPECT_COUNT_LIMIT}[/yellow]" if suspect > 0 else "[dim]0[/dim]"

            # Destaca se está sendo verificado
            if name == self.checking_instance:
                name = f"[bold cyan]→ {name}[/bold cyan]"

            table.add_row(name, cpu_txt, net_txt, status_txt, suspect_txt)

        # Status do sistema
        auto_key = "[green]ON[/green]" if CONFIG.get("auto_key", True) else "[red]OFF[/red]"
        table.add_row("", "", "", "", "")
        table.add_row("[bright_red]🔑 AUTO-KEY[/bright_red]", "", "", auto_key, "")

        layout["main"].update(Panel(table, title="[bold white on red] MONITOR PASSIVO [/bold white on red]", 
                                   border_style="bright_red", box=DOUBLE))

        # Logs
        log_text = "\n".join(self.logs) if self.logs else "[dim]Aguardando eventos...[/dim]"
        layout["logs"].update(Panel(log_text, title="[bold white on red] LOGS [/bold white on red]", 
                                   border_style="red", box=ROUNDED))

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
    [white]                   v9.0 PRO FOCUS LOCK by MSA[/white]"""
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
            Panel("[bold white][1] 🚀 INICIAR MONITOR[/bold white]\n[dim]Passivo + Focus Lock[/dim]", border_style="bright_red"),
            Panel("[bold white][2] ⚙️ CONFIGURAÇÕES[/bold white]", border_style="red")
        )
        menu.add_row(
            Panel("[bold white][3] 🔑 BYPASS MANUAL[/bold white]\n[dim]Verificar keys agora[/dim]", border_style="red"),
            Panel("[bold white][4] 🛠️ FERRAMENTAS[/bold white]", border_style="red")
        )
        menu.add_row(
            Panel("[bold white][0] ❌ SAIR[/bold white]", border_style="dark_red"),
            Panel("[dim]RE_PHONE v9.0 PRO by MSA[/dim]", border_style="dark_red")
        )
        rprint(menu)

        choice = Prompt.ask("\n[bold bright_red]Selecione[/bold bright_red]", choices=["1", "2", "3", "4", "0"])

        if choice == "1":
            monitor.start()
        elif choice == "2":
            config_menu()
        elif choice == "3":
            manual_bypass()
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
        rprint(f"[green]Auto-Key {'ATIVADO' if CONFIG['auto_key'] else 'DESATIVADO'}![/green]")
        time.sleep(1)

def manual_bypass():
    """Executa bypass manual em todos os pacotes"""
    console.clear()
    rprint(Panel("[bold]BYPASS MANUAL DE KEY[/bold]", border_style="bright_red"))
    
    pkgs = get_packages()
    if not pkgs:
        rprint("[red]Nenhum pacote Roblox encontrado![/red]")
        Prompt.ask("Enter para voltar")
        return

    rprint(f"[yellow]Verificando {len(pkgs)} pacotes (um por vez)...[/yellow]\n")
    
    bypass = DeltaKeyBypass(lambda x: rprint(x))
    
    for pkg in pkgs:
        name = pkg.split('.')[-1].upper()
        rprint(f"\n[bright_red]═══ {name} ═══[/bright_red]")
        
        # Traz para foco
        rprint(f"[dim]Trazendo para foco...[/dim]")
        bring_to_focus(pkg)
        time.sleep(1)
        
        # Captura UI
        xml = get_ui_xml()
        
        # Verifica e processa
        if detect_key_screen(xml):
            bypass.process(pkg, xml)
        else:
            rprint(f"[blue]✓ {name} não precisa de key[/blue]")
        
        time.sleep(FOCUS_DELAY)
    
    rprint("\n[bold green]Verificação concluída![/bold green]")
    Prompt.ask("Enter para voltar")

def tools_menu():
    console.clear()
    rprint(Panel("[bold]FERRAMENTAS[/bold]", border_style="bright_red"))
    
    rprint("[1] Forçar Modo Retrato")
    rprint("[2] Parar Todos os Roblox")
    rprint("[3] Listar Pacotes")
    rprint("[4] Testar ADB")
    rprint("[5] Trazer Janela para Foco")
    rprint("[6] Ver UI Atual (Debug)")
    rprint("[7] Iniciar Todos os Roblox")
    rprint("[0] Voltar")
    
    opt = Prompt.ask("Opção", choices=["1", "2", "3", "4", "5", "6", "7", "0"])
    
    if opt == "1":
        force_portrait()
        rprint("[green]Modo retrato ativado![/green]")
        time.sleep(1)
    
    elif opt == "2":
        for p in get_packages():
            stop_app(p)
            rprint(f"[red]Parado: {p.split('.')[-1]}[/red]")
        time.sleep(1)
    
    elif opt == "3":
        pkgs = get_packages()
        for i, p in enumerate(pkgs, 1):
            pid = get_pid(p)
            cpu = get_cpu(pid) if pid else 0
            rprint(f"[green]{i}. {p}[/green] [dim](PID: {pid or 'N/A'}, CPU: {cpu:.1f}%)[/dim]")
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
            bring_to_focus(pkg)
            rprint(f"[green]Janela trazida para foco![/green]")
        except:
            rprint("[red]Índice inválido[/red]")
        time.sleep(2)
    
    elif opt == "6":
        rprint("[yellow]Capturando UI...[/yellow]")
        xml = get_ui_xml()
        texts = re.findall(r'text="([^"]+)"', xml)
        rprint(f"\n[bold]Textos encontrados:[/bold]")
        for t in texts[:25]:
            if t.strip():
                rprint(f"  • {t}")
        Prompt.ask("\nEnter para voltar")
    
    elif opt == "7":
        vip = CONFIG.get("vip_link", "")
        if not vip:
            rprint("[red]Configure o VIP Link primeiro![/red]")
        else:
            for p in get_packages():
                start_app_with_vip(p, vip)
                rprint(f"[green]Iniciado: {p.split('.')[-1]}[/green]")
                time.sleep(1)
        time.sleep(1)

if __name__ == "__main__":
    main_menu()
