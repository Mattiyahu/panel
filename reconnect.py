#!/usr/bin/env python3
"""
RE_PHONE RETRO EDITION 🌸
Sistema de Monitoramento para Roblox - VSPhone

Tema: Gradiente Vermelho → Rosa (Retro/Synthwave)
Funcionalidades:
- Detecção de tela de key via CPU/RAM
- Envio de screenshot via webhook quando detectar key
- Configuração simples: apenas webhook e link do servidor
"""
import os
import subprocess
import time
import requests
import datetime
import json
import threading
import re
import base64
from io import BytesIO

# ═══════════════════════════════════════════════════════════════════
# CORES DO TEMA RETRO (Vermelho → Rosa)
# ═══════════════════════════════════════════════════════════════════
class Colors:
    # Gradiente Vermelho → Rosa
    RED = "\033[38;5;196m"
    RED_LIGHT = "\033[38;5;197m"
    PINK = "\033[38;5;198m"
    PINK_LIGHT = "\033[38;5;199m"
    MAGENTA = "\033[38;5;200m"
    MAGENTA_LIGHT = "\033[38;5;201m"
    HOT_PINK = "\033[38;5;205m"
    ROSE = "\033[38;5;211m"
    
    # Extras
    WHITE = "\033[97m"
    GRAY = "\033[90m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    
    # Estilos
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"
    
    # Backgrounds
    BG_RED = "\033[48;5;196m"
    BG_PINK = "\033[48;5;198m"
    BG_MAGENTA = "\033[48;5;200m"

C = Colors()

# ═══════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES
# ═══════════════════════════════════════════════════════════════════
CONFIG_FILE = "config_retro.json"

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
# CONSTANTES DE MONITORAMENTO
# ═══════════════════════════════════════════════════════════════════
# Quando está jogando: CPU alta, RAM estável
# Quando está na tela de key: CPU baixa, RAM baixa/estável
CPU_PLAYING = 20.0          # CPU acima disso = jogando
CPU_KEY_SCREEN = 5.0        # CPU abaixo disso = possível tela de key
RAM_PLAYING = 500           # RAM em MB quando jogando (aproximado)
RAM_KEY_SCREEN = 200        # RAM em MB na tela de key (aproximado)

CHECK_INTERVAL = 3          # Segundos entre verificações
KEY_DETECT_COUNT = 3        # Quantas verificações com CPU baixa para considerar tela de key

# ═══════════════════════════════════════════════════════════════════
# FUNÇÕES ADB
# ═══════════════════════════════════════════════════════════════════
def adb(cmd, timeout=5):
    """Executa comando ADB"""
    try:
        return subprocess.check_output(
            f"adb shell {cmd}", 
            shell=True, 
            stderr=subprocess.DEVNULL, 
            timeout=timeout
        ).decode().strip()
    except: 
        return ""

def get_packages():
    """Obtém pacotes Roblox instalados"""
    out = adb("pm list packages roblox")
    return [l.replace("package:", "").strip() for l in out.splitlines() if "roblox" in l.lower()]

def get_pid(pkg):
    """Obtém PID de um pacote"""
    return adb(f"pidof {pkg}")

def get_cpu(pid):
    """Obtém uso de CPU"""
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

def get_ram(pid):
    """Obtém uso de RAM em MB"""
    if not pid:
        return 0
    try:
        out = adb(f"dumpsys meminfo {pid} | grep 'TOTAL'")
        match = re.search(r'TOTAL\s+(\d+)', out)
        if match:
            return int(match.group(1)) // 1024  # KB para MB
    except:
        pass
    return 0

