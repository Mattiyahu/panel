#!/usr/bin/env python3
"""
🎮 Roblox AutoRejoin - Organizado 🎮
Interface hacker com janelas organizadas lado a lado
Versão: 5.0 - Organizada
"""

import os
import sys
import time
import json
import signal
import subprocess
from datetime import datetime
from typing import Dict, List, Optional
import math

# ============================================
# 🎨 TEMA HACKER SIMPLIFICADO
# ============================================
class HackerTheme:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    
    # Cores hacker
    GREEN = "\033[38;5;46m"
    CYAN = "\033[38;5;51m"
    BLUE = "\033[38;5;39m"
    YELLOW = "\033[38;5;226m"
    RED = "\033[38;5;196m"
    PURPLE = "\033[38;5;93m"
    ORANGE = "\033[38;5;208m"
    
    # Símbolos
    TRIANGLE = "▶"
    SQUARE = "■"
    CIRCLE = "●"
    DIAMOND = "◆"
    
    @staticmethod
    def print_banner():
        """Banner hacker simples"""
        print(f"""
{HackerTheme.GREEN}{HackerTheme.BOLD}
╔══════════════════════════════════════════════════════╗
║  ██████╗ ██████╗ ██████╗ ██╗      ██████╗ ██╗  ██╗  ║
║  ██╔══██╗██╔══██╗██╔══██╗██║     ██╔═══██╗╚██╗██╔╝  ║
║  ██████╔╝██████╔╝██████╔╝██║     ██║   ██║ ╚███╔╝   ║
║  ██╔══██╗██╔══██╗██╔═══╝ ██║     ██║   ██║ ██╔██╗   ║
║  ██║  ██║██║  ██║██║     ███████╗╚██████╔╝██╔╝ ██╗  ║
║  ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚══════╝ ╚═════╝ ╚═╝  ╚═╝  ║
║                                                      ║
║           AUTOREJOIN - JANELAS ORGANIZADAS           ║
║                 Versão 5.0 • Hacker                  ║
╚══════════════════════════════════════════════════════╝
{HackerTheme.RESET}""")

# ============================================
# ⚙️ CONFIGURAÇÃO
# ============================================
CONFIG_FILE = "autorejoin_config.json"
DEFAULT_CONFIG = {
    "web_link": "https://www.roblox.com/games/1537690962/Bee-Swarm-Simulator?privateServerLinkCode=05888256464342538313491710978310",
    "webhook_url": "",
    "check_interval": 10,
    "low_cpu_threshold": 8.0,
    "max_lowcpu_time": 10,
    "cooldown_time": 10,
    "packages": []
}

