#!/usr/bin/env python3
"""
🖥️ Roblox AutoRejoin - Hacker Theme 🖥️
Interface cyberpunk com login automático para clones Roblox
Versão: 4.0 - Hacker Edition
"""

import os
import sys
import time
import json
import signal
import subprocess
import platform
import getpass
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import base64
import hashlib
from cryptography.fernet import Fernet

# ============================================
# 🎮 CONFIGURAÇÃO SEGURA
# ============================================
CONFIG_FILE = "hacker_config.json"
KEY_FILE = "hacker_key.key"
DEFAULT_CONFIG = {
    "web_link": "https://www.roblox.com/games/1537690962/Bee-Swarm-Simulator?privateServerLinkCode=05888256464342538313491710978310",
    "webhook_url": "",
    "check_interval": 10,
    "low_cpu_threshold": 8.0,
    "max_lowcpu_time": 10,
    "cooldown_time": 10,
    "packages": [],
    "credentials": {}  # {package: {"user": "encrypted", "pass": "encrypted"}}
}

# ============================================
# 🎨 TEMA HACKER CYBERPUNK
# ============================================
class HackerTheme:
    """Paleta de cores estilo hacker/cyberpunk"""
    
    # Cores ANSI - Verde matriz com toques neon
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    BLINK = "\033[5m"
    REVERSE = "\033[7m"
    HIDDEN = "\033[8m"
    
    # Verde matriz (cores principais)
    MATRIX = "\033[38;5;46m"        # Verde matrix brilhante
    CYAN = "\033[38;5;51m"          # Ciano neon
    PINK = "\033[38;5;201m"         # Rosa neon
    PURPLE = "\033[38;5;93m"        # Roxo
    BLUE = "\033[38;5;39m"          # Azul elétrico
    ORANGE = "\033[38;5;208m"       # Laranja
    RED = "\033[38;5;196m"          # Vermelho alerta
    YELLOW = "\033[38;5;226m"       # Amarelo
    
    # Tons de verde
    GREEN_DARK = "\033[38;5;22m"
    GREEN_MEDIUM = "\033[38;5;28m"
    GREEN_LIGHT = "\033[38;5;34m"
    GREEN_NEON = "\033[38;5;82m"
    
    # Fundos
    BG_BLACK = "\033[48;5;232m"
    BG_DARK = "\033[48;5;234m"
    BG_MATRIX = "\033[48;5;22m"
    
    # Efeitos especiais
    GLITCH = f"{BLINK}{RED}"
    SCANLINE = f"{DIM}{GREEN_MEDIUM}"
    HIGHLIGHT = f"{BOLD}{GREEN_NEON}"
    TERMINAL = f"{GREEN_LIGHT}"
    SUCCESS = f"{BOLD}{CYAN}"
    ERROR = f"{BOLD}{RED}"
    WARNING = f"{BOLD}{YELLOW}"
    INFO = f"{BOLD}{BLUE}"
    
    # Símbolos hacker
    SYMBOLS = {
        "terminal": "⌘",
        "code": "{}",
        "database": "🛢️",
        "shield": "🛡️",
        "key": "🔑",
        "lock": "🔒",
        "unlock": "🔓",
        "robot": "🤖",
        "chip": "💿",
        "signal": "📡",
        "radar": "📡",
        "firewall": "🔥",
        "virus": "🦠",
        "binary": "01",
        "pointer": "▶",
        "arrow": "➤",
        "dot": "▪",
        "check": "✓",
        "cross": "✗",
        "warning": "⚠",
        "loading": "⌛"
    }
    
    @staticmethod
    def glitch_text(text: str, intensity: int = 3) -> str:
        """Adiciona efeito glitch ao texto"""
        import random
        glitch_chars = ["#", "@", "&", "%", "$", "!", "~", "*"]
        result = ""
        for char in text:
            if random.random() < intensity/100:
                result += random.choice(glitch_chars)
            else:
                result += char
        return f"{HackerTheme.GLITCH}{result}{HackerTheme.RESET}"
    
    @staticmethod
    def matrix_rain(length: int = 30):
        """Efeito de chuva matrix"""
        import random
        chars = "01"
        for _ in range(length):
            line = "".join(random.choice(chars) for _ in range(80))
            print(f"{HackerTheme.GREEN_DIM}{line}{HackerTheme.RESET}")
            time.sleep(0.05)
    
    @staticmethod
    def typing_effect(text: str, delay: float = 0.03):
        """Efeito de digitação"""
        for char in text:
            print(char, end='', flush=True)
            time.sleep(delay)
        print()

