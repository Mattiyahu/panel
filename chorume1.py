#!/usr/bin/env python3
"""
🎮 Roblox AutoRejoin - Stable Version 🎮
Versão simplificada e estável que monitora sem bagunçar
Versão: 7.0 - Stable
"""

import os
import sys
import time
import json
import signal
import subprocess
from datetime import datetime
from typing import Dict, List, Optional

# ============================================
# 🎨 TEMA SIMPLES
# ============================================
class SimpleUI:
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
    WHITE = "\033[38;5;15m"
    
    @staticmethod
    def clear():
        os.system('cls' if os.name == 'nt' else 'clear')
    
    @staticmethod
    def print_header():
        SimpleUI.clear()
        print(f"""
{SimpleUI.CYAN}{SimpleUI.BOLD}
╔═══════════════════════════════════════════════════╗
║                                                   ║
║          ROBLOX AUTOREJOIN - STABLE               ║
║               Version 7.0                         ║
║                                                   ║
║    • Monitoramento Estável                        ║
║    • Sem Bagunçar Janelas                         ║
║    • Reinício Individual                          ║
║                                                   ║
╚═══════════════════════════════════════════════════╝
{SimpleUI.RESET}""")
    
    @staticmethod
    def print_log(icon: str, message: str, color: str = ""):
        timestamp = datetime.now().strftime("%H:%M:%S")
        color_code = color if color else SimpleUI.WHITE
        print(f"{SimpleUI.PURPLE}[{timestamp}] {color_code}{icon} {message}{SimpleUI.RESET}")

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
    "open_delay": 3,  # Delay entre aberturas
    "max_retries": 3   # Tentativas de reabertura
}

