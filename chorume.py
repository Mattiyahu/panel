#!/usr/bin/env python3
"""
🌿 Roblox AutoRejoin - Nature Theme 🌿
Interface verdejante para monitoramento de múltiplos Roblox
Versão: 3.0 - Nature Theme
"""

import os
import sys
import time
import json
import signal
import subprocess
import platform
from datetime import datetime
from typing import Dict, List, Optional
import urllib.request
import zipfile
import io

# ============================================
# 🌈 CONFIGURAÇÃO DO TEMA NATURE
# ============================================
class NatureTheme:
    """Paleta de cores inspirada na natureza"""
    # Cores ANSI em tons de verde
    RESET = "\033[0m"
    BOLD = "\033[1m"
    
    # Tons de verde
    MOSS = "\033[38;5;22m"       # Verde musgo escuro
    FOREST = "\033[38;5;28m"     # Verde floresta
    SPRING = "\033[38;5;34m"     # Verde primavera
    LIME = "\033[38;5;46m"       # Verde limão
    MINT = "\033[38;5;121m"      # Verde menta
    SAGE = "\033[38;5;108m"      # Verde sálvia
    EMERALD = "\033[38;5;42m"    # Verde esmeralda
    PINE = "\033[38;5;23m"       # Verde pinho
    
    # Cores de acento
    SUN = "\033[38;5;226m"       # Amarelo sol
    EARTH = "\033[38;5;94m"      # Marrom terra
    WATER = "\033[38;5;33m"      # Azul água
    SKY = "\033[38;5;117m"       # Azul céu
    
    # Fundos
    BG_DARK = "\033[48;5;234m"
    BG_LIGHT = "\033[48;5;238m"
    
    # Símbolos da natureza
    ICONS = {
        "leaf": "🍃", "tree": "🌲", "seed": "🌱", "flower": "🌸",
        "forest": "🌳", "mountain": "⛰️", "river": "🌊", "sun": "☀️",
        "bug": "🐛", "bee": "🐝", "butterfly": "🦋", "bird": "🐦",
        "rock": "🪨", "wood": "🪵", "fire": "🔥", "star": "⭐"
    }

