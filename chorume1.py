#!/usr/bin/env python3
"""
🎮 Roblox AutoRejoin - Organização Corrigida 🎮
Sistema aprimorado que abre Roblox de forma organizada sem bugar
Versão: 6.0 - Correção de Organização
"""

import os
import sys
import time
import json
import signal
import subprocess
import random
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass

# ============================================
# 🎨 TEMA HACKER MELHORADO
# ============================================
class HackerUI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    
    # Cores
    GREEN = "\033[38;5;46m"
    CYAN = "\033[38;5;51m"
    BLUE = "\033[38;5;39m"
    YELLOW = "\033[38;5;226m"
    RED = "\033[38;5;196m"
    PURPLE = "\033[38;5;93m"
    ORANGE = "\033[38;5;208m"
    PINK = "\033[38;5;201m"
    
    @staticmethod
    def clear():
        os.system('cls' if os.name == 'nt' else 'clear')
    
    @staticmethod
    def print_banner():
        HackerUI.clear()
        print(f"""
{HackerUI.GREEN}{HackerUI.BOLD}
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║    ██████╗  ██████╗ ██████╗ ██╗      ██████╗ ██╗  ██╗   ║
║    ██╔══██╗██╔═══██╗██╔══██╗██║     ██╔═══██╗╚██╗██╔╝   ║
║    ██████╔╝██║   ██║██████╔╝██║     ██║   ██║ ╚███╔╝    ║
║    ██╔══██╗██║   ██║██╔══██╗██║     ██║   ██║ ██╔██╗    ║
║    ██║  ██║╚██████╔╝██║  ██║███████╗╚██████╔╝██╔╝ ██╗   ║
║    ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝   ║
║                                                          ║
║           AUTOREJOIN - ORGANIZAÇÃO CORRIGIDA             ║
║                 Versão 6.0 • Stable                      ║
╚══════════════════════════════════════════════════════════╝
{HackerUI.RESET}""")
    
    @staticmethod
    def print_log(icon: str, message: str, color: str = ""):
        timestamp = datetime.now().strftime("%H:%M:%S")
        color_code = color if color else HackerUI.CYAN
        print(f"{HackerUI.PURPLE}[{timestamp}] {color_code}{icon} {message}{HackerUI.RESET}")

# ============================================
# ⚙️ CONFIGURAÇÃO
# ============================================
CONFIG_FILE = "autorejoin_config.json"
DEFAULT_CONFIG = {
    "web_link": "https://www.roblox.com/games/1537690962/Bee-Swarm-Simulator?privateServerLinkCode=05888256464342538313491710978310",
    "check_interval": 10,
    "low_cpu_threshold": 8.0,
    "max_lowcpu_time": 10,
    "cooldown_time": 10,
    "packages": [],
    "organize_windows": True,  # Nova opção para controlar organização
    "open_delay": 5,  # Delay entre aberturas
    "use_swipe_method": False  # Método alternativo se o principal falhar
}