# ============================================
# 🎮 MONITOR ESTÁVEL
# ============================================
class StableMonitor:
    """Monitor estável que não tenta organizar janelas"""
    
    def __init__(self, config: dict):
        self.config = config
        self.lowcpu_count: Dict[str, int] = {}
        self.cooldown: Dict[str, float] = {}
        self.retry_count: Dict[str, int] = {}
        self.max_count = config["max_lowcpu_time"] // config["check_interval"]
        self.running = True
        
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        SimpleUI.print_log("🛑", "Monitoramento interrompido", SimpleUI.RED)
        self.running = False
    
    def run_adb(self, command: str, timeout: int = 5) -> str:
        """Executa comando ADB com tratamento de erro"""
        try:
            result = subprocess.run(
                ["adb"] + command.split(),
                capture_output=True,
                text=True,
                timeout=timeout
            )
            if result.returncode != 0:
                return ""
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            SimpleUI.print_log("⏱️", f"Timeout no comando: {command}", SimpleUI.YELLOW)
            return ""
        except Exception as e:
            SimpleUI.print_log("⚠", f"Erro ADB: {str(e)}", SimpleUI.YELLOW)
            return ""
    
    def get_pid(self, package: str) -> Optional[str]:
        """Obtém PID do pacote de forma segura"""
        return self.run_adb(f"shell pidof {package}")
    
    def get_cpu_usage(self, pid: str) -> float:
        """Obtém uso de CPU do processo"""
        try:
            # Método mais confiável
            cmd = f"shell ps -p {pid} -o %cpu 2>/dev/null || echo '0.0'"
            output = self.run_adb(cmd)
            
            if output:
                # Extrai o valor numérico
                lines = output.strip().split('\n')
                if len(lines) >= 2:
                    cpu_str = lines[1].strip().replace(',', '.')
                    try:
                        return float(cpu_str)
                    except ValueError:
                        pass
            
            # Fallback: tenta com top
            cmd = "shell top -n 1 -b | grep -E '^" + pid + "' || echo ''"
            output = self.run_adb(cmd, timeout=3)
            
            if output and len(output.split()) >= 9:
                cpu_str = output.split()[8].replace(',', '.').replace('%', '')
                try:
                    return float(cpu_str)
                except ValueError:
                    pass
                    
        except Exception as e:
            SimpleUI.print_log("⚠", f"Erro ao ler CPU: {str(e)}", SimpleUI.YELLOW)
        
        return 0.0
    
    def open_roblox_safe(self, package: str) -> bool:
        """
        Abre um Roblox de forma SEGURA e SIMPLES.
        NÃO tenta organizar janelas, NÃO tenta redimensionar.
        """
        SimpleUI.print_log("▶", f"Abrindo {package}", SimpleUI.BLUE)
        
        # 1. Fecha suavemente se estiver aberto
        current_pid = self.get_pid(package)
        if current_pid:
            SimpleUI.print_log("⏹️", f"Fechando {package} (PID: {current_pid})", SimpleUI.YELLOW)
            self.run_adb(f"shell am force-stop {package}")
            time.sleep(1)
        
        # 2. Limpa APENAS cache (NUNCA dados completos!)
        self.run_adb(f"shell pm clear --cache-only {package}")
        time.sleep(0.5)
        
        # 3. Abre o VIP (método mais simples possível)
        cmd = f"shell am start -n {package}/com.roblox.client.ActivityProtocolLaunch -a android.intent.action.VIEW -d \"{self.config['web_link']}\""
        
        SimpleUI.print_log("🚀", f"Iniciando Roblox...", SimpleUI.CYAN)
        result = self.run_adb(cmd, timeout=10)
        
        # 4. Aguarda CARREGAMENTO (tempo mais longo)
        SimpleUI.print_log("⏳", f"Aguardando carregamento (8s)...", SimpleUI.PURPLE)
        time.sleep(8)
        
        # 5. Verifica se abriu
        new_pid = self.get_pid(package)
        
        if new_pid:
            SimpleUI.print_log("✅", f"{package} aberto com sucesso (PID: {new_pid})", SimpleUI.GREEN)
            
            # Verifica se realmente está respondendo (CPU > 0)
            time.sleep(2)
            cpu = self.get_cpu_usage(new_pid)
            if cpu > 0:
                SimpleUI.print_log("📈", f"CPU inicial: {cpu:.1f}%", SimpleUI.GREEN)
            else:
                SimpleUI.print_log("⚠", f"CPU zerada, pode estar travado", SimpleUI.YELLOW)
            
            return True
        else:
            SimpleUI.print_log("❌", f"Falha ao abrir {package}", SimpleUI.RED)
            return False
    
    def restart_with_retry(self, package: str) -> bool:
        """Tenta reiniciar com retry limitado"""
        if package not in self.retry_count:
            self.retry_count[package] = 0
        
        max_retries = self.config.get("max_retries", 3)
        
        if self.retry_count[package] >= max_retries:
            SimpleUI.print_log("⚠", f"Máximo de tentativas atingido para {package}", SimpleUI.ORANGE)
            return False
        
        self.retry_count[package] += 1
        
        SimpleUI.print_log("🔄", f"Tentativa {self.retry_count[package]}/{max_retries} para {package}", SimpleUI.ORANGE)
        
        success = self.open_roblox_safe(package)
        
        if success:
            self.retry_count[package] = 0
            self.cooldown[package] = time.time() + self.config["cooldown_time"]
            self.lowcpu_count[package] = 0
        else:
            # Aguarda antes de tentar novamente
            retry_delay = self.retry_count[package] * 2  # Delay exponencial
            SimpleUI.print_log("⏳", f"Aguardando {retry_delay}s para próxima tentativa...", SimpleUI.YELLOW)
            time.sleep(retry_delay)
        
        return success
    
    def initialize_all(self):
        """Inicializa todos os Roblox de forma sequencial e segura"""
        packages = self.config["packages"]
        
        if not packages:
            SimpleUI.print_log("❌", "Nenhum pacote configurado!", SimpleUI.RED)
            return False
        
        SimpleUI.print_log("🎮", f"Inicializando {len(packages)} Roblox...", SimpleUI.CYAN)
        print(f"{SimpleUI.PURPLE}{'='*60}{SimpleUI.RESET}")
        
        success_count = 0
        
        for i, package in enumerate(packages):
            SimpleUI.print_log(f"{i+1}/{len(packages)}", f"Processando {package}", SimpleUI.WHITE)
            
            # Verifica se já está aberto
            pid = self.get_pid(package)
            if pid:
                SimpleUI.print_log("ℹ️", f"Já está aberto (PID: {pid})", SimpleUI.GREEN)
                success_count += 1
            else:
                # Tenta abrir
                if self.open_roblox_safe(package):
                    success_count += 1
            
            # Delay entre aberturas (IMPORTANTE!)
            if i < len(packages) - 1:
                delay = self.config.get("open_delay", 3)
                SimpleUI.print_log("⏳", f"Aguardando {delay}s...", SimpleUI.PURPLE)
                time.sleep(delay)
        
        print(f"{SimpleUI.PURPLE}{'='*60}{SimpleUI.RESET}")
        
        status_color = SimpleUI.GREEN if success_count == len(packages) else SimpleUI.YELLOW
        SimpleUI.print_log("📊", f"Resultado: {success_count}/{len(packages)} sucessos", status_color)
        
        return success_count > 0
    
    def check_package_health(self, package: str) -> Dict:
        """Verifica saúde de um pacote"""
        pid = self.get_pid(package)
        
        result = {
            "package": package,
            "pid": pid,
            "running": pid is not None,
            "cpu": 0.0,
            "needs_restart": False,
            "status": "UNKNOWN"
        }
        
        if pid:
            cpu = self.get_cpu_usage(pid)
            result["cpu"] = cpu
            
            if cpu <= self.config["low_cpu_threshold"]:
                self.lowcpu_count[package] = self.lowcpu_count.get(package, 0) + 1
                result["lowcpu_count"] = self.lowcpu_count[package]
                
                if self.lowcpu_count[package] >= self.max_count:
                    result["needs_restart"] = True
                    result["status"] = "STUCK"
                else:
                    result["status"] = "LOW_CPU"
            else:
                self.lowcpu_count[package] = 0
                result["status"] = "HEALTHY"
        else:
            result["status"] = "OFFLINE"
            result["needs_restart"] = True
        
        return result
    
    def monitor(self):
        """Loop principal de monitoramento"""
        SimpleUI.print_log("🎯", "INICIANDO MONITORAMENTO ESTÁVEL", SimpleUI.CYAN)
        print(f"{SimpleUI.BLUE}• CPU limite: {self.config['low_cpu_threshold']}%")
        print(f"• Intervalo: {self.config['check_interval']}s")
        print(f"• Pacotes: {len(self.config['packages'])}")
        print(f"• Delay: {self.config.get('open_delay', 3)}s entre aberturas{SimpleUI.RESET}")
        print(f"{SimpleUI.PURPLE}{'='*60}{SimpleUI.RESET}")
        
        # Inicialização
        self.initialize_all()
        
        cycle = 0
        while self.running:
            cycle += 1
            
            print(f"\n{SimpleUI.CYAN}{SimpleUI.BOLD}═══════ CICLO {cycle} • {datetime.now().strftime('%H:%M:%S')} ═══════{SimpleUI.RESET}")
            
            all_healthy = True
            
            for package in self.config["packages"]:
                # Verifica cooldown
                current_time = time.time()
                if package in self.cooldown and current_time < self.cooldown[package]:
                    remaining = int(self.cooldown[package] - current_time)
                    SimpleUI.print_log("⏸️", f"{package} em cooldown ({remaining}s)", SimpleUI.PURPLE)
                    continue
                
                # Verifica saúde
                health = self.check_package_health(package)
                
                if health["status"] == "OFFLINE":
                    SimpleUI.print_log("❌", f"{package} OFFLINE", SimpleUI.RED)
                    self.restart_with_retry(package)
                    all_healthy = False
                    
                elif health["status"] == "STUCK":
                    SimpleUI.print_log("⚠", f"{package} TRAVADO (CPU: {health['cpu']:.1f}%)", SimpleUI.ORANGE)
                    self.restart_with_retry(package)
                    all_healthy = False
                    
                elif health["status"] == "LOW_CPU":
                    count = health.get("lowcpu_count", 0)
                    SimpleUI.print_log("📉", f"{package}: {health['cpu']:.1f}% ({count}/{self.max_count})", SimpleUI.YELLOW)
                    all_healthy = False
                    
                elif health["status"] == "HEALTHY":
                    cpu_color = SimpleUI.GREEN if health['cpu'] > 15 else SimpleUI.CYAN
                    SimpleUI.print_log("✅", f"{package}: {cpu_color}{health['cpu']:.1f}%{SimpleUI.RESET}")
                    
                else:
                    SimpleUI.print_log("❓", f"{package}: status desconhecido", SimpleUI.WHITE)
            
            # Status geral do ciclo
            if all_healthy:
                cycle_status = f"{SimpleUI.GREEN}TODOS SAUDÁVEIS{SimpleUI.RESET}"
            else:
                cycle_status = f"{SimpleUI.YELLOW}ALGUM PROBLEMA{SimpleUI.RESET}"
            
            print(f"\n{SimpleUI.PURPLE}• Status do ciclo: {cycle_status}")
            
            # Contagem regressiva
            interval = self.config["check_interval"]
            for i in range(interval, 0, -1):
                print(f"\r{SimpleUI.BLUE}⏳ Próxima verificação em {i:02d}s...{' ' * 10}{SimpleUI.RESET}", end="")
                time.sleep(1)
            
            print()