# ============================================
# ⚙️ CONFIGURAÇÃO DO SISTEMA
# ============================================
CONFIG_FILE = "nature_config.json"
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
# 🎨 INTERFACE NATURE
# ============================================
class NatureUI:
    """Interface gráfica no tema Nature"""
    
    @staticmethod
    def clear_screen():
        """Limpa a tela de forma elegante"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    @staticmethod
    def print_header(title: str):
        """Imprime cabeçalho estilizado"""
        NatureUI.clear_screen()
        print(f"\n{NatureTheme.BG_DARK}{NatureTheme.SUN}{'═'*70}{NatureTheme.RESET}")
        print(f"{NatureTheme.BOLD}{NatureTheme.EMERALD}          🌿 {title} 🌿")
        print(f"{NatureTheme.BG_DARK}{NatureTheme.SUN}{'═'*70}{NatureTheme.RESET}\n")
    
    @staticmethod
    def print_box(content: str, color: str = NatureTheme.FOREST, icon: str = ""):
        """Imprime conteúdo em uma caixa estilizada"""
        lines = content.split('\n')
        max_len = max(len(line) for line in lines)
        
        print(f"{color}{NatureTheme.BOLD}╔{'═'*(max_len + 2)}╗{NatureTheme.RESET}")
        for line in lines:
            spaces = max_len - len(line)
            print(f"{color}{NatureTheme.BOLD}║ {icon}{line}{' '*spaces} ║{NatureTheme.RESET}")
        print(f"{color}{NatureTheme.BOLD}╚{'═'*(max_len + 2)}╝{NatureTheme.RESET}")
    
    @staticmethod
    def print_status(package: str, status: str, cpu: float = 0.0, extra: str = ""):
        """Imprime status de um pacote com ícones"""
        icons = {
            "online": f"{NatureTheme.ICONS['tree']}",
            "offline": f"{NatureTheme.ICONS['rock']}",
            "restart": f"{NatureTheme.ICONS['seed']}",
            "warning": f"{NatureTheme.ICONS['bug']}",
            "cooldown": f"{NatureTheme.ICONS['flower']}",
            "success": f"{NatureTheme.ICONS['butterfly']}"
        }
        
        colors = {
            "online": NatureTheme.EMERALD,
            "offline": NatureTheme.EARTH,
            "restart": NatureTheme.SUN,
            "warning": NatureTheme.SUN,
            "cooldown": NatureTheme.SAGE,
            "success": NatureTheme.LIME
        }
        
        icon = icons.get(status, NatureTheme.ICONS['star'])
        color = colors.get(status, NatureTheme.FOREST)
        
        status_text = f"{color}{NatureTheme.BOLD}{icon} {package}"
        if cpu > 0:
            status_text += f" {NatureTheme.WATER}CPU: {cpu:.1f}%"
        if extra:
            status_text += f" {NatureTheme.SKY}{extra}"
        status_text += f"{NatureTheme.RESET}"
        
        print(status_text)
    
    @staticmethod
    def print_menu(options: List[Dict]):
        """Imprime menu interativo"""
        print(f"\n{NatureTheme.PINE}{NatureTheme.BOLD}╔{'═'*40}╗{NatureTheme.RESET}")
        print(f"{NatureTheme.PINE}{NatureTheme.BOLD}║{' '*15}🌲 MENU 🌲{' '*15}║{NatureTheme.RESET}")
        print(f"{NatureTheme.PINE}{NatureTheme.BOLD}╠{'═'*40}╣{NatureTheme.RESET}")
        
        for i, option in enumerate(options, 1):
            icon = option.get('icon', NatureTheme.ICONS['leaf'])
            color = option.get('color', NatureTheme.FOREST)
            print(f"{NatureTheme.PINE}{NatureTheme.BOLD}║{NatureTheme.RESET} "
                  f"{color}{icon} {i}. {option['text']:<33}{NatureTheme.RESET}"
                  f"{NatureTheme.PINE}{NatureTheme.BOLD}║{NatureTheme.RESET}")
        
        print(f"{NatureTheme.PINE}{NatureTheme.BOLD}╚{'═'*40}╝{NatureTheme.RESET}")
    
    @staticmethod
    def loading_animation(text: str, duration: int = 3):
        """Animação de carregamento"""
        frames = ["🌱", "🌿", "🍃", "🌾", "🌳", "🌲"]
        for i in range(duration * 4):
            frame = frames[i % len(frames)]
            print(f"\r{NatureTheme.SPRING}{frame} {text}{'.' * (i % 4)}{' ' * 3}{NatureTheme.RESET}", end="")
            time.sleep(0.25)
        print()

# ============================================
# 🌱 SETUP PARA TERMUX
# ============================================
class TermuxSetup:
    """Configuração automática para Termux"""
    
    @staticmethod
    def is_termux() -> bool:
        """Verifica se está no Termux"""
        return "com.termux" in os.environ.get("PREFIX", "")
    
    @staticmethod
    def install_dependencies():
        """Instala dependências com interface bonita"""
        NatureUI.print_header("Instalando Dependências")
        
        steps = [
            {"icon": "🌱", "text": "Atualizando pacotes Termux", "cmd": ["pkg", "update", "-y"]},
            {"icon": "🌿", "text": "Instalando Android Tools", "cmd": ["pkg", "install", "android-tools", "-y"]},
            {"icon": "🍃", "text": "Instalando Python packages", "cmd": [sys.executable, "-m", "pip", "install", "requests"]},
        ]
        
        for step in steps:
            print(f"\n{NatureTheme.SPRING}{step['icon']} {step['text']}...{NatureTheme.RESET}")
            try:
                result = subprocess.run(step['cmd'], capture_output=True, text=True)
                if result.returncode == 0:
                    print(f"{NatureTheme.EMERALD}✓ Concluído{NatureTheme.RESET}")
                else:
                    print(f"{NatureTheme.SUN}⚠️ Continuando mesmo com aviso{NatureTheme.RESET}")
            except Exception:
                print(f"{NatureTheme.SUN}⚠️ Etapa pulada{NatureTheme.RESET}")
        
        NatureUI.loading_animation("Finalizando instalação")
        print(f"\n{NatureTheme.EMERALD}{NatureTheme.ICONS['butterfly']} Dependências instaladas com sucesso!{NatureTheme.RESET}")

# ============================================
# 🎮 MONITOR ROBLOX
# ============================================
class RobloxMonitor:
    """Monitor inteligente de instâncias Roblox"""
    
    def __init__(self, config: dict):
        self.config = config
        self.proto_activity = "com.roblox.client.ActivityProtocolLaunch"
        self.lowcpu_count: Dict[str, int] = {}
        self.cooldown: Dict[str, float] = {}
        self.max_count = config["max_lowcpu_time"] // config["check_interval"]
        self.running = True
        
        # Signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handler para encerramento gracioso"""
        print(f"\n{NatureTheme.SUN}{NatureTheme.ICONS['flower']} Encerrando monitoramento...{NatureTheme.RESET}")
        self.running = False
    
    def run_adb_command(self, command: str) -> str:
        """Executa comando ADB com segurança"""
        try:
            cmd_parts = ["adb"] + command.split()
            result = subprocess.run(cmd_parts, capture_output=True, text=True, timeout=10)
            return result.stdout.strip()
        except Exception as e:
            return ""
    
    def detect_roblox_packages(self) -> List[str]:
        """Detecta pacotes Roblox automaticamente"""
        NatureUI.print_header("Detectando Pacotes Roblox")
        
        packages = []
        output = self.run_adb_command("shell pm list packages")
        
        if output:
            for line in output.split('\n'):
                if line.startswith("package:") and "com.roblox" in line.lower():
                    pkg = line.replace("package:", "").strip()
                    packages.append(pkg)
        
        if packages:
            print(f"\n{NatureTheme.EMERALD}{NatureTheme.ICONS['forest']} Encontrados {len(packages)} pacotes:{NatureTheme.RESET}")
            for pkg in packages:
                print(f"  {NatureTheme.SPRING}• {pkg}{NatureTheme.RESET}")
        else:
            print(f"\n{NatureTheme.SUN}{NatureTheme.ICONS['rock']} Nenhum pacote encontrado{NatureTheme.RESET}")
        
        return packages
    
    def get_pid(self, package: str) -> Optional[str]:
        """Obtém PID do pacote"""
        return self.run_adb_command(f"shell pidof {package}")
    
    def get_cpu_usage(self, pid: str) -> float:
        """Obtém uso de CPU do processo"""
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
        """Verifica status completo do pacote"""
        pid = self.get_pid(package)
        status = {
            "package": package,
            "pid": pid,
            "running": pid is not None,
            "cpu": 0.0,
            "needs_restart": False
        }
        
        if pid:
            cpu = self.get_cpu_usage(pid)
            status["cpu"] = cpu
            
            if cpu <= self.config["low_cpu_threshold"]:
                self.lowcpu_count[package] = self.lowcpu_count.get(package, 0) + 1
                if self.lowcpu_count[package] >= self.max_count:
                    status["needs_restart"] = True
            else:
                self.lowcpu_count[package] = 0
        
        return status
    
    def soft_restart(self, package: str) -> bool:
        """
        Reinício SUAVE que preserva o login.
        NÃO usa 'pm clear' que apaga dados!
        """
        current_time = time.time()
        
        # Verifica cooldown
        if package in self.cooldown and current_time < self.cooldown[package]:
            remaining = self.cooldown[package] - current_time
            NatureUI.print_status(package, "cooldown", extra=f"⌛ {remaining:.0f}s")
            return False
        
        NatureUI.print_status(package, "restart", extra="🔄 Reiniciando...")
        
        # 1. Apenas força parada (NÃO limpa dados)
        self.run_adb_command(f"shell am force-stop {package}")
        time.sleep(2)
        
        # 2. Limpa APENAS cache (opcional, mas seguro)
        self.run_adb_command(f"shell pm clear --cache-only {package}")
        time.sleep(1)
        
        # 3. Abre o VIP
        success = self.open_vip(package)
        
        # 4. Aplica cooldown
        self.cooldown[package] = time.time() + self.config["cooldown_time"]
        self.lowcpu_count[package] = 0
        
        if success:
            NatureUI.print_status(package, "success", extra="✅ Reiniciado com sucesso")
        else:
            NatureUI.print_status(package, "warning", extra="⚠️ Pode precisar de login")
        
        return success
    
    def open_vip(self, package: str) -> bool:
        """Abre servidor VIP sem apagar login"""
        # APENAS force-stop, NUNCA pm clear completo!
        self.run_adb_command(f"shell am force-stop {package}")
        time.sleep(1.5)
        
        cmd = (f"shell am start -n {package}/{self.proto_activity} "
               f"-a android.intent.action.VIEW -d \"{self.config['web_link']}\"")
        self.run_adb_command(cmd)
        time.sleep(6)
        
        return self.get_pid(package) is not None
    
    def monitor(self):
        """Loop principal de monitoramento"""
        NatureUI.print_header("Monitoramento Nature Ativo")
        
        print(f"{NatureTheme.WATER}╔══════════════════════════════════════════════════════╗")
        print(f"║  🌿  Configuração: {self.config['low_cpu_threshold']}% CPU • {self.config['check_interval']}s • {len(self.config['packages'])} pacotes  🌿  ║")
        print(f"╚══════════════════════════════════════════════════════╝{NatureTheme.RESET}\n")
        
        # Inicialização suave
        for package in self.config["packages"]:
            NatureUI.print_status(package, "online", extra="🌱 Iniciando...")
            self.soft_restart(package)
            time.sleep(3)
        
        cycle = 0
        while self.running:
            cycle += 1
            
            print(f"\n{NatureTheme.PINE}{NatureTheme.BOLD}═══════ Ciclo {cycle} • {datetime.now().strftime('%H:%M:%S')} ═══════{NatureTheme.RESET}")
            
            for package in self.config["packages"]:
                status = self.check_package_status(package)
                
                if not status["running"]:
                    NatureUI.print_status(package, "offline", extra="❌ Offline")
                    self.soft_restart(package)
                    
                elif status["needs_restart"]:
                    NatureUI.print_status(package, "warning", status["cpu"], "⚠️ CPU baixa")
                    self.soft_restart(package)
                    
                elif status["cpu"] <= self.config["low_cpu_threshold"]:
                    count = self.lowcpu_count.get(package, 0)
                    NatureUI.print_status(package, "online", status["cpu"], f"📉 {count}/{self.max_count}")
                    
                else:
                    NatureUI.print_status(package, "online", status["cpu"], "✅ Normal")
            
            # Contagem regressiva elegante
            for i in range(self.config["check_interval"], 0, -1):
                print(f"\r{NatureTheme.SAGE}Aguardando {i}s... {NatureTheme.ICONS['leaf']}{NatureTheme.RESET}", end="")
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
                # Garante valores padrão
                defaults = DEFAULT_CONFIG.copy()
                defaults.update(config)
                return defaults
        except:
            pass
    
    return DEFAULT_CONFIG.copy()