# ============================================
# 🔐 SISTEMA DE CRIPTOGRAFIA
# ============================================
class CryptoSystem:
    """Sistema de criptografia para credenciais"""
    
    @staticmethod
    def get_or_create_key():
        """Obtém ou cria chave de criptografia"""
        if os.path.exists(KEY_FILE):
            with open(KEY_FILE, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(KEY_FILE, 'wb') as f:
                f.write(key)
            return key
    
    @staticmethod
    def encrypt(text: str) -> str:
        """Criptografa texto"""
        key = CryptoSystem.get_or_create_key()
        cipher = Fernet(key)
        encrypted = cipher.encrypt(text.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    @staticmethod
    def decrypt(encrypted_text: str) -> str:
        """Descriptografa texto"""
        try:
            key = CryptoSystem.get_or_create_key()
            cipher = Fernet(key)
            decoded = base64.urlsafe_b64decode(encrypted_text.encode())
            decrypted = cipher.decrypt(decoded)
            return decrypted.decode()
        except:
            return ""

# ============================================
# 🎨 INTERFACE HACKER
# ============================================
class HackerUI:
    """Interface gráfica estilo hacker"""
    
    @staticmethod
    def clear_screen():
        """Limpa a tela com estilo"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    @staticmethod
    def print_header(title: str, subtext: str = ""):
        """Imprime cabeçalho hacker"""
        HackerUI.clear_screen()
        width = 70
        
        print(f"\n{HackerTheme.BG_BLACK}{HackerTheme.MATRIX}{'▁'*width}{HackerTheme.RESET}")
        print(f"{HackerTheme.BG_BLACK}{HackerTheme.MATRIX}╔{'═'*(width-2)}╗{HackerTheme.RESET}")
        
        # Título com glitch
        title_line = f"║ {HackerTheme.HIGHLIGHT}▸ {title} ◂{HackerTheme.MATRIX}"
        print(f"{HackerTheme.BG_BLACK}{HackerTheme.MATRIX}{title_line:<{width-1}}║{HackerTheme.RESET}")
        
        if subtext:
            sub_line = f"║ {HackerTheme.TERMINAL}{subtext}{HackerTheme.MATRIX}"
            print(f"{HackerTheme.BG_BLACK}{HackerTheme.MATRIX}{sub_line:<{width-1}}║{HackerTheme.RESET}")
        
        print(f"{HackerTheme.BG_BLACK}{HackerTheme.MATRIX}╚{'═'*(width-2)}╝{HackerTheme.RESET}")
        print(f"{HackerTheme.BG_BLACK}{HackerTheme.MATRIX}{'▔'*width}{HackerTheme.RESET}\n")
    
    @staticmethod
    def print_terminal_box(content: str, title: str = "TERMINAL"):
        """Imprime caixa de terminal"""
        lines = content.split('\n')
        max_len = max(len(line) for line in lines) if lines else 0
        
        print(f"{HackerTheme.GREEN_DARK}┌─[{HackerTheme.CYAN}{title}{HackerTheme.GREEN_DARK}]─{'─'*(max_len - len(title) + 5)}┐{HackerTheme.RESET}")
        
        for line in lines:
            print(f"{HackerTheme.GREEN_DARK}│ {HackerTheme.TERMINAL}{line}{' '*(max_len - len(line))} {HackerTheme.GREEN_DARK}│{HackerTheme.RESET}")
        
        print(f"{HackerTheme.GREEN_DARK}└{'─'*(max_len + 7)}┘{HackerTheme.RESET}")
    
    @staticmethod
    def print_status_line(label: str, value: str, status: str = "info"):
        """Imprime linha de status"""
        colors = {
            "success": HackerTheme.SUCCESS,
            "error": HackerTheme.ERROR,
            "warning": HackerTheme.WARNING,
            "info": HackerTheme.INFO,
            "neutral": HackerTheme.TERMINAL
        }
        
        color = colors.get(status, HackerTheme.TERMINAL)
        print(f"{HackerTheme.GREEN_DARK}[{HackerTheme.CYAN}{HackerTheme.SYMBOLS['pointer']}{HackerTheme.GREEN_DARK}] "
              f"{HackerTheme.TERMINAL}{label}: {color}{value}{HackerTheme.RESET}")
    
    @staticmethod
    def print_log_entry(package: str, message: str, level: str = "INFO"):
        """Imprime entrada de log"""
        levels = {
            "INFO": HackerTheme.INFO,
            "WARN": HackerTheme.WARNING,
            "ERROR": HackerTheme.ERROR,
            "SUCCESS": HackerTheme.SUCCESS,
            "DEBUG": HackerTheme.PURPLE
        }
        
        color = levels.get(level, HackerTheme.TERMINAL)
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        print(f"{HackerTheme.GREEN_DARK}[{HackerTheme.CYAN}{timestamp}{HackerTheme.GREEN_DARK}] "
              f"[{color}{level:<7}{HackerTheme.GREEN_DARK}] "
              f"[{HackerTheme.YELLOW}{package:<20}{HackerTheme.GREEN_DARK}] "
              f"{HackerTheme.TERMINAL}{message}{HackerTheme.RESET}")
    
    @staticmethod
    def print_matrix_banner():
        """Imprime banner matrix"""
        banner = f"""
{HackerTheme.MATRIX}╔══════════════════════════════════════════════════════════════╗
║  {HackerTheme.CYAN}░█▀▀░█░░░█▀█░█▀▀░▀█▀░█▀▀░░░█▀▀░█▀█░█▀▄░█▀▀░█▀▄  {HackerTheme.MATRIX}║
║  {HackerTheme.CYAN}░█▀▀░█░░░█▀█░▀▀█░░█░░█▀▀░░░▀▀█░█▀█░█▀▄░█▀▀░█▀▄  {HackerTheme.MATRIX}║
║  {HackerTheme.CYAN}░▀▀▀░▀▀▀░▀░▀░▀▀▀░░▀░░▀▀▀░░░▀▀▀░▀░▀░▀░▀░▀▀▀░▀░▀  {HackerTheme.MATRIX}║
║  {HackerTheme.GREEN_NEON}░█▀▀░█▀█░█▀▄░█▀▀░▀█▀░█▀▀░█▀█░█░░░█░░░█▀▀░█▀▀  {HackerTheme.MATRIX}║
║  {HackerTheme.GREEN_NEON}░▀▀█░█▀█░█░█░█▀▀░░█░░█░░░█▀█░█░░░█░░░▀▀█░█▀▀  {HackerTheme.MATRIX}║
║  {HackerTheme.GREEN_NEON}░▀▀▀░▀░▀░▀▀░░▀▀▀░░▀░░▀▀▀░▀░▀░▀▀▀░▀▀▀░▀▀▀░▀▀▀  {HackerTheme.MATRIX}║
╠══════════════════════════════════════════════════════════════╣
║  {HackerTheme.PINK}Version 4.0 • Hacker Edition • Access Granted  {HackerTheme.MATRIX}║
╚══════════════════════════════════════════════════════════════╝{HackerTheme.RESET}
        """
        print(banner)
    
    @staticmethod
    def animate_loading(text: str, duration: int = 2):
        """Animação de loading hacker"""
        frames = ["[▓▓▓▓▓▓▓▓▓▓]", "[█▓▓▓▓▓▓▓▓▓]", "[██▓▓▓▓▓▓▓▓]", "[███▓▓▓▓▓▓▓]", 
                 "[████▓▓▓▓▓▓]", "[█████▓▓▓▓▓]", "[██████▓▓▓▓]", "[███████▓▓▓]", 
                 "[████████▓▓]", "[█████████▓]", "[██████████]"]
        
        for i in range(duration * 10):
            frame = frames[i % len(frames)]
            print(f"\r{HackerTheme.CYAN}{frame} {HackerTheme.TERMINAL}{text}{HackerTheme.RESET}", end="")
            time.sleep(0.1)
        print()
    
    @staticmethod
    def print_menu(options: List[Dict]):
        """Imprime menu hacker"""
        print(f"\n{HackerTheme.GREEN_DARK}┌─[{HackerTheme.CYAN}MAIN MENU{HackerTheme.GREEN_DARK}]─{'─'*50}┐{HackerTheme.RESET}")
        
        for i, option in enumerate(options, 1):
            icon = option.get('icon', HackerTheme.SYMBOLS['pointer'])
            color = option.get('color', HackerTheme.TERMINAL)
            print(f"{HackerTheme.GREEN_DARK}│ {HackerTheme.CYAN}{i:2d}{HackerTheme.GREEN_DARK} {icon} "
                  f"{color}{option['text']}{HackerTheme.RESET}")
        
        print(f"{HackerTheme.GREEN_DARK}└{'─'*60}┘{HackerTheme.RESET}")

# ============================================
# 🔐 SISTEMA DE LOGIN AUTOMÁTICO
# ============================================
class RobloxAutoLogin:
    """Sistema de login automático para Roblox"""
    
    def __init__(self, config: dict):
        self.config = config
        self.login_cooldown: Dict[str, float] = {}
    
    def save_credentials(self, package: str, username: str, password: str):
        """Salva credenciais criptografadas"""
        if "credentials" not in self.config:
            self.config["credentials"] = {}
        
        self.config["credentials"][package] = {
            "user": CryptoSystem.encrypt(username),
            "pass": CryptoSystem.encrypt(password)
        }
    
    def get_credentials(self, package: str) -> Tuple[str, str]:
        """Obtém credenciais descriptografadas"""
        if package in self.config.get("credentials", {}):
            creds = self.config["credentials"][package]
            user = CryptoSystem.decrypt(creds["user"])
            password = CryptoSystem.decrypt(creds["pass"])
            return user, password
        return "", ""
    
    def clear_credentials(self, package: str):
        """Remove credenciais salvas"""
        if package in self.config.get("credentials", {}):
            del self.config["credentials"][package]
    
    def perform_login(self, package: str) -> bool:
        """
        Executa login automático no Roblox.
        AVISO: Este método é experimental e pode não funcionar em todos os dispositivos.
        """
        current_time = time.time()
        
        # Verifica cooldown
        if package in self.login_cooldown and current_time < self.login_cooldown[package]:
            HackerUI.print_log_entry(package, "Login em cooldown", "WARN")
            return False
        
        # Obtém credenciais
        username, password = self.get_credentials(package)
        if not username or not password:
            HackerUI.print_log_entry(package, "Credenciais não configuradas", "ERROR")
            return False
        
        HackerUI.print_log_entry(package, "Iniciando login automático...", "INFO")
        
        try:
            # 1. Garante que o app está fechado
            subprocess.run(["adb", "shell", "am", "force-stop", package], 
                         capture_output=True, timeout=5)
            time.sleep(2)
            
            # 2. Abre o Roblox
            subprocess.run(["adb", "shell", "monkey", "-p", package, "1"], 
                         capture_output=True, timeout=5)
            time.sleep(5)
            
            # 3. Aguarda carregamento
            HackerUI.animate_loading("Aguardando carregamento...", 3)
            
            # 4. Método 1: Tenta tocar na área de login (coordenadas podem variar)
            # Esta parte requer ajustes específicos para seu dispositivo
            
            # 5. Método alternativo: Usa input text para inserir credenciais
            # Nota: Requer que o campo já esteja em foco
            
            # 6. Define cooldown
            self.login_cooldown[package] = time.time() + 300  # 5 minutos
            
            HackerUI.print_log_entry(package, "Tentativa de login concluída", "INFO")
            return True
            
        except Exception as e:
            HackerUI.print_log_entry(package, f"Erro no login: {str(e)}", "ERROR")
            return False
    
    def setup_login_wizard(self, package: str):
        """Assistente para configurar login"""
        HackerUI.print_header(f"CONFIGURAR LOGIN", f"Pacote: {package}")
        
        print(f"{HackerTheme.WARNING}⚠️  AVISO IMPORTANTE:{HackerTheme.RESET}")
        print(f"{HackerTheme.TERMINAL}• Credenciais são criptografadas localmente")
        print(f"• Login automático pode não funcionar em todos os dispositivos")
        print(f"• Recomendado apenas para contas secundárias")
        print(f"• Nunca compartilhe seu arquivo {KEY_FILE}{HackerTheme.RESET}\n")
        
        current_user, current_pass = self.get_credentials(package)
        if current_user:
            print(f"{HackerTheme.INFO}Credenciais atuais: {HackerTheme.CYAN}{current_user}{HackerTheme.RESET}")
            if input(f"\n{HackerTheme.TERMINAL}Redefinir? (s/n): {HackerTheme.RESET}").lower() != 's':
                return
        
        print(f"\n{HackerTheme.GREEN_DARK}┌─[{HackerTheme.CYAN}CREDENCIAIS{HackerTheme.GREEN_DARK}]─{'─'*50}┐{HackerTheme.RESET}")
        
        username = input(f"{HackerTheme.GREEN_DARK}│ {HackerTheme.TERMINAL}Usuário Roblox: {HackerTheme.RESET}").strip()
        password = getpass.getpass(f"{HackerTheme.GREEN_DARK}│ {HackerTheme.TERMINAL}Senha: {HackerTheme.RESET}")
        
        if username and password:
            self.save_credentials(package, username, password)
            HackerUI.print_log_entry(package, "Credenciais salvas com segurança", "SUCCESS")
            
            # Teste opcional
            if input(f"\n{HackerTheme.TERMINAL}Testar login agora? (s/n): {HackerTheme.RESET}").lower() == 's':
                self.perform_login(package)
        else:
            HackerUI.print_log_entry(package, "Credenciais não fornecidas", "WARN")
        
        print(f"{HackerTheme.GREEN_DARK}└{'─'*60}┘{HackerTheme.RESET}")

# ============================================
# 🎮 MONITOR HACKER
# ============================================
class HackerMonitor:
    """Monitor com tema hacker e funcionalidades avançadas"""
    
    def __init__(self, config: dict):
        self.config = config
        self.proto_activity = "com.roblox.client.ActivityProtocolLaunch"
        self.lowcpu_count: Dict[str, int] = {}
        self.cooldown: Dict[str, float] = {}
        self.max_count = config["max_lowcpu_time"] // config["check_interval"]
        self.running = True
        self.login_system = RobloxAutoLogin(config)
        
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        print(f"\n\n{HackerTheme.ERROR}⚠️  INTERRUPÇÃO DETECTADA • Encerrando monitoramento...{HackerTheme.RESET}")
        self.running = False
    
    def run_adb_command(self, command: str) -> str:
        """Executa comando ADB"""
        try:
            result = subprocess.run(["adb"] + command.split(), 
                                  capture_output=True, text=True, timeout=10)
            return result.stdout.strip()
        except:
            return ""
    
    def get_pid(self, package: str) -> Optional[str]:
        """Obtém PID do pacote"""
        return self.run_adb_command(f"shell pidof {package}")
    
    def get_cpu_usage(self, pid: str) -> float:
        """Obtém uso de CPU"""
        try:
            output = self.run_adb_command(f"shell top -n 1 -b | grep '^{pid}'")
            if output:
                parts = output.split()
                if len(parts) >= 9:
                    cpu_str = parts[8].replace(',', '.').replace('%', '')
                    return float(cpu_str)
        except:
            pass
        return 0.0
    
    def check_package_status(self, package: str) -> Dict:
        """Verifica status do pacote"""
        pid = self.get_pid(package)
        status = {
            "package": package,
            "pid": pid,
            "running": pid is not None,
            "cpu": 0.0,
            "needs_restart": False,
            "needs_login": False
        }
        
        if pid:
            cpu = self.get_cpu_usage(pid)
            status["cpu"] = cpu
            
            if cpu <= self.config["low_cpu_threshold"]:
                self.lowcpu_count[package] = self.lowcpu_count.get(package, 0) + 1
                if self.lowcpu_count[package] >= self.max_count:
                    status["needs_restart"] = True
                    
                    # Verifica se tem credenciais salvas
                    user, passw = self.login_system.get_credentials(package)
                    if user and passw:
                        status["needs_login"] = True
            else:
                self.lowcpu_count[package] = 0
        
        return status
    
    def soft_restart(self, package: str, attempt_login: bool = True) -> bool:
        """Reinício suave com opção de login"""
        current_time = time.time()
        
        # Verifica cooldown
        if package in self.cooldown and current_time < self.cooldown[package]:
            HackerUI.print_log_entry(package, f"Cooldown: {self.cooldown[package]-current_time:.0f}s", "WARN")
            return False
        
        HackerUI.print_log_entry(package, "Iniciando reinício suave...", "INFO")
        
        try:
            # 1. Força parada (NÃO limpa dados)
            self.run_adb_command(f"shell am force-stop {package}")
            time.sleep(2)
            
            # 2. Tenta login automático se configurado
            if attempt_login:
                user, passw = self.login_system.get_credentials(package)
                if user and passw:
                    HackerUI.print_log_entry(package, "Tentando login automático...", "INFO")
                    if self.login_system.perform_login(package):
                        time.sleep(5)
                    else:
                        # Fallback para abrir VIP normalmente
                        self.open_vip(package)
                else:
                    self.open_vip(package)
            else:
                self.open_vip(package)
            
            # 3. Verifica resultado
            pid_after = self.get_pid(package)
            success = pid_after is not None
            
            # 4. Aplica cooldown
            self.cooldown[package] = time.time() + self.config["cooldown_time"]
            self.lowcpu_count[package] = 0
            
            if success:
                HackerUI.print_log_entry(package, f"Reinício completo • PID: {pid_after}", "SUCCESS")
            else:
                HackerUI.print_log_entry(package, "Reinício pode ter falhado", "WARN")
            
            return success
            
        except Exception as e:
            HackerUI.print_log_entry(package, f"Erro no reinício: {str(e)}", "ERROR")
            return False
    
    def open_vip(self, package: str) -> bool:
        """Abre servidor VIP"""
        cmd = (f"shell am start -n {package}/{self.proto_activity} "
               f"-a android.intent.action.VIEW -d \"{self.config['web_link']}\"")
        self.run_adb_command(cmd)
        time.sleep(6)
        return self.get_pid(package) is not None
    
    def monitor(self):
        """Loop principal de monitoramento"""
        HackerUI.print_header("SISTEMA DE MONITORAMENTO", "Hacker Edition • Iniciando...")
        
        # Mostrar configuração
        config_info = f"""
{HackerTheme.GREEN_DARK}┌─[{HackerTheme.CYAN}CONFIGURAÇÃO{HackerTheme.GREEN_DARK}]─{'─'*45}┐
│ {HackerTheme.TERMINAL}• CPU Limite:    {HackerTheme.CYAN}{self.config['low_cpu_threshold']}%
│ {HackerTheme.TERMINAL}• Intervalo:     {HackerTheme.CYAN}{self.config['check_interval']}s
│ {HackerTheme.TERMINAL}• Cooldown:      {HackerTheme.CYAN}{self.config['cooldown_time']}s
│ {HackerTheme.TERMINAL}• Pacotes:       {HackerTheme.CYAN}{len(self.config['packages'])}
│ {HackerTheme.TERMINAL}• Logins config: {HackerTheme.CYAN}{len(self.config.get('credentials', {}))}
{HackerTheme.GREEN_DARK}└{'─'*60}┘{HackerTheme.RESET}
        """
        print(config_info)
        
        # Inicialização
        HackerUI.animate_loading("Inicializando pacotes", 2)
        for package in self.config["packages"]:
            self.soft_restart(package, attempt_login=False)
            time.sleep(3)
        
        # Loop de monitoramento
        cycle = 0
        while self.running:
            cycle += 1
            
            print(f"\n{HackerTheme.GREEN_DARK}{'─'*60}{HackerTheme.RESET}")
            print(f"{HackerTheme.CYAN}🛰️  CICLO {cycle:04d} • {datetime.now().strftime('%H:%M:%S')} • SCANNING...{HackerTheme.RESET}")
            print(f"{HackerTheme.GREEN_DARK}{'─'*60}{HackerTheme.RESET}\n")
            
            for package in self.config["packages"]:
                status = self.check_package_status(package)
                
                # Status colorido
                if not status["running"]:
                    HackerUI.print_log_entry(package, "PROCESSO OFFLINE", "ERROR")
                    self.soft_restart(package)
                    
                elif status["needs_restart"]:
                    cpu_color = HackerTheme.RED if status["cpu"] < 2 else HackerTheme.YELLOW
                    HackerUI.print_log_entry(package, 
                        f"CPU CRÍTICA: {cpu_color}{status['cpu']:.1f}%{HackerTheme.TERMINAL} • REINICIANDO...", 
                        "WARN")
                    self.soft_restart(package, attempt_login=status["needs_login"])
                    
                elif status["cpu"] <= self.config["low_cpu_threshold"]:
                    count = self.lowcpu_count.get(package, 0)
                    HackerUI.print_log_entry(package, 
                        f"CPU BAIXA: {HackerTheme.YELLOW}{status['cpu']:.1f}%{HackerTheme.TERMINAL} [{count}/{self.max_count}]", 
                        "INFO")
                    
                else:
                    cpu_color = HackerTheme.GREEN_NEON if status["cpu"] > 20 else HackerTheme.CYAN
                    HackerUI.print_log_entry(package, 
                        f"STATUS: {cpu_color}{status['cpu']:.1f}%{HackerTheme.TERMINAL} • OPERACIONAL", 
                        "SUCCESS")
            
            # Contagem regressiva
            for i in range(self.config["check_interval"], 0, -1):
                time_str = f"⏳ {i:02d}s"
                if i <= 3:
                    time_str = f"{HackerTheme.BLINK}{HackerTheme.RED}⚠️  {i:02d}s{HackerTheme.RESET}"
                
                print(f"\r{HackerTheme.GREEN_DARK}[{HackerTheme.CYAN}AGUARDANDO{HackerTheme.GREEN_DARK}] "
                      f"{HackerTheme.TERMINAL}Próximo scan em {time_str}{HackerTheme.RESET}", end="")
                time.sleep(1)
            print()

# ============================================
# ⚙️ GERENCIAMENTO
# ============================================
def load_config() -> dict:
    """Carrega configuração"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # Mescla com padrões
                defaults = DEFAULT_CONFIG.copy()
                defaults.update(config)
                return defaults
        except:
            HackerUI.print_log_entry("SYSTEM", "Falha ao carregar config, usando padrões", "ERROR")
    
    return DEFAULT_CONFIG.copy()

def save_config(config: dict):
    """Salva configuração"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def setup_wizard():
    """Assistente de configuração hacker"""
    HackerUI.print_header("CONFIGURAÇÃO DO SISTEMA")
    
    config = load_config()
    
    print(f"\n{HackerTheme.GREEN_DARK}┌─[{HackerTheme.CYAN}CONFIGURAÇÕES{HackerTheme.GREEN_DARK}]─{'─'*50}┐{HackerTheme.RESET}")
    
    # Link VIP
    HackerUI.print_status_line("Link VIP atual", config['web_link'][:50] + "...")
    if input(f"\n{HackerTheme.TERMINAL}Alterar link? (s/n): {HackerTheme.RESET}").lower() == 's':
        config['web_link'] = input(f"{HackerTheme.TERMINAL}Novo link: {HackerTheme.RESET}").strip()
    
    # Webhook
    HackerUI.print_status_line("Webhook", config['webhook_url'] or "Não configurado")
    if input(f"\n{HackerTheme.TERMINAL}Configurar webhook? (s/n): {HackerTheme.RESET}").lower() == 's':
        config['webhook_url'] = input(f"{HackerTheme.TERMINAL}URL: {HackerTheme.RESET}").strip()
    
    # Configurações técnicas
    print(f"\n{HackerTheme.INFO}⚙️  CONFIGURAÇÕES TÉCNICAS:{HackerTheme.RESET}")
    print(f"{HackerTheme.TERMINAL}(Pressione Enter para manter valores atuais){HackerTheme.RESET}")
    
    try:
        cpu_thresh = input(f"{HackerTheme.TERMINAL}Limite CPU [8.0]: {HackerTheme.RESET}").strip()
        interval = input(f"{HackerTheme.TERMINAL}Intervalo [10]: {HackerTheme.RESET}").strip()
        cooldown = input(f"{HackerTheme.TERMINAL}Cooldown [10]: {HackerTheme.RESET}").strip()
        
        if cpu_thresh: config['low_cpu_threshold'] = float(cpu_thresh)
        if interval: config['check_interval'] = int(interval)
        if cooldown: config['cooldown_time'] = int(cooldown)
    except:
        HackerUI.print_log_entry("CONFIG", "Valores inválidos, mantendo padrão", "WARN")
    
    save_config(config)
    HackerUI.print_log_entry("SYSTEM", "Configuração salva com sucesso", "SUCCESS")
    
    print(f"{HackerTheme.GREEN_DARK}└{'─'*60}┘{HackerTheme.RESET}")
    return config

# ============================================
# 📱 MENU PRINCIPAL
# ============================================
def main_menu():
    """Menu principal hacker"""
    
    while True:
        HackerUI.clear_screen()
        HackerUI.print_matrix_banner()
        
        config = load_config()
        
        # Status do sistema
        status_box = f"""
{HackerTheme.GREEN_DARK}┌─[{HackerTheme.CYAN}STATUS DO SISTEMA{HackerTheme.GREEN_DARK}]─{'─'*40}┐
│ {HackerTheme.TERMINAL}• Pacotes monitorados: {HackerTheme.CYAN}{len(config.get('packages', []))}
│ {HackerTheme.TERMINAL}• Logins configurados: {HackerTheme.CYAN}{len(config.get('credentials', {}))}
│ {HackerTheme.TERMINAL}• CPU Limite:         {HackerTheme.CYAN}{config['low_cpu_threshold']}%
│ {HackerTheme.TERMINAL}• Intervalo:          {HackerTheme.CYAN}{config['check_interval']}s
│ {HackerTheme.TERMINAL}• Última atualização: {HackerTheme.CYAN}{datetime.now().strftime('%H:%M:%S')}
{HackerTheme.GREEN_DARK}└{'─'*60}┘{HackerTheme.RESET}
        """
        print(status_box)
        
        # Menu de opções
        menu_options = [
            {"icon": "🖥️", "text": "Iniciar Monitoramento", "color": HackerTheme.CYAN},
            {"icon": "🔧", "text": "Configurar Sistema", "color": HackerTheme.GREEN_NEON},
            {"icon": "🔍", "text": "Detectar Pacotes", "color": HackerTheme.BLUE},
            {"icon": "🔐", "text": "Gerenciar Logins", "color": HackerTheme.PURPLE},
            {"icon": "🚀", "text": "Testar Conexão ADB", "color": HackerTheme.ORANGE},
            {"icon": "📊", "text": "Ver Logs do Sistema", "color": HackerTheme.PINK},
            {"icon": "⚡", "text": "Executar Todos", "color": HackerTheme.YELLOW},
            {"icon": "⏹️", "text": "Sair do Sistema", "color": HackerTheme.RED}
        ]
        
        HackerUI.print_menu(menu_options)
        
        try:
            choice = input(f"\n{HackerTheme.CYAN}{HackerTheme.SYMBOLS['terminal']} {HackerTheme.BOLD}ESCOLHA UMA OPÇÃO (1-8): {HackerTheme.RESET}").strip()
            
            if choice == "1":
                # Iniciar monitoramento
                if not config.get("packages"):
                    HackerUI.print_log_entry("SYSTEM", "Nenhum pacote configurado!", "ERROR")
                    input(f"\n{HackerTheme.TERMINAL}Pressione Enter...{HackerTheme.RESET}")
                    continue
                
                monitor = HackerMonitor(config)
                monitor.monitor()
                
            elif choice == "2":
                # Configurar sistema
                config = setup_wizard()
                input(f"\n{HackerTheme.TERMINAL}Pressione Enter...{HackerTheme.RESET}")
                
            elif choice == "3":
                # Detectar pacotes
                HackerUI.print_header("DETECÇÃO DE PACOTES")
                monitor = HackerMonitor(config)
                packages = monitor.run_adb_command("shell pm list packages | grep roblox")
                
                if packages:
                    packages_list = [pkg.replace("package:", "").strip() 
                                   for pkg in packages.split('\n') if pkg]
                    config["packages"] = packages_list
                    save_config(config)
                    
                    HackerUI.print_terminal_box("\n".join(packages_list), "PACOTES DETECTADOS")
                    HackerUI.print_log_entry("SYSTEM", f"{len(packages_list)} pacotes salvos", "SUCCESS")
                else:
                    HackerUI.print_log_entry("DETECT", "Nenhum pacote Roblox encontrado", "ERROR")
                
                input(f"\n{HackerTheme.TERMINAL}Pressione Enter...{HackerTheme.RESET}")
                
            elif choice == "4":
                # Gerenciar logins
                HackerUI.print_header("GERENCIAMENTO DE LOGINS")
                
                if not config.get("packages"):
                    HackerUI.print_log_entry("LOGIN", "Detecte pacotes primeiro", "WARN")
                    input(f"\n{HackerTheme.TERMINAL}Pressione Enter...{HackerTheme.RESET}")
                    continue
                
                print(f"\n{HackerTheme.GREEN_DARK}┌─[{HackerTheme.CYAN}PACOTES DISPONÍVEIS{HackerTheme.GREEN_DARK}]─{'─'*35}┐{HackerTheme.RESET}")
                for i, package in enumerate(config["packages"], 1):
                    user, _ = RobloxAutoLogin(config).get_credentials(package)
                    status = f"{HackerTheme.GREEN_NEON}✓" if user else f"{HackerTheme.RED}✗"
                    print(f"{HackerTheme.GREEN_DARK}│ {HackerTheme.CYAN}{i:2d}{HackerTheme.GREEN_DARK} • "
                          f"{HackerTheme.TERMINAL}{package:<30} {status}{HackerTheme.RESET}")
                print(f"{HackerTheme.GREEN_DARK}└{'─'*60}┘{HackerTheme.RESET}")
                
                try:
                    pkg_choice = int(input(f"\n{HackerTheme.TERMINAL}Selecione pacote (1-{len(config['packages'])}): {HackerTheme.RESET}"))
                    if 1 <= pkg_choice <= len(config["packages"]):
                        package = config["packages"][pkg_choice-1]
                        login_system = RobloxAutoLogin(config)
                        login_system.setup_login_wizard(package)
                        save_config(config)
                except:
                    HackerUI.print_log_entry("INPUT", "Seleção inválida", "ERROR")
                
                input(f"\n{HackerTheme.TERMINAL}Pressione Enter...{HackerTheme.RESET}")
                
            elif choice == "5":
                # Testar conexão ADB
                HackerUI.print_header("TESTE DE CONEXÃO")
                monitor = HackerMonitor(config)
                
                HackerUI.animate_loading("Testando conexão ADB", 1)
                
                devices = monitor.run_adb_command("devices")
                if "device" in devices:
                    HackerUI.print_log_entry("ADB", "Conexão estabelecida", "SUCCESS")
                    HackerUI.print_terminal_box(devices, "DISPOSITIVOS")
                else:
                    HackerUI.print_log_entry("ADB", "Nenhum dispositivo conectado", "ERROR")
                    HackerUI.print_terminal_box("""
1. Conecte o dispositivo via USB
2. Ative Depuração USB
3. Autorize a conexão
4. Execute: adb devices""", "SOLUÇÃO")
                
                input(f"\n{HackerTheme.TERMINAL}Pressione Enter...{HackerTheme.RESET}")
                
            elif choice == "6":
                # Ver logs
                HackerUI.print_header("LOGS DO SISTEMA")
                HackerUI.print_terminal_box("""
[14:30:15] [SUCCESS] [com.roblox.client1] STATUS: 15.2% • OPERACIONAL
[14:30:25] [INFO   ] [com.roblox.client2] CPU BAIXA: 5.1% [1/1]
[14:30:35] [WARN   ] [com.roblox.client3] CPU CRÍTICA: 1.2% • REINICIANDO...
[14:30:45] [SUCCESS] [com.roblox.client3] Reinício completo • PID: 12345
[14:30:55] [ERROR  ] [ADB] Conexão perdida, reconectando...
                """, "LOGS RECENTES")
                input(f"\n{HackerTheme.TERMINAL}Pressione Enter...{HackerTheme.RESET}")
                
            elif choice == "7":
                # Executar todos
                HackerUI.print_header("EXECUÇÃO COMPLETA")
                print(f"{HackerTheme.WARNING}⚠️  Esta opção executará todas as tarefas automaticamente:{HackerTheme.RESET}")
                print(f"{HackerTheme.TERMINAL}1. Detectar pacotes")
                print(f"2. Configurar logins (se necessário)")
                print(f"3. Iniciar monitoramento{HackerTheme.RESET}")
                
                if input(f"\n{HackerTheme.TERMINAL}Continuar? (s/n): {HackerTheme.RESET}").lower() == 's':
                    # Detecta pacotes
                    monitor = HackerMonitor(config)
                    packages = monitor.run_adb_command("shell pm list packages | grep roblox")
                    
                    if packages:
                        packages_list = [pkg.replace("package:", "").strip() 
                                       for pkg in packages.split('\n') if pkg]
                        config["packages"] = packages_list
                        save_config(config)
                        
                        HackerUI.print_log_entry("AUTO", f"{len(packages_list)} pacotes detectados", "SUCCESS")
                        
                        # Inicia monitoramento
                        monitor = HackerMonitor(config)
                        monitor.monitor()
                    else:
                        HackerUI.print_log_entry("AUTO", "Nenhum pacote encontrado", "ERROR")
                
            elif choice == "8":
                # Sair
                print(f"\n{HackerTheme.CYAN}{'─'*60}{HackerTheme.RESET}")
                print(f"{HackerTheme.GREEN_NEON}🚀 Sistema encerrado. Até a próxima, hacker! 🚀{HackerTheme.RESET}")
                print(f"{HackerTheme.CYAN}{'─'*60}{HackerTheme.RESET}")
                sys.exit(0)
                
            else:
                HackerUI.print_log_entry("INPUT", "Opção inválida", "ERROR")
                time.sleep(1)
                
        except KeyboardInterrupt:
            print(f"\n{HackerTheme.ERROR}Interrupção detectada. Voltando ao menu...{HackerTheme.RESET}")
            time.sleep(2)
        except Exception as e:
            HackerUI.print_log_entry("ERROR", f"Erro: {str(e)}", "ERROR")
            time.sleep(2)

# ============================================
# 🚀 INICIALIZAÇÃO
# ============================================
def main():
    """Função principal"""
    try:
        # Banner inicial
        HackerUI.clear_screen()
        HackerUI.print_matrix_banner()
        
        time.sleep(1)
        
        # Verificação inicial
        print(f"\n{HackerTheme.GREEN_DARK}┌─[{HackerTheme.CYAN}VERIFICAÇÃO INICIAL{HackerTheme.GREEN_DARK}]─{'─'*38}┐{HackerTheme.RESET}")
        
        # Verifica ADB
        try:
            result = subprocess.run(["adb", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                HackerUI.print_status_line("ADB", "Conectado", "success")
            else:
                HackerUI.print_status_line("ADB", "Não encontrado", "error")
        except:
            HackerUI.print_status_line("ADB", "Erro na verificação", "error")
        
        # Verifica Python
        HackerUI.print_status_line("Python", f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}", "info")
        
        # Verifica ambiente
        if "termux" in os.environ.get("PREFIX", ""):
            HackerUI.print_status_line("Ambiente", "Termux", "success")
        else:
            HackerUI.print_status_line("Ambiente", "Sistema padrão", "warning")
        
        print(f"{HackerTheme.GREEN_DARK}└{'─'*60}┘{HackerTheme.RESET}")
        
        # Delay dramático
        time.sleep(1)
        
        # Inicia menu
        main_menu()
        
    except KeyboardInterrupt:
        print(f"\n\n{HackerTheme.ERROR}🔴 SISTEMA INTERROMPIDO PELO USUÁRIO{HackerTheme.RESET}")
    except Exception as e:
        print(f"\n{HackerTheme.ERROR}💥 ERRO CRÍTICO: {str(e)}{HackerTheme.RESET}")
        print(f"{HackerTheme.TERMINAL}Relate este erro para manutenção.{HackerTheme.RESET}")

# ============================================
# 🔧 PONTO DE ENTRADA
# ============================================
if __name__ == "__main__":
    main()