# ============================================
# ⚙️ GERENCIAMENTO DE CONFIGURAÇÃO
# ============================================
def load_config() -> dict:
    """Carrega configuração do arquivo"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # Mescla com valores padrão
                for key, value in DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value
                return config
        except Exception as e:
            SimpleUI.print_log("⚠", f"Erro ao carregar config: {str(e)}", SimpleUI.YELLOW)
    
    return DEFAULT_CONFIG.copy()

def save_config(config: dict):
    """Salva configuração no arquivo"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        SimpleUI.print_log("💾", "Configuração salva", SimpleUI.GREEN)
    except Exception as e:
        SimpleUI.print_log("❌", f"Erro ao salvar config: {str(e)}", SimpleUI.RED)

def detect_packages() -> List[str]:
    """Detecta pacotes Roblox automaticamente"""
    SimpleUI.print_log("🔍", "Procurando pacotes Roblox...", SimpleUI.CYAN)
    
    packages = []
    
    try:
        # Tenta listar todos os pacotes
        result = subprocess.run(
            ["adb", "shell", "pm", "list", "packages"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                line = line.strip()
                if line.startswith("package:") and "roblox" in line.lower():
                    pkg = line.replace("package:", "").strip()
                    packages.append(pkg)
        
        if packages:
            SimpleUI.print_log("✅", f"Encontrados {len(packages)} pacotes:", SimpleUI.GREEN)
            for i, pkg in enumerate(packages, 1):
                print(f"  {SimpleUI.BLUE}{i:2d}. {pkg}{SimpleUI.RESET}")
        else:
            SimpleUI.print_log("❌", "Nenhum pacote Roblox encontrado", SimpleUI.RED)
            SimpleUI.print_log("💡", "Instale o Roblox no dispositivo primeiro", SimpleUI.YELLOW)
            
    except Exception as e:
        SimpleUI.print_log("❌", f"Erro na detecção: {str(e)}", SimpleUI.RED)
    
    return packages

def test_adb_connection() -> bool:
    """Testa conexão ADB"""
    SimpleUI.print_log("🔌", "Testando conexão ADB...", SimpleUI.CYAN)
    
    try:
        result = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            devices = [line for line in lines if '\tdevice' in line]
            
            if devices:
                SimpleUI.print_log("✅", f"{len(devices)} dispositivo(s) conectado(s)", SimpleUI.GREEN)
                print(f"{SimpleUI.BLUE}{result.stdout}{SimpleUI.RESET}")
                return True
            else:
                SimpleUI.print_log("❌", "Nenhum dispositivo conectado", SimpleUI.RED)
                print(f"{SimpleUI.YELLOW}Conecte um dispositivo e ative a depuração USB{SimpleUI.RESET}")
                return False
        else:
            SimpleUI.print_log("❌", "ADB não encontrado ou com erro", SimpleUI.RED)
            return False
            
    except Exception as e:
        SimpleUI.print_log("❌", f"Erro: {str(e)}", SimpleUI.RED)
        return False

def setup_configuration():
    """Configura o sistema"""
    SimpleUI.print_log("⚙️", "Configuração do Sistema", SimpleUI.CYAN)
    
    config = load_config()
    
    print(f"\n{SimpleUI.WHITE}1. Link VIP:")
    print(f"   {SimpleUI.BLUE}Atual: {config['web_link'][:50]}...{SimpleUI.RESET}")
    
    change = input(f"   {SimpleUI.CYAN}Alterar? (s/n): {SimpleUI.RESET}").strip().lower()
    if change == 's':
        new_link = input(f"   {SimpleUI.CYAN}Novo link VIP: {SimpleUI.RESET}").strip()
        if new_link:
            config['web_link'] = new_link
    
    print(f"\n{SimpleUI.WHITE}2. Delay entre aberturas:")
    print(f"   {SimpleUI.BLUE}Atual: {config.get('open_delay', 3)}s{SimpleUI.RESET}")
    
    delay = input(f"   {SimpleUI.CYAN}Novo delay (3-10) [{config.get('open_delay', 3)}]: {SimpleUI.RESET}").strip()
    if delay.isdigit() and 3 <= int(delay) <= 10:
        config['open_delay'] = int(delay)
    
    print(f"\n{SimpleUI.WHITE}3. Limite de CPU:")
    print(f"   {SimpleUI.BLUE}Atual: {config['low_cpu_threshold']}%{SimpleUI.RESET}")
    
    cpu_limit = input(f"   {SimpleUI.CYAN}Novo limite (5-20) [{config['low_cpu_threshold']}]: {SimpleUI.RESET}").strip()
    if cpu_limit.replace('.', '').isdigit() and 5 <= float(cpu_limit) <= 20:
        config['low_cpu_threshold'] = float(cpu_limit)
    
    save_config(config)
    SimpleUI.print_log("✅", "Configuração atualizada", SimpleUI.GREEN)

# ============================================
# 📱 MENU PRINCIPAL
# ============================================
def main_menu():
    """Menu principal"""
    
    while True:
        SimpleUI.print_header()
        
        config = load_config()
        
        # Status
        print(f"\n{SimpleUI.CYAN}📊 STATUS DO SISTEMA{SimpleUI.RESET}")
        print(f"{SimpleUI.WHITE}• Pacotes: {len(config.get('packages', []))}")
        print(f"• CPU limite: {config['low_cpu_threshold']}%")
        print(f"• Intervalo: {config['check_interval']}s")
        print(f"• Delay: {config.get('open_delay', 3)}s")
        print(f"• Link: {config['web_link'][:40]}...{SimpleUI.RESET}")
        
        print(f"\n{SimpleUI.PURPLE}{'='*55}{SimpleUI.RESET}")
        print(f"{SimpleUI.CYAN}📋 MENU{SimpleUI.RESET}")
        print(f"{SimpleUI.GREEN}1. 🚀 Iniciar Monitoramento")
        print(f"2. 🔍 Detectar Pacotes")
        print(f"3. ⚙️  Configurar")
        print(f"4. 🔌 Testar Conexão ADB")
        print(f"5. 🎮 Abrir Todos (Teste)")
        print(f"6. 🧹 Limpar Config")
        print(f"7. ❌ Sair{SimpleUI.RESET}")
        print(f"\n{SimpleUI.PURPLE}{'='*55}{SimpleUI.RESET}")
        
        try:
            choice = input(f"\n{SimpleUI.CYAN}▶ Escolha (1-7): {SimpleUI.RESET}").strip()
            
            if choice == "1":
                # Iniciar monitoramento
                if not config.get("packages"):
                    SimpleUI.print_log("❌", "Nenhum pacote configurado!", SimpleUI.RED)
                    input(f"{SimpleUI.YELLOW}Pressione Enter...{SimpleUI.RESET}")
                    continue
                
                if not test_adb_connection():
                    input(f"{SimpleUI.YELLOW}Pressione Enter...{SimpleUI.RESET}")
                    continue
                
                monitor = StableMonitor(config)
                monitor.monitor()
                
            elif choice == "2":
                # Detectar pacotes
                if not test_adb_connection():
                    input(f"{SimpleUI.YELLOW}Pressione Enter...{SimpleUI.RESET}")
                    continue
                
                packages = detect_packages()
                if packages:
                    config["packages"] = packages
                    save_config(config)
                input(f"{SimpleUI.YELLOW}Pressione Enter...{SimpleUI.RESET}")
                
            elif choice == "3":
                # Configurar
                setup_configuration()
                input(f"{SimpleUI.YELLOW}Pressione Enter...{SimpleUI.RESET}")
                
            elif choice == "4":
                # Testar ADB
                test_adb_connection()
                input(f"{SimpleUI.YELLOW}Pressione Enter...{SimpleUI.RESET}")
                
            elif choice == "5":
                # Abrir todos (teste)
                if not config.get("packages"):
                    SimpleUI.print_log("❌", "Nenhum pacote configurado!", SimpleUI.RED)
                    input(f"{SimpleUI.YELLOW}Pressione Enter...{SimpleUI.RESET}")
                    continue
                
                if not test_adb_connection():
                    input(f"{SimpleUI.YELLOW}Pressione Enter...{SimpleUI.RESET}")
                    continue
                
                monitor = StableMonitor(config)
                monitor.initialize_all()
                input(f"{SimpleUI.YELLOW}Pressione Enter...{SimpleUI.RESET}")
                
            elif choice == "6":
                # Limpar config
                confirm = input(f"{SimpleUI.RED}⚠️  Tem certeza? (s/n): {SimpleUI.RESET}").lower()
                if confirm == 's':
                    config = DEFAULT_CONFIG.copy()
                    save_config(config)
                    SimpleUI.print_log("✅", "Configuração limpa", SimpleUI.GREEN)
                input(f"{SimpleUI.YELLOW}Pressione Enter...{SimpleUI.RESET}")
                
            elif choice == "7":
                # Sair
                print(f"\n{SimpleUI.GREEN}👋 Até logo!{SimpleUI.RESET}")
                sys.exit(0)
                
            else:
                print(f"\n{SimpleUI.RED}❌ Opção inválida!{SimpleUI.RESET}")
                time.sleep(1)
                
        except KeyboardInterrupt:
            print(f"\n{SimpleUI.RED}⚠️  Interrompido{SimpleUI.RESET}")
            time.sleep(1)

# ============================================
# 🚀 INICIALIZAÇÃO
# ============================================
def main():
    """Função principal"""
    try:
        main_menu()
    except KeyboardInterrupt:
        print(f"\n{SimpleUI.RED}👋 Programa encerrado{SimpleUI.RESET}")
    except Exception as e:
        print(f"\n{SimpleUI.RED}💥 ERRO CRÍTICO: {str(e)}{SimpleUI.RESET}")

if __name__ == "__main__":
    main()