def take_screenshot():
    """Captura screenshot e retorna como bytes"""
    try:
        # Captura screenshot
        adb("screencap -p /sdcard/screen.png")
        time.sleep(0.5)
        
        # Puxa o arquivo
        subprocess.run("adb pull /sdcard/screen.png /tmp/screen.png", 
                      shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        
        # Lê o arquivo
        with open("/tmp/screen.png", "rb") as f:
            return f.read()
    except:
        return None

def send_webhook_with_screenshot(webhook_url, message, screenshot_bytes=None):
    """Envia mensagem para webhook com screenshot"""
    if not webhook_url:
        return False
    
    try:
        # Prepara o payload
        payload = {
            "content": message,
            "username": "RE_PHONE RETRO 🌸",
        }
        
        files = None
        if screenshot_bytes:
            files = {
                "file": ("screenshot.png", BytesIO(screenshot_bytes), "image/png")
            }
        
        # Envia
        if files:
            response = requests.post(webhook_url, data={"content": message}, files=files, timeout=10)
        else:
            response = requests.post(webhook_url, json=payload, timeout=10)
        
        return response.status_code in [200, 204]
    except Exception as e:
        return False

# ═══════════════════════════════════════════════════════════════════
# ARTE ASCII RETRO
# ═══════════════════════════════════════════════════════════════════
def print_banner():
    """Imprime banner com gradiente vermelho → rosa"""
    banner = f"""
{C.RED}██████╗ {C.RED_LIGHT}███████╗{C.PINK}      ██████╗ {C.PINK_LIGHT}██╗  ██╗{C.MAGENTA} ██████╗ {C.MAGENTA_LIGHT}███╗   ██╗{C.HOT_PINK}███████╗
{C.RED}██╔══██╗{C.RED_LIGHT}██╔════╝{C.PINK}      ██╔══██╗{C.PINK_LIGHT}██║  ██║{C.MAGENTA}██╔═══██╗{C.MAGENTA_LIGHT}████╗  ██║{C.HOT_PINK}██╔════╝
{C.RED}██████╔╝{C.RED_LIGHT}█████╗  {C.PINK}█████╗██████╔╝{C.PINK_LIGHT}███████║{C.MAGENTA}██║   ██║{C.MAGENTA_LIGHT}██╔██╗ ██║{C.HOT_PINK}█████╗  
{C.RED}██╔══██╗{C.RED_LIGHT}██╔══╝  {C.PINK}╚════╝██╔═══╝ {C.PINK_LIGHT}██╔══██║{C.MAGENTA}██║   ██║{C.MAGENTA_LIGHT}██║╚██╗██║{C.HOT_PINK}██╔══╝  
{C.RED}██║  ██║{C.RED_LIGHT}███████╗{C.PINK}      ██║     {C.PINK_LIGHT}██║  ██║{C.MAGENTA}╚██████╔╝{C.MAGENTA_LIGHT}██║ ╚████║{C.HOT_PINK}███████╗
{C.RED}╚═╝  ╚═╝{C.RED_LIGHT}╚══════╝{C.PINK}      ╚═╝     {C.PINK_LIGHT}╚═╝  ╚═╝{C.MAGENTA} ╚═════╝ {C.MAGENTA_LIGHT}╚═╝  ╚═══╝{C.HOT_PINK}╚══════╝{C.RESET}
{C.ROSE}                    ✧ RETRO EDITION ✧{C.RESET}
{C.GRAY}              Synthwave Monitor for VSPhone{C.RESET}
"""
    print(banner)

def print_gradient_line(char="═", length=60):
    """Imprime linha com gradiente"""
    colors = [C.RED, C.RED_LIGHT, C.PINK, C.PINK_LIGHT, C.MAGENTA, C.MAGENTA_LIGHT, C.HOT_PINK, C.ROSE]
    segment = length // len(colors)
    line = ""
    for i, color in enumerate(colors):
        line += f"{color}{char * segment}"
    print(line + C.RESET)

def print_box(title, content, width=60):
    """Imprime caixa estilizada"""
    print(f"\n{C.RED}╔{'═' * (width-2)}╗{C.RESET}")
    print(f"{C.RED_LIGHT}║{C.RESET} {C.BOLD}{C.PINK}{title.center(width-4)}{C.RESET} {C.RED_LIGHT}║{C.RESET}")
    print(f"{C.PINK}╠{'═' * (width-2)}╣{C.RESET}")
    for line in content.split('\n'):
        print(f"{C.PINK_LIGHT}║{C.RESET} {line.ljust(width-4)} {C.PINK_LIGHT}║{C.RESET}")
    print(f"{C.MAGENTA}╚{'═' * (width-2)}╝{C.RESET}")

# ═══════════════════════════════════════════════════════════════════
# CLASSE DE INSTÂNCIA
# ═══════════════════════════════════════════════════════════════════
class Instance:
    def __init__(self, pkg):
        self.pkg = pkg
        self.name = pkg.split('.')[-1].upper()
        self.pid = ""
        self.cpu = 0.0
        self.ram = 0
        self.status = "INIT"
        self.low_cpu_count = 0  # Contador de CPU baixa consecutiva
        self.key_detected = False
        self.last_key_time = 0
    
    def update_metrics(self):
        """Atualiza métricas de CPU e RAM"""
        self.pid = get_pid(self.pkg)
        
        if not self.pid:
            self.status = "DEAD"
            self.cpu = 0.0
            self.ram = 0
            return
        
        self.cpu = get_cpu(self.pid)
        self.ram = get_ram(self.pid)
        
        # Detecta estado baseado em CPU/RAM
        if self.cpu >= CPU_PLAYING:
            self.status = "PLAYING"
            self.low_cpu_count = 0
            self.key_detected = False
        elif self.cpu <= CPU_KEY_SCREEN:
            self.low_cpu_count += 1
            if self.low_cpu_count >= KEY_DETECT_COUNT:
                self.status = "KEY?"
                if not self.key_detected:
                    self.key_detected = True
                    self.last_key_time = time.time()
            else:
                self.status = "LOW"
        else:
            self.status = "IDLE"
            self.low_cpu_count = max(0, self.low_cpu_count - 1)

# ═══════════════════════════════════════════════════════════════════
# MONITOR PRINCIPAL
# ═══════════════════════════════════════════════════════════════════
class RetroMonitor:
    def __init__(self):
        self.instances = {}
        self.running = False
        self.logs = []
    
    def log(self, msg):
        """Adiciona log com timestamp"""
        t = datetime.datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{t}] {msg}")
        if len(self.logs) > 8:
            self.logs.pop(0)
    
    def clear_screen(self):
        """Limpa a tela"""
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def render_hud(self):
        """Renderiza o HUD retro"""
        self.clear_screen()
        print_banner()
        print_gradient_line()
        
        # Status das instâncias
        print(f"\n{C.BOLD}{C.PINK}  ◈ INSTÂNCIAS{C.RESET}")
        print(f"{C.GRAY}  {'─' * 56}{C.RESET}")
        
        for pkg, inst in self.instances.items():
            # Ícone de status
            if inst.status == "PLAYING":
                icon = f"{C.GREEN}▶{C.RESET}"
                status_color = C.GREEN
            elif inst.status == "KEY?":
                icon = f"{C.YELLOW}🔑{C.RESET}"
                status_color = C.YELLOW
            elif inst.status == "DEAD":
                icon = f"{C.RED}✖{C.RESET}"
                status_color = C.RED
            elif inst.status == "LOW":
                icon = f"{C.YELLOW}◐{C.RESET}"
                status_color = C.YELLOW
            else:
                icon = f"{C.GRAY}◌{C.RESET}"
                status_color = C.GRAY
            
            # CPU com cor gradiente
            if inst.cpu >= CPU_PLAYING:
                cpu_color = C.GREEN
            elif inst.cpu >= CPU_KEY_SCREEN:
                cpu_color = C.YELLOW
            else:
                cpu_color = C.RED
            
            # RAM
            ram_str = f"{inst.ram}MB" if inst.ram > 0 else "N/A"
            
            print(f"  {icon} {C.BOLD}{C.ROSE}{inst.name:12}{C.RESET} "
                  f"{C.GRAY}│{C.RESET} CPU: {cpu_color}{inst.cpu:5.1f}%{C.RESET} "
                  f"{C.GRAY}│{C.RESET} RAM: {C.CYAN}{ram_str:8}{C.RESET} "
                  f"{C.GRAY}│{C.RESET} {status_color}{inst.status:8}{C.RESET}")
        
        print(f"{C.GRAY}  {'─' * 56}{C.RESET}")
        
        # Legenda
        print(f"\n{C.DIM}  {C.GREEN}▶ Jogando{C.RESET}  {C.DIM}{C.YELLOW}🔑 Tela de Key{C.RESET}  {C.DIM}{C.RED}✖ Morto{C.RESET}")
        
        # Logs
        print(f"\n{C.BOLD}{C.MAGENTA}  ◈ LOGS{C.RESET}")
        print(f"{C.GRAY}  {'─' * 56}{C.RESET}")
        for log in self.logs[-6:]:
            print(f"  {C.DIM}{log}{C.RESET}")
        
        # Rodapé
        print(f"\n{C.GRAY}  {'─' * 56}{C.RESET}")
        print(f"  {C.DIM}Pressione Ctrl+C para sair{C.RESET}")
    
    def check_for_key_screen(self, inst):
        """Verifica se instância está na tela de key e envia webhook"""
        if inst.key_detected and (time.time() - inst.last_key_time) < 5:
            self.log(f"🔑 {inst.name}: Possível tela de KEY detectada!")
            
            webhook = CONFIG.get("webhook_url", "")
            if webhook:
                self.log(f"📸 Capturando screenshot...")
                screenshot = take_screenshot()
                
                message = f"🔑 **{inst.name}** - Possível tela de KEY detectada!\n" \
                         f"CPU: {inst.cpu:.1f}% | RAM: {inst.ram}MB"
                
                if send_webhook_with_screenshot(webhook, message, screenshot):
                    self.log(f"✅ Screenshot enviado para webhook!")
                else:
                    self.log(f"❌ Falha ao enviar webhook")
            
            # Reseta para não enviar múltiplas vezes
            inst.last_key_time = 0
    
    def monitor_worker(self, inst):
        """Worker de monitoramento para uma instância"""
        while self.running:
            inst.update_metrics()
            self.check_for_key_screen(inst)
            time.sleep(CHECK_INTERVAL)
    
    def start(self):
        """Inicia o monitor"""
        webhook = CONFIG.get("webhook_url", "")
        server = CONFIG.get("server_link", "")
        
        if not webhook:
            print(f"\n{C.RED}⚠ Configure o Webhook primeiro!{C.RESET}")
            time.sleep(2)
            return
        
        self.running = True
        pkgs = get_packages()
        
        if not pkgs:
            print(f"\n{C.RED}⚠ Nenhum pacote Roblox encontrado!{C.RESET}")
            time.sleep(2)
            return
        
        self.log(f"Iniciando monitor com {len(pkgs)} instâncias")
        
        # Cria instâncias
        for pkg in pkgs:
            inst = Instance(pkg)
            self.instances[pkg] = inst
            threading.Thread(target=self.monitor_worker, args=(inst,), daemon=True).start()
            self.log(f"+ {inst.name} monitorando")
        
        # Envia webhook de início
        send_webhook_with_screenshot(webhook, f"🚀 **RE_PHONE RETRO** iniciado!\nMonitorando {len(pkgs)} instâncias")
        
        # Loop de renderização
        try:
            while self.running:
                self.render_hud()
                time.sleep(1)
        except KeyboardInterrupt:
            self.running = False
            print(f"\n{C.YELLOW}Monitor encerrado.{C.RESET}")