def save_config(config: dict):
    """Salva configuração no arquivo"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def setup_wizard():
    """Assistente de configuração com tema Nature"""
    NatureUI.print_header("Assistente de Configuração")
    
    config = load_config()
    
    # Link VIP
    print(f"\n{NatureTheme.SPRING}1. Link do Servidor VIP:{NatureTheme.RESET}")
    print(f"{NatureTheme.SAGE}Atual: {config['web_link'][:50]}...{NatureTheme.RESET}")
    if input(f"{NatureTheme.MINT}Alterar? (s/n): {NatureTheme.RESET}").lower() == 's':
        config['web_link'] = input(f"{NatureTheme.MINT}Novo link: {NatureTheme.RESET}").strip()
    
    # Webhook
    print(f"\n{NatureTheme.SPRING}2. Webhook Discord:{NatureTheme.RESET}")
    print(f"{NatureTheme.SAGE}Atual: {config['webhook_url'] or 'Não configurado'}{NatureTheme.RESET}")
    if input(f"{NatureTheme.MINT}Configurar? (s/n): {NatureTheme.RESET}").lower() == 's':
        config['webhook_url'] = input(f"{NatureTheme.MINT}URL do webhook: {NatureTheme.RESET}").strip()
    
    # Configurações
    print(f"\n{NatureTheme.SPRING}3. Configurações de Monitoramento:{NatureTheme.RESET}")
    print(f"{NatureTheme.MINT}Manter configurações recomendadas? (8% CPU, 10s intervalo){NatureTheme.RESET}")
    
    if input(f"{NatureTheme.SAGE}(s/n): {NatureTheme.RESET}").lower() == 'n':
        try:
            config['low_cpu_threshold'] = float(input(f"{NatureTheme.MINT}Limite de CPU (%): {NatureTheme.RESET}") or 8.0)
            config['check_interval'] = int(input(f"{NatureTheme.MINT}Intervalo (segundos): {NatureTheme.RESET}") or 10)
            config['cooldown_time'] = int(input(f"{NatureTheme.MINT}Cooldown (segundos): {NatureTheme.RESET}") or 10)
        except:
            print(f"{NatureTheme.SUN}⚠️ Valores inválidos, mantendo padrão{NatureTheme.RESET}")
    
    save_config(config)
    print(f"\n{NatureTheme.EMERALD}{NatureTheme.ICONS['butterfly']} Configuração salva!{NatureTheme.RESET}")
    return config

# ============================================
# 📱 MENU PRINCIPAL
# ============================================
def main_menu():
    """Menu principal com tema Nature"""
    
    menu_options = [
        {"icon": "🌿", "text": "Iniciar Monitoramento", "color": NatureTheme.EMERALD},
        {"icon": "⚙️", "text": "Configurações", "color": NatureTheme.SPRING},
        {"icon": "🔍", "text": "Detectar Pacotes", "color": NatureTheme.MINT},
        {"icon": "📦", "text": "Instalar Dependências", "color": NatureTheme.SAGE},
        {"icon": "📖", "text": "Guia de Conexão", "color": NatureTheme.WATER},
        {"icon": "🌅", "text": "Sair", "color": NatureTheme.SUN}
    ]
    
    while True:
        NatureUI.print_header("Roblox AutoRejoin - Nature Theme")
        
        # Status atual
        config = load_config()
        print(f"{NatureTheme.FOREST}Configuração Atual:{NatureTheme.RESET}")
        print(f"  {NatureTheme.SPRING}• CPU Limite: {config['low_cpu_threshold']}%")
        print(f"  {NatureTheme.MINT}• Intervalo: {config['check_interval']}s")
        print(f"  {NatureTheme.SAGE}• Pacotes: {len(config.get('packages', []))}")
        print(f"  {NatureTheme.WATER}• Webhook: {'✅' if config['webhook_url'] else '❌'}")
        print()
        
        NatureUI.print_menu(menu_options)
        
        try:
            choice = int(input(f"\n{NatureTheme.EMERALD}{NatureTheme.ICONS['leaf']} Escolha (1-6): {NatureTheme.RESET}"))
        except:
            continue
        
        if choice == 1:
            # Iniciar monitoramento
            config = load_config()
            
            if not config.get("packages"):
                print(f"\n{NatureTheme.SUN}{NatureTheme.ICONS['bug']} Nenhum pacote configurado!{NatureTheme.RESET}")
                print(f"{NatureTheme.MINT}Execute 'Detectar Pacotes' primeiro.{NatureTheme.RESET}")
                input(f"\n{NatureTheme.SAGE}Pressione Enter...{NatureTheme.RESET}")
                continue
            
            monitor = RobloxMonitor(config)
            monitor.monitor()
            
        elif choice == 2:
            # Configurações
            setup_wizard()
            
        elif choice == 3:
            # Detectar pacotes
            config = load_config()
            monitor = RobloxMonitor(config)
            packages = monitor.detect_roblox_packages()
            
            if packages:
                config["packages"] = packages
                save_config(config)
                print(f"\n{NatureTheme.EMERALD}{NatureTheme.ICONS['butterfly']} {len(packages)} pacotes salvos!{NatureTheme.RESET}")
            
            input(f"\n{NatureTheme.SAGE}Pressione Enter...{NatureTheme.RESET}")
            
        elif choice == 4:
            # Instalar dependências
            if TermuxSetup.is_termux():
                TermuxSetup.install_dependencies()
            else:
                print(f"\n{NatureTheme.SUN}⚠️ Esta opção é apenas para Termux{NatureTheme.RESET}")
            input(f"\n{NatureTheme.SAGE}Pressione Enter...{NatureTheme.RESET}")
            
        elif choice == 5:
            # Guia de conexão
            NatureUI.print_header("Guia de Conexão")
            guide = """
            1. No dispositivo Android (UghPhone/VSPhone):
               • Configurações > Sistema > Sobre o telefone
               • Toque 7x em 'Número da versão'
               • Volte para Opções do Desenvolvedor
               • Ative 'Depuração USB'
            
            2. Conecte via USB ou Wi-Fi:
               USB: Conecte o cabo e autorize
               Wi-Fi: adb tcpip 5555
                     adb connect IP:5555
            
            3. Teste a conexão:
               adb devices
               (Deve mostrar 'device')
            """
            NatureUI.print_box(guide, NatureTheme.SAGE, "📖")
            input(f"\n{NatureTheme.SAGE}Pressione Enter...{NatureTheme.RESET}")
            
        elif choice == 6:
            # Sair
            print(f"\n{NatureTheme.EMERALD}{NatureTheme.ICONS['flower']} Até logo! Que a natureza esteja com você! 🌿{NatureTheme.RESET}")
            sys.exit(0)

# ============================================
# 🚀 INICIALIZAÇÃO
# ============================================
def main():
    """Função principal"""
    # Verifica ambiente
    if TermuxSetup.is_termux():
        env = "Termux 🌿"
    else:
        env = "Ambiente Padrão"
    
    # Banner inicial
    NatureUI.clear_screen()
    print(f"\n{NatureTheme.BG_DARK}{NatureTheme.SUN}{'═'*70}{NatureTheme.RESET}")
    print(f"{NatureTheme.BOLD}{NatureTheme.EMERALD}")
    print("     🌳🌳🌳🌳🌳🌳🌳🌳🌳🌳🌳🌳🌳🌳🌳🌳🌳🌳")
    print("     🌳                                        🌳")
    print("     🌳      ROBLOX AUTOREJOIN - NATURE       🌳")
    print("     🌳           🌿 Version 3.0 🌿           🌳")
    print("     🌳                                        🌳")
    print("     🌳🌳🌳🌳🌳🌳🌳🌳🌳🌳🌳🌳🌳🌳🌳🌳🌳🌳")
    print(f"{NatureTheme.RESET}")
    print(f"{NatureTheme.BG_DARK}{NatureTheme.SUN}{'═'*70}{NatureTheme.RESET}")
    print(f"{NatureTheme.SAGE}Ambiente: {env} • Data: {datetime.now().strftime('%d/%m/%Y')}{NatureTheme.RESET}")
    print(f"{NatureTheme.MINT}Monitoramento suave que preserva seus logins!{NatureTheme.RESET}")
    
    # Pausa dramática
    time.sleep(2)
    
    # Inicia menu
    main_menu()

# ============================================
# 🔧 EXECUÇÃO
# ============================================
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{NatureTheme.SUN}{NatureTheme.ICONS['flower']} Programa interrompido pelo usuário{NatureTheme.RESET}")
    except Exception as e:
        print(f"\n{NatureTheme.SUN}{NatureTheme.ICONS['bug']} Erro: {e}{NatureTheme.RESET}")