# ============================================
# 🪟 ORGANIZADOR CORRIGIDO
# ============================================
class SafeWindowOrganizer:
    """
    Organizador seguro que NÃO usa wm size (que bagunça tudo).
    Usa métodos mais seguros para controlar as janelas.
    """
    
    @staticmethod
    def open_with_delay(package: str, link: str, delay: int = 0):
        """Abre um Roblox com delay e retorna PID"""
        HackerUI.print_log("▶", f"Abrindo {package}", HackerUI.BLUE)
        
        # Fecha se já estiver aberto (suave)
        subprocess.run(["adb", "shell", "am", "force-stop", package], 
                      capture_output=True, timeout=5)
        time.sleep(1)
        
        # Abre normalmente
        cmd = f"shell am start -n {package}/com.roblox.client.ActivityProtocolLaunch -a android.intent.action.VIEW -d \"{link}\""
        subprocess.run(["adb"] + cmd.split(), capture_output=True, timeout=5)
        
        if delay > 0:
            time.sleep(delay)
        
        # Verifica se abriu
        result = subprocess.run(["adb", "shell", "pidof", package], 
                              capture_output=True, text=True, timeout=5)
        pid = result.stdout.strip()
        
        if pid:
            HackerUI.print_log("✓", f"{package} aberto (PID: {pid})", HackerUI.GREEN)
        else:
            HackerUI.print_log("⚠", f"{package} pode não ter aberto", HackerUI.YELLOW)
        
        return pid
    
    @staticmethod
    def open_all_sequentially(packages: List[str], link: str, config: dict):
        """
        Abre todos os Roblox sequencialmente com delays inteligentes.
        Isso evita que abram todos de uma vez bagunçando.
        """
        HackerUI.print_log("🔄", f"Iniciando abertura sequencial de {len(packages)} Roblox", HackerUI.CYAN)
        
        pids = {}
        delay = config.get("open_delay", 5)
        
        for i, package in enumerate(packages):
            HackerUI.print_log(f"{i+1}/{len(packages)}", f"Processando {package}", HackerUI.PURPLE)
            
            pid = SafeWindowOrganizer.open_with_delay(package, link, delay)
            if pid:
                pids[package] = pid
            
            # Delay maior entre diferentes instâncias
            if i < len(packages) - 1:
                HackerUI.print_log("⏳", f"Aguardando {delay}s antes do próximo...", HackerUI.YELLOW)
                time.sleep(delay)
        
        return pids
    
    @staticmethod
    def get_current_activity(package: str) -> str:
        """Obtém a atividade atual de um pacote"""
        try:
            cmd = f"shell dumpsys window windows | grep -E 'mCurrentFocus|mFocusedApp'"
            result = subprocess.run(["adb"] + cmd.split(), 
                                  capture_output=True, text=True, timeout=5)
            return result.stdout.strip()
        except:
            return ""
    
    @staticmethod
    def safe_organize_method(packages: List[str]):
        """
        Método SEGURO de organização que não bagunça.
        Usa keyevents para navegar entre apps.
        """
        if len(packages) <= 1:
            return
        
        HackerUI.print_log("🔄", "Organizando janelas (método seguro)...", HackerUI.CYAN)
        
        try:
            # 1. Vai para a home primeiro
            subprocess.run(["adb", "shell", "input", "keyevent", "3"],  # HOME
                         capture_output=True, timeout=2)
            time.sleep(1)
            
            # 2. Para múltiplos Roblox, usamos app switching
            for i, package in enumerate(packages):
                # Abre o app switcher (recentes)
                subprocess.run(["adb", "shell", "input", "keyevent", "187"],  # APP_SWITCH
                             capture_output=True, timeout=2)
                time.sleep(0.5)
                
                # Fecha o app switcher
                subprocess.run(["adb", "shell", "input", "keyevent", "4"],  # BACK
                             capture_output=True, timeout=2)
                time.sleep(1)
                
                # Toca para abrir o Roblox
                subprocess.run(["adb", "shell", "monkey", "-p", package, "1"],
                             capture_output=True, timeout=2)
                time.sleep(2)
            
            HackerUI.print_log("✓", "Organização segura concluída", HackerUI.GREEN)
            
        except Exception as e:
            HackerUI.print_log("⚠", f"Organização falhou: {str(e)}", HackerUI.YELLOW)