monitor = RetroMonitor()

# ═══════════════════════════════════════════════════════════════════
# MENU PRINCIPAL
# ═══════════════════════════════════════════════════════════════════
def main_menu():
    while True:
        os.system('clear' if os.name == 'posix' else 'cls')
        print_banner()
        print_gradient_line()
        
        # Status atual
        webhook_ok = "✓" if CONFIG.get("webhook_url") else "✗"
        server_ok = "✓" if CONFIG.get("server_link") else "✗"
        
        webhook_color = C.GREEN if webhook_ok == "✓" else C.RED
        server_color = C.GREEN if server_ok == "✓" else C.RED
        
        print(f"\n  {C.GRAY}Status:{C.RESET}")
        print(f"  {C.PINK}Webhook:{C.RESET} {webhook_color}{webhook_ok}{C.RESET}  "
              f"{C.PINK}Server:{C.RESET} {server_color}{server_ok}{C.RESET}")
        
        # Menu
        print(f"\n{C.BOLD}{C.ROSE}  ╔══════════════════════════════════════╗{C.RESET}")
        print(f"{C.BOLD}{C.ROSE}  ║{C.RESET}  {C.RED}[1]{C.RESET} {C.WHITE}🚀 Iniciar Monitor{C.RESET}              {C.BOLD}{C.ROSE}║{C.RESET}")
        print(f"{C.BOLD}{C.ROSE}  ║{C.RESET}  {C.PINK}[2]{C.RESET} {C.WHITE}🔗 Configurar Webhook{C.RESET}           {C.BOLD}{C.ROSE}║{C.RESET}")
        print(f"{C.BOLD}{C.ROSE}  ║{C.RESET}  {C.MAGENTA}[3]{C.RESET} {C.WHITE}🌐 Configurar Link do Servidor{C.RESET}  {C.BOLD}{C.ROSE}║{C.RESET}")
        print(f"{C.BOLD}{C.ROSE}  ║{C.RESET}  {C.HOT_PINK}[4]{C.RESET} {C.WHITE}📸 Testar Screenshot + Webhook{C.RESET}  {C.BOLD}{C.ROSE}║{C.RESET}")
        print(f"{C.BOLD}{C.ROSE}  ║{C.RESET}  {C.GRAY}[0]{C.RESET} {C.WHITE}❌ Sair{C.RESET}                         {C.BOLD}{C.ROSE}║{C.RESET}")
        print(f"{C.BOLD}{C.ROSE}  ╚══════════════════════════════════════╝{C.RESET}")
        
        choice = input(f"\n  {C.PINK}Selecione:{C.RESET} ").strip()
        
        if choice == "1":
            monitor.start()
        elif choice == "2":
            print(f"\n  {C.CYAN}Cole o URL do Webhook:{C.RESET}")
            webhook = input(f"  {C.GRAY}>{C.RESET} ").strip()
            if webhook:
                CONFIG["webhook_url"] = webhook
                save_config(CONFIG)
                print(f"  {C.GREEN}✓ Webhook salvo!{C.RESET}")
                time.sleep(1)
        elif choice == "3":
            print(f"\n  {C.CYAN}Cole o Link do Servidor (VIP):{C.RESET}")
            server = input(f"  {C.GRAY}>{C.RESET} ").strip()
            if server:
                CONFIG["server_link"] = server
                save_config(CONFIG)
                print(f"  {C.GREEN}✓ Link salvo!{C.RESET}")
                time.sleep(1)
        elif choice == "4":
            print(f"\n  {C.YELLOW}Capturando screenshot...{C.RESET}")
            screenshot = take_screenshot()
            webhook = CONFIG.get("webhook_url", "")
            
            if not webhook:
                print(f"  {C.RED}⚠ Configure o webhook primeiro!{C.RESET}")
            elif screenshot:
                if send_webhook_with_screenshot(webhook, "🧪 **Teste de Screenshot**\nSe você está vendo isso, funcionou!", screenshot):
                    print(f"  {C.GREEN}✓ Screenshot enviado com sucesso!{C.RESET}")
                else:
                    print(f"  {C.RED}✗ Falha ao enviar screenshot{C.RESET}")
            else:
                print(f"  {C.RED}✗ Falha ao capturar screenshot{C.RESET}")
            
            input(f"\n  {C.GRAY}Pressione Enter para continuar...{C.RESET}")
        elif choice == "0":
            print(f"\n  {C.ROSE}Até mais! ✧{C.RESET}\n")
            break

if __name__ == "__main__":
    main_menu()