# ============================================
# 🪟 ORGANIZADOR DE JANELAS
# ============================================
class WindowOrganizer:
    """
    Organiza janelas do Roblox lado a lado em uma grade.
    """
    
    @staticmethod
    def get_screen_info() -> tuple:
        """Obtém informações da tela do dispositivo"""
        try:
            # Tenta obter resolução da tela
            result = subprocess.run(
                ["adb", "shell", "wm", "size"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                # Formato: "Physical size: 1080x1920"
                if "x" in output:
                    size_part = output.split(":")[-1].strip()
                    width, height = map(int, size_part.split("x"))
                    return width, height
        except:
            pass
        
        # Valores padrão para dispositivos comuns
        return 1080, 1920
    
    @staticmethod
    def calculate_grid_positions(num_windows: int) -> list:
        """
        Calcula posições para organizar janelas em grade.
        Retorna lista de dicionários com x, y, width, height.
        """
        screen_width, screen_height = WindowOrganizer.get_screen_info()
        
        # Calcula layout ideal (tenta ser o mais quadrado possível)
        cols = math.ceil(math.sqrt(num_windows))
        rows = math.ceil(num_windows / cols)
        
        positions = []
        cell_width = screen_width // cols
        cell_height = screen_height // rows
        
        for i in range(num_windows):
            row = i // cols
            col = i % cols
            
            # Calcula posição com pequenas margens
            x = col * cell_width + 10
            y = row * cell_height + 10
            width = cell_width - 20
            height = cell_height - 20
            
            positions.append({
                'x': x,
                'y': y,
                'width': width,
                'height': height,
                'row': row + 1,
                'col': col + 1
            })
        
        return positions
    
    @staticmethod
    def set_window_position(package: str, position: dict):
        """
        Define posição e tamanho da janela de um pacote.
        Usa comandos ADB para controlar a janela.
        """
        try:
            # Primeiro, garante que o app está em primeiro plano
            subprocess.run(
                ["adb", "shell", "am", "start", package],
                capture_output=True,
                timeout=5
            )
            time.sleep(1)
            
            # Tenta definir tamanho e posição (Android 7.0+)
            # Comando para redimensionar janela
            cmd = f"shell wm size {position['width']}x{position['height']}"
            subprocess.run(["adb"] + cmd.split(), capture_output=True, timeout=5)
            
            # Comando para definir posição (pode não funcionar em todos os dispositivos)
            # Esta parte é experimental
            time.sleep(0.5)
            
            print(f"{HackerTheme.BLUE}[LAYOUT] {package} → Posição: {position['col']},{position['row']} "
                  f"({position['width']}x{position['height']}){HackerTheme.RESET}")
            return True
            
        except Exception as e:
            print(f"{HackerTheme.YELLOW}[AVISO] Não foi possível organizar {package}: {str(e)}{HackerTheme.RESET}")
            return False

# ============================================
# 🎮 MONITOR ORGANIZADO
# ============================================
class OrganizedMonitor:
    """Monitor que organiza janelas lado a lado"""
    
    def __init__(self, config: dict):
        self.config = config
        self.proto_activity = "com.roblox.client.ActivityProtocolLaunch"
        self.lowcpu_count: Dict[str, int] = {}
        self.cooldown: Dict[str, float] = {}
        self.max_count = config["max_lowcpu_time"] // config["check_interval"]
        self.running = True
        self.window_positions = []
        
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        print(f"\n{HackerTheme.RED}⚠️  Monitoramento interrompido{HackerTheme.RESET}")
        self.running = False
    
    def run_adb_command(self, command: str) -> str:
        """Executa comando ADB"""
        try:
            result = subprocess.run(
                ["adb"] + command.split(),
                capture_output=True,
                text=True,
                timeout=10
            )
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
    
    def open_organized(self, package: str, position: dict = None):
        """
        Abre um Roblox em posição específica.
        Se position=None, abre em tela cheia.
        """
        print(f"{HackerTheme.CYAN}[ABRINDO] {package}{HackerTheme.RESET}")
        
        # Fecha se já estiver aberto
        self.run_adb_command(f"shell am force-stop {package}")
        time.sleep(1)
        
        # Abre o VIP
        cmd = (f"shell am start -n {package}/{self.proto_activity} "
               f"-a android.intent.action.VIEW -d \"{self.config['web_link']}\"")
        self.run_adb_command(cmd)
        time.sleep(5)
        
        # Se tiver posição específica, tenta organizar
        if position:
            WindowOrganizer.set_window_position(package, position)
        
        return self.get_pid(package) is not None
    
    def restart_all_organized(self):
        """Reinicia todos os pacotes organizadamente"""
        packages = self.config["packages"]
        
        if not packages:
            print(f"{HackerTheme.RED}❌ Nenhum pacote configurado{HackerTheme.RESET}")
            return False
        
        print(f"\n{HackerTheme.GREEN}🔄 ORGANIZANDO {len(packages)} JANELAS{HackerTheme.RESET}")
        print(f"{HackerTheme.PURPLE}{'='*60}{HackerTheme.RESET}")
        
        # Calcula posições
        self.window_positions = WindowOrganizer.calculate_grid_positions(len(packages))
        
        # Abre cada pacote em sua posição
        for i, package in enumerate(packages):
            position = self.window_positions[i] if i < len(self.window_positions) else None
            success = self.open_organized(package, position)
            
            if success:
                status = f"{HackerTheme.GREEN}✅ OK"
                if position:
                    status += f" (Pos {position['col']},{position['row']})"
            else:
                status = f"{HackerTheme.RED}❌ FALHA"
            
            print(f"{HackerTheme.CYAN}  [{i+1}/{len(packages)}] {package:<25} {status}{HackerTheme.RESET}")
            time.sleep(3)  # Aguarda entre aberturas
        
        print(f"{HackerTheme.PURPLE}{'='*60}{HackerTheme.RESET}")
        return True
    
    def soft_restart(self, package: str):
        """Reinício suave de um pacote específico"""
        current_time = time.time()
        
        # Verifica cooldown
        if package in self.cooldown and current_time < self.cooldown[package]:
            remaining = self.cooldown[package] - current_time
            print(f"{HackerTheme.YELLOW}[COOLDOWN] {package} ({remaining:.0f}s){HackerTheme.RESET}")
            return False
        
        print(f"{HackerTheme.ORANGE}[REINICIANDO] {package}{HackerTheme.RESET}")
        
        # Encontra posição original deste pacote
        position = None
        if package in self.config["packages"]:
            idx = self.config["packages"].index(package)
            if idx < len(self.window_positions):
                position = self.window_positions[idx]
        
        # Reinicia
        success = self.open_organized(package, position)
        
        # Aplica cooldown
        self.cooldown[package] = time.time() + self.config["cooldown_time"]
        self.lowcpu_count[package] = 0
        
        return success
    
    def reorganize_windows(self):
        """Reorganiza todas as janelas abertas"""
        print(f"\n{HackerTheme.GREEN}🔄 REORGANIZANDO JANELAS{HackerTheme.RESET}")
        
        packages = self.config["packages"]
        self.window_positions = WindowOrganizer.calculate_grid_positions(len(packages))
        
        for i, package in enumerate(packages):
            pid = self.get_pid(package)
            if pid:  # Só reorganiza se estiver aberto
                position = self.window_positions[i] if i < len(self.window_positions) else None
                if position:
                    WindowOrganizer.set_window_position(package, position)
        
        print(f"{HackerTheme.GREEN}✅ Janelas reorganizadas{HackerTheme.RESET}")
    
    def monitor(self):
        """Loop principal de monitoramento"""
        print(f"\n{HackerTheme.GREEN}🎮 INICIANDO MONITOR ORGANIZADO{HackerTheme.RESET}")
        print(f"{HackerTheme.CYAN}• Pacotes: {len(self.config['packages'])}")
        print(f"• CPU limite: {self.config['low_cpu_threshold']}%")
        print(f"• Intervalo: {self.config['check_interval']}s{HackerTheme.RESET}")
        print(f"{HackerTheme.PURPLE}{'='*60}{HackerTheme.RESET}\n")
        
        # Inicializa todos organizados
        self.restart_all_organized()
        
        cycle = 0
        while self.running:
            cycle += 1
            
            print(f"\n{HackerTheme.CYAN}🔄 CICLO {cycle} - {datetime.now().strftime('%H:%M:%S')}{HackerTheme.RESET}")
            
            for package in self.config["packages"]:
                pid = self.get_pid(package)
                
                if not pid:
                    print(f"{HackerTheme.RED}[OFFLINE] {package}{HackerTheme.RESET}")
                    self.soft_restart(package)
                    continue
                
                cpu = self.get_cpu_usage(pid)
                
                if cpu <= self.config["low_cpu_threshold"]:
                    self.lowcpu_count[package] = self.lowcpu_count.get(package, 0) + 1
                    
                    if self.lowcpu_count[package] >= self.max_count:
                        print(f"{HackerTheme.ORANGE}[CPU BAIXA] {package}: {cpu:.1f}% (reiniciando){HackerTheme.RESET}")
                        self.soft_restart(package)
                    else:
                        print(f"{HackerTheme.YELLOW}[MONITOR] {package}: {cpu:.1f}% "
                              f"({self.lowcpu_count[package]}/{self.max_count}){HackerTheme.RESET}")
                else:
                    self.lowcpu_count[package] = 0
                    print(f"{HackerTheme.GREEN}[OK] {package}: {cpu:.1f}%{HackerTheme.RESET}")
            
            # Contagem regressiva
            for i in range(self.config["check_interval"], 0, -1):
                print(f"\r{HackerTheme.PURPLE}⏳ Próxima verificação em {i:02d}s...{HackerTheme.RESET}", end="")
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
                # Garante valores padrão
                defaults = DEFAULT_CONFIG.copy()
                defaults.update(config)
                return defaults
        except:
            pass
    
    return DEFAULT_CONFIG.copy()

def save_config(config: dict):
    """Salva configuração"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def detect_packages():
    """Detecta pacotes Roblox automaticamente"""
    print(f"\n{HackerTheme.CYAN}🔍 DETECTANDO PACOTES ROBLOX{HackerTheme.RESET}")
    
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
                if "com.roblox" in line.lower():
                    pkg = line.replace("package:", "").strip()
                    packages.append(pkg)
        
        if packages:
            print(f"{HackerTheme.GREEN}✅ Encontrados {len(packages)} pacotes:{HackerTheme.RESET}")
            for pkg in packages:
                print(f"  {HackerTheme.CYAN}• {pkg}{HackerTheme.RESET}")
            return packages
        else:
            print(f"{HackerTheme.RED}❌ Nenhum pacote encontrado{HackerTheme.RESET}")
            return []
            
    except Exception as e:
        print(f"{HackerTheme.RED}❌ Erro: {str(e)}{HackerTheme.RESET}")
        return []

# ============================================
# 📱 MENU PRINCIPAL SIMPLES
# ============================================
def main_menu():
    """Menu principal simples"""
    
    while True:
        HackerTheme.print_banner()
        
        config = load_config()
        
        print(f"\n{HackerTheme.CYAN}📊 STATUS DO SISTEMA{HackerTheme.RESET}")
        print(f"{HackerTheme.GREEN}• Pacotes: {len(config.get('packages', []))}")
        print(f"• CPU limite: {config['low_cpu_threshold']}%")
        print(f"• Intervalo: {config['check_interval']}s{HackerTheme.RESET}")
        print(f"\n{HackerTheme.PURPLE}{'='*60}{HackerTheme.RESET}")
        
        print(f"\n{HackerTheme.CYAN}📋 MENU PRINCIPAL{HackerTheme.RESET}")
        print(f"{HackerTheme.GREEN}1. 🚀 Iniciar Monitoramento (Organizado)")
        print(f"2. 🔍 Detectar Pacotes Automaticamente")
        print(f"3. 🎮 Testar Organização (Abre Todos)")
        print(f"4. 🔧 Configurar Link VIP")
        print(f"5. 🧹 Limpar Configuração")
        print(f"6. 📊 Verificar Conexão ADB")
        print(f"7. ❌ Sair{HackerTheme.RESET}")
        print(f"\n{HackerTheme.PURPLE}{'='*60}{HackerTheme.RESET}")
        
        try:
            choice = input(f"\n{HackerTheme.CYAN}▶ Escolha (1-7): {HackerTheme.RESET}").strip()
            
            if choice == "1":
                # Iniciar monitoramento
                if not config.get("packages"):
                    print(f"\n{HackerTheme.RED}❌ Nenhum pacote configurado!{HackerTheme.RESET}")
                    input(f"{HackerTheme.YELLOW}Pressione Enter...{HackerTheme.RESET}")
                    continue
                
                monitor = OrganizedMonitor(config)
                monitor.monitor()
                
            elif choice == "2":
                # Detectar pacotes
                packages = detect_packages()
                if packages:
                    config["packages"] = packages
                    save_config(config)
                    print(f"\n{HackerTheme.GREEN}✅ Configuração salva!{HackerTheme.RESET}")
                input(f"\n{HackerTheme.YELLOW}Pressione Enter...{HackerTheme.RESET}")
                
            elif choice == "3":
                # Testar organização
                if not config.get("packages"):
                    print(f"\n{HackerTheme.RED}❌ Nenhum pacote configurado!{HackerTheme.RESET}")
                    input(f"{HackerTheme.YELLOW}Pressione Enter...{HackerTheme.RESET}")
                    continue
                
                monitor = OrganizedMonitor(config)
                monitor.restart_all_organized()
                input(f"\n{HackerTheme.YELLOW}Pressione Enter...{HackerTheme.RESET}")
                
            elif choice == "4":
                # Configurar link VIP
                print(f"\n{HackerTheme.CYAN}🔧 CONFIGURAR LINK VIP{HackerTheme.RESET}")
                print(f"{HackerTheme.GREEN}Link atual: {config['web_link'][:50]}...{HackerTheme.RESET}")
                
                new_link = input(f"\n{HackerTheme.CYAN}Novo link (ou Enter para manter): {HackerTheme.RESET}").strip()
                if new_link:
                    config['web_link'] = new_link
                    save_config(config)
                    print(f"{HackerTheme.GREEN}✅ Link atualizado!{HackerTheme.RESET}")
                
                input(f"\n{HackerTheme.YELLOW}Pressione Enter...{HackerTheme.RESET}")
                
            elif choice == "5":
                # Limpar configuração
                confirm = input(f"\n{HackerTheme.RED}⚠️  Tem certeza? (s/n): {HackerTheme.RESET}").lower()
                if confirm == 's':
                    config = DEFAULT_CONFIG.copy()
                    save_config(config)
                    print(f"{HackerTheme.GREEN}✅ Configuração limpa!{HackerTheme.RESET}")
                input(f"\n{HackerTheme.YELLOW}Pressione Enter...{HackerTheme.RESET}")
                
            elif choice == "6":
                # Verificar ADB
                print(f"\n{HackerTheme.CYAN}📊 VERIFICANDO CONEXÃO ADB{HackerTheme.RESET}")
                
                try:
                    result = subprocess.run(
                        ["adb", "devices"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    
                    if result.returncode == 0:
                        print(f"\n{HackerTheme.GREEN}✅ ADB Conectado:{HackerTheme.RESET}")
                        print(f"{HackerTheme.CYAN}{result.stdout}{HackerTheme.RESET}")
                    else:
                        print(f"\n{HackerTheme.RED}❌ ADB não encontrado{HackerTheme.RESET}")
                        
                except Exception as e:
                    print(f"\n{HackerTheme.RED}❌ Erro: {str(e)}{HackerTheme.RESET}")
                
                input(f"\n{HackerTheme.YELLOW}Pressione Enter...{HackerTheme.RESET}")
                
            elif choice == "7":
                # Sair
                print(f"\n{HackerTheme.GREEN}👋 Até logo!{HackerTheme.RESET}")
                sys.exit(0)
                
            else:
                print(f"\n{HackerTheme.RED}❌ Opção inválida!{HackerTheme.RESET}")
                time.sleep(1)
                
        except KeyboardInterrupt:
            print(f"\n{HackerTheme.RED}⚠️  Interrompido pelo usuário{HackerTheme.RESET}")
            time.sleep(1)

# ============================================
# 🚀 INICIALIZAÇÃO
# ============================================
def main():
    """Função principal"""
    try:
        # Limpa tela
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # Banner
        HackerTheme.print_banner()
        
        # Verificação rápida
        print(f"\n{HackerTheme.CYAN}🔧 VERIFICANDO AMBIENTE...{HackerTheme.RESET}")
        
        try:
            subprocess.run(["adb", "--version"], capture_output=True)
            print(f"{HackerTheme.GREEN}✅ ADB disponível{HackerTheme.RESET}")
        except:
            print(f"{HackerTheme.RED}❌ ADB não encontrado{HackerTheme.RESET}")
        
        time.sleep(1)
        
        # Menu principal
        main_menu()
        
    except KeyboardInterrupt:
        print(f"\n{HackerTheme.RED}👋 Programa encerrado{HackerTheme.RESET}")
    except Exception as e:
        print(f"\n{HackerTheme.RED}💥 ERRO: {str(e)}{HackerTheme.RESET}")

# ============================================
# 🔧 EXECUÇÃO
# ============================================
if __name__ == "__main__":
    main()