# ============================================
# 🎮 MONITOR CORRIGIDO
# ============================================
class FixedMonitor:
    """Monitor corrigido que não bagunça as janelas"""
    
    def __init__(self, config: dict):
        self.config = config
        self.lowcpu_count: Dict[str, int] = {}
        self.cooldown: Dict[str, float] = {}
        self.max_count = config["max_lowcpu_time"] // config["check_interval"]
        self.running = True
        
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        HackerUI.print_log("🛑", "Monitoramento interrompido", HackerUI.RED)
        self.running = False
    
    def run_adb(self, command: str) -> str:
        try:
            result = subprocess.run(["adb"] + command.split(),
                                  capture_output=True, text=True, timeout=10)
            return result.stdout.strip()
        except:
            return ""
    
    def get_pid(self, package: str) -> Optional[str]:
        return self.run_adb(f"shell pidof {package}")
    
    def get_cpu(self, pid: str) -> float:
        try:
            output = self.run_adb(f"shell top -n 1 -b | grep '^{pid}'")
            if output and len(output.split()) >= 9:
                cpu_str = output.split()[8].replace(',', '.').replace('%', '')
                return float(cpu_str)
        except:
            pass
        return 0.0
    
    def open_single_roblox(self, package: str) -> bool:
        """Abre um único Roblox de forma limpa"""
        HackerUI.print_log("🚀", f"Abrindo {package}", HackerUI.BLUE)
        
        # 1. Fecha suavemente
        self.run_adb(f"shell am force-stop {package}")
        time.sleep(2)
        
        # 2. Limpa apenas cache (NÃO dados!)
        self.run_adb(f"shell pm clear --cache-only {package}")
        time.sleep(1)
        
        # 3. Abre o VIP
        cmd = f"shell am start -n {package}/com.roblox.client.ActivityProtocolLaunch -a android.intent.action.VIEW -d \"{self.config['web_link']}\""
        self.run_adb(cmd)
        
        # 4. Aguarda inteligentemente
        wait_time = 8
        for i in range(wait_time):
            print(f"\r{HackerUI.YELLOW}⏳ Aguardando {wait_time-i}s...{HackerUI.RESET}", end="")
            time.sleep(1)
        print()
        
        # 5. Verifica
        pid = self.get_pid(package)
        if pid:
            HackerUI.print_log("✅", f"{package} pronto (PID: {pid})", HackerUI.GREEN)
            return True
        else:
            HackerUI.print_log("⚠", f"{package} não abriu corretamente", HackerUI.YELLOW)
            return False
    
    def initialize_all(self):
        """Inicializa todos os Roblox de forma organizada"""
        packages = self.config["packages"]
        
        if not packages:
            HackerUI.print_log("❌", "Nenhum pacote configurado", HackerUI.RED)
            return False
        
        HackerUI.print_log("🎮", f"Inicializando {len(packages)} Roblox...", HackerUI.CYAN)
        print(f"{HackerUI.PURPLE}{'='*60}{HackerUI.RESET}")
        
        success_count = 0
        
        # Se organização está habilitada, usa método sequencial
        if self.config.get("organize_windows", True):
            pids = SafeWindowOrganizer.open_all_sequentially(
                packages, 
                self.config["web_link"],
                self.config
            )
            success_count = len(pids)
        else:
            # Método simples (um por um com delays)
            for i, package in enumerate(packages):
                HackerUI.print_log(f"{i+1}/{len(packages)}", f"Iniciando {package}", HackerUI.PURPLE)
                
                if self.open_single_roblox(package):
                    success_count += 1
                
                # Delay entre aberturas
                if i < len(packages) - 1:
                    delay = self.config.get("open_delay", 5)
                    HackerUI.print_log("⏳", f"Aguardando {delay}s...", HackerUI.YELLOW)
                    time.sleep(delay)
        
        print(f"{HackerUI.PURPLE}{'='*60}{HackerUI.RESET}")
        HackerUI.print_log("📊", f"Resultado: {success_count}/{len(packages)} sucessos", 
                          HackerUI.GREEN if success_count == len(packages) else HackerUI.YELLOW)
        
        return success_count > 0
    
    def restart_single(self, package: str):
        """Reinicia um único Roblox"""
        current_time = time.time()
        
        # Cooldown check
        if package in self.cooldown and current_time < self.cooldown[package]:
            remaining = self.cooldown[package] - current_time
            HackerUI.print_log("⏸️", f"{package} em cooldown ({remaining:.0f}s)", HackerUI.YELLOW)
            return False
        
        HackerUI.print_log("🔄", f"Reiniciando {package}", HackerUI.ORANGE)
        
        success = self.open_single_roblox(package)
        
        if success:
            self.cooldown[package] = time.time() + self.config["cooldown_time"]
            self.lowcpu_count[package] = 0
        
        return success
    
    def monitor(self):
        """Loop principal de monitoramento"""
        HackerUI.print_log("🎯", "Iniciando monitoramento organizado", HackerUI.CYAN)
        print(f"{HackerUI.BLUE}• CPU limite: {self.config['low_cpu_threshold']}%")
        print(f"• Intervalo: {self.config['check_interval']}s")
        print(f"• Pacotes: {len(self.config['packages'])}")
        print(f"• Organização: {'ATIVADA' if self.config.get('organize_windows', True) else 'DESATIVADA'}{HackerUI.RESET}")
        print(f"{HackerUI.PURPLE}{'='*60}{HackerUI.RESET}")
        
        # Inicialização
        self.initialize_all()
        
        cycle = 0
        while self.running:
            cycle += 1
            
            print(f"\n{HackerUI.CYAN}{HackerUI.BOLD}═══════ CICLO {cycle} • {datetime.now().strftime('%H:%M:%S')} ═══════{HackerUI.RESET}")
            
            for package in self.config["packages"]:
                pid = self.get_pid(package)
                
                if not pid:
                    HackerUI.print_log("❌", f"{package} OFFLINE", HackerUI.RED)
                    self.restart_single(package)
                    continue
                
                cpu = self.get_cpu(pid)
                
                if cpu <= self.config["low_cpu_threshold"]:
                    self.lowcpu_count[package] = self.lowcpu_count.get(package, 0) + 1
                    
                    if self.lowcpu_count[package] >= self.max_count:
                        HackerUI.print_log("⚠", f"{package}: {cpu:.1f}% (TRAVADO)", HackerUI.ORANGE)
                        self.restart_single(package)
                    else:
                        HackerUI.print_log("📉", f"{package}: {cpu:.1f}% ({self.lowcpu_count[package]}/{self.max_count})", HackerUI.YELLOW)
                else:
                    self.lowcpu_count[package] = 0
                    cpu_color = HackerUI.GREEN if cpu > 15 else HackerUI.CYAN
                    HackerUI.print_log("✅", f"{package}: {cpu_color}{cpu:.1f}%{HackerUI.RESET}")
            
            # Contagem regressiva melhorada
            interval = self.config["check_interval"]
            for i in range(interval, 0, -1):
                dots = "." * (interval - i)
                print(f"\r{HackerUI.PURPLE}⏳ Próxima verificação em {i:02d}s{dots}{' ' * 10}{HackerUI.RESET}", end="")
                time.sleep(1)
            print()

# ============================================
# ⚙️ GERENCIAMENTO
# ============================================
def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                defaults = DEFAULT_CONFIG.copy()
                defaults.update(config)
                return defaults
        except:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(config: dict):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def detect_roblox():
    """Detecta pacotes Roblox"""
    HackerUI.print_log("🔍", "Procurando pacotes Roblox...", HackerUI.CYAN)
    
    try:
        result = subprocess.run(
            ["adb", "shell", "pm", "list", "packages"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        packages = []
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if "package:" in line and "roblox" in line.lower():
                    pkg = line.replace("package:", "").strip()
                    packages.append(pkg)
        
        if packages:
            HackerUI.print_log("✅", f"Encontrados {len(packages)} pacotes:", HackerUI.GREEN)
            for pkg in packages:
                print(f"  {HackerUI.BLUE}• {pkg}{HackerUI.RESET}")
            return packages
        else:
            HackerUI.print_log("❌", "Nenhum pacote Roblox encontrado", HackerUI.RED)
            return []
            
    except Exception as e:
        HackerUI.print_log("❌", f"Erro: {str(e)}", HackerUI.RED)
        return []

def test_organization():
    """Testa a organização sem iniciar monitoramento"""
    HackerUI.print_log("🧪", "Testando organização de janelas...", HackerUI.CYAN)
    
    config = load_config()
    packages = config.get("packages", [])
    
    if not packages:
        HackerUI.print_log("❌", "Configure pacotes primeiro", HackerUI.RED)
        return
    
    print(f"{HackerUI.PURPLE}{'='*60}{HackerUI.RESET}")
    HackerUI.print_log("ℹ️", f"Testando com {len(packages)} Roblox", HackerUI.BLUE)
    print(f"{HackerUI.PURPLE}{'='*60}{HackerUI.RESET}")
    
    # Fecha todos primeiro
    for package in packages:
        subprocess.run(["adb", "shell", "am", "force-stop", package], capture_output=True)
    
    time.sleep(2)
    
    # Abre sequencialmente
    organizer = SafeWindowOrganizer()
    pids = organizer.open_all_sequentially(packages, config["web_link"], config)
    
    print(f"{HackerUI.PURPLE}{'='*60}{HackerUI.RESET}")
    HackerUI.print_log("📊", f"Resultado do teste: {len(pids)}/{len(packages)} abertos", 
                      HackerUI.GREEN if len(pids) == len(packages) else HackerUI.YELLOW)

# ============================================
# 📱 MENU SIMPLES E FUNCIONAL
# ============================================
def main_menu():
    """Menu principal simplificado"""
    
    while True:
        HackerUI.print_banner()
        
        config = load_config()
        
        # Status
        print(f"\n{HackerUI.CYAN}{HackerUI.BOLD}📊 STATUS DO SISTEMA{HackerUI.RESET}")
        print(f"{HackerUI.BLUE}• Pacotes: {len(config.get('packages', []))}")
        print(f"• CPU limite: {config['low_cpu_threshold']}%")
        print(f"• Intervalo: {config['check_interval']}s")
        print(f"• Organização: {'✅ ATIVA' if config.get('organize_windows', True) else '❌ INATIVA'}")
        print(f"• Link VIP: {config['web_link'][:40]}...{HackerUI.RESET}")
        
        print(f"\n{HackerUI.PURPLE}{'='*60}{HackerUI.RESET}")
        print(f"{HackerUI.CYAN}{HackerUI.BOLD}📋 MENU PRINCIPAL{HackerUI.RESET}")
        print(f"{HackerUI.GREEN}1. 🚀 Iniciar Monitoramento")
        print(f"2. 🔍 Detectar Pacotes Roblox")
        print(f"3. ⚙️  Configurar Sistema")
        print(f"4. 🧪 Testar Organização")
        print(f"5. 🔄 Reiniciar Todos Agora")
        print(f"6. 📊 Verificar ADB")
        print(f"7. ❌ Sair{HackerUI.RESET}")
        print(f"\n{HackerUI.PURPLE}{'='*60}{HackerUI.RESET}")
        
        try:
            choice = input(f"\n{HackerUI.CYAN}▶ Escolha (1-7): {HackerUI.RESET}").strip()
            
            if choice == "1":
                # Iniciar monitoramento
                if not config.get("packages"):
                    HackerUI.print_log("❌", "Configure pacotes primeiro!", HackerUI.RED)
                    input(f"\n{HackerUI.YELLOW}Pressione Enter...{HackerUI.RESET}")
                    continue
                
                monitor = FixedMonitor(config)
                monitor.monitor()
                
            elif choice == "2":
                # Detectar pacotes
                packages = detect_roblox()
                if packages:
                    config["packages"] = packages
                    save_config(config)
                    HackerUI.print_log("✅", "Pacotes salvos na configuração", HackerUI.GREEN)
                input(f"\n{HackerUI.YELLOW}Pressione Enter...{HackerUI.RESET}")
                
            elif choice == "3":
                # Configurar sistema
                print(f"\n{HackerUI.CYAN}⚙️  CONFIGURAÇÃO{HackerUI.RESET}")
                
                print(f"\n{HackerUI.BLUE}1. Organização de janelas:")
                current = config.get("organize_windows", True)
                print(f"   Atual: {'✅ ATIVA' if current else '❌ INATIVA'}")
                org = input(f"   Ativar organização? (s/n) [{ 's' if current else 'n' }]: ").strip().lower()
                if org in ['s', 'n']:
                    config["organize_windows"] = (org == 's')
                
                print(f"\n{HackerUI.BLUE}2. Delay entre aberturas:")
                current_delay = config.get("open_delay", 5)
                print(f"   Atual: {current_delay}s")
                delay = input(f"   Novo delay (segundos) [{current_delay}]: ").strip()
                if delay.isdigit():
                    config["open_delay"] = int(delay)
                
                print(f"\n{HackerUI.BLUE}3. Link VIP:")
                print(f"   Atual: {config['web_link'][:50]}...")
                change = input(f"   Alterar? (s/n): ").strip().lower()
                if change == 's':
                    new_link = input(f"   Novo link: ").strip()
                    if new_link:
                        config['web_link'] = new_link
                
                save_config(config)
                HackerUI.print_log("✅", "Configuração atualizada", HackerUI.GREEN)
                input(f"\n{HackerUI.YELLOW}Pressione Enter...{HackerUI.RESET}")
                
            elif choice == "4":
                # Testar organização
                test_organization()
                input(f"\n{HackerUI.YELLOW}Pressione Enter...{HackerUI.RESET}")
                
            elif choice == "5":
                # Reiniciar todos agora
                if not config.get("packages"):
                    HackerUI.print_log("❌", "Configure pacotes primeiro!", HackerUI.RED)
                    input(f"\n{HackerUI.YELLOW}Pressione Enter...{HackerUI.RESET}")
                    continue
                
                monitor = FixedMonitor(config)
                monitor.initialize_all()
                input(f"\n{HackerUI.YELLOW}Pressione Enter...{HackerUI.RESET}")
                
            elif choice == "6":
                # Verificar ADB
                print(f"\n{HackerUI.CYAN}📊 VERIFICANDO ADB{HackerUI.RESET}")
                
                try:
                    result = subprocess.run(["adb", "devices"], 
                                          capture_output=True, text=True, timeout=5)
                    
                    if result.returncode == 0:
                        print(f"\n{HackerUI.GREEN}✅ ADB Conectado:{HackerUI.RESET}")
                        print(result.stdout)
                    else:
                        print(f"\n{HackerUI.RED}❌ ADB não encontrado{HackerUI.RESET}")
                        
                except Exception as e:
                    print(f"\n{HackerUI.RED}❌ Erro: {str(e)}{HackerUI.RESET}")
                
                input(f"\n{HackerUI.YELLOW}Pressione Enter...{HackerUI.RESET}")
                
            elif choice == "7":
                # Sair
                print(f"\n{HackerUI.GREEN}👋 Até logo!{HackerUI.RESET}")
                sys.exit(0)
                
            else:
                print(f"\n{HackerUI.RED}❌ Opção inválida!{HackerUI.RESET}")
                time.sleep(1)
                
        except KeyboardInterrupt:
            print(f"\n{HackerUI.RED}⚠️  Interrompido{HackerUI.RESET}")
            time.sleep(1)

# ============================================
# 🚀 INICIALIZAÇÃO
# ============================================
def main():
    try:
        main_menu()
    except KeyboardInterrupt:
        print(f"\n{HackerUI.RED}👋 Programa encerrado{HackerUI.RESET}")
    except Exception as e:
        print(f"\n{HackerUI.RED}💥 ERRO: {str(e)}{HackerUI.RESET}")

if __name__ == "__main__":
    main()
