#!/usr/bin/env python3
"""
Roblox AutoRejoin para Termux (UghPhone/VSPhone) - VERSÃO ATUALIZADA
Monitora e reinicia automaticamente múltiplas instâncias do Roblox.
Configuração: 8% CPU, 10s intervalos, verificação individual
"""

import os
import sys
import time
import json
import signal
import subprocess
import platform
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import urllib.request
import zipfile
import io

# CONFIGURAÇÃO ATUALIZADA
CONFIG_FILE = "autorejoin_config.json"
DEFAULT_CONFIG = {
    "web_link": "https://www.roblox.com/games/1537690962/Bee-Swarm-Simulator?privateServerLinkCode=05888256464342538313491710978310",
    "webhook_url": "",
    "check_interval": 10,  # 10 segundos
    "low_cpu_threshold": 8.0,  # 8%
    "max_lowcpu_time": 10,  # 10 segundos
    "cooldown_time": 10,  # 10 segundos
    "packages": []  # Será preenchido automaticamente
}

class TermuxSetup:
    """Configuração automática para Termux (UghPhone/VSPhone)"""
    
    @staticmethod
    def is_termux() -> bool:
        """Verifica se está executando no Termux"""
        return "com.termux" in os.environ.get("PREFIX", "")
    
    @staticmethod
    def install_termux_adb() -> bool:
        """
        Instala o termux-adb (ADB sem root para Termux).
        """
        print("\n[SETUP] Instalando termux-adb...")
        try:
            # Método alternativo para Termux
            commands = [
                ["pkg", "update", "-y"],
                ["pkg", "install", "android-tools", "-y"],
                ["pkg", "install", "termux-api", "-y"]
            ]
            
            for cmd in commands:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"[AVISO] Comando {' '.join(cmd)} falhou: {result.stderr}")
            
            # Verifica se adb está disponível
            result = subprocess.run(["adb", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                print("[SUCESSO] ADB instalado")
                return True
            else:
                print("[AVISO] Usando adb do Termux")
                return True
                
        except Exception as e:
            print(f"[ERRO] Exceção durante instalação: {e}")
            return False
    
    @staticmethod
    def install_python_packages():
        """Instala pacotes Python necessários"""
        required = ["requests"]
        try:
            import importlib.util
            
            for package in required:
                if importlib.util.find_spec(package) is None:
                    print(f"[SETUP] Instalando {package}...")
                    subprocess.run([sys.executable, "-m", "pip", "install", package], 
                                 capture_output=True)
                    print(f"[OK] {package} instalado")
        except Exception as e:
            print(f"[AVISO] Não foi possível instalar pacotes: {e}")
    
    @staticmethod
    def setup_android_debugging():
        """Guia para habilitar depuração USB no dispositivo"""
        print("\n" + "="*60)
        print("[CONFIGURAÇÃO ANDROID PARA UghPhone/VSPhone]")
        print("="*60)
        print("1. No dispositivo Android:")
        print("   - Configurações > Sistema > Sobre o telefone")
        print("   - Toque 7x em 'Número da versão' para habilitar Opções do desenvolvedor")
        print("   - Volte para Configurações > Sistema > Opções do desenvolvedor")
        print("   - Ative 'Depuração USB'")
        print("   - Ative 'Depuração via Wi-Fi' (se disponível)")
        print("\n2. No Termux, conecte:")
        print("   - Conecte via USB: adb devices")
        print("   - OU conecte via Wi-Fi:")
        print("     adb tcpip 5555")
        print("     adb connect IP_DO_DISPOSITIVO:5555")
        print("\n3. Autorize a conexão no dispositivo quando aparecer")
        print("="*60)

class RobloxMonitor:
    def __init__(self, config: dict):
        self.config = config
        self.proto_activity = "com.roblox.client.ActivityProtocolLaunch"
        self.lowcpu_count: Dict[str, int] = {}
        self.cooldown: Dict[str, float] = {}
        self.max_count = config["max_lowcpu_time"] // config["check_interval"]
        self.running = True
        self.last_check_time: Dict[str, float] = {}
        
        # Usar termux-adb se estiver no Termux
        self.adb_cmd = "adb"
        if TermuxSetup.is_termux():
            self.adb_cmd = "adb"
        
        # Configurar signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        print("\n[INFO] Encerrando monitoramento...")
        self.running = False
    
    def run_adb_command(self, command: str) -> str:
        """Executa um comando ADB e retorna a saída"""
        try:
            cmd_parts = [self.adb_cmd] + command.split()
            result = subprocess.run(cmd_parts, capture_output=True, text=True, timeout=10)
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            print(f"[ERRO] Timeout no comando ADB: {command}")
            return ""
        except FileNotFoundError:
            print(f"[ERRO] {self.adb_cmd} não encontrado. Execute o setup primeiro.")
            return ""
        except Exception as e:
            print(f"[ERRO] Falha ao executar ADB: {e}")
            return ""
    
    def detect_roblox_packages(self) -> List[str]:
        """
        Detecta automaticamente todos os pacotes do Roblox instalados.
        Usa o comando 'pm list packages' para listar pacotes.
        """
        print("[DETECT] Procurando pacotes do Roblox...")
        packages = []
        
        # Lista todos os pacotes
        output = self.run_adb_command("shell pm list packages")
        if not output:
            print("[ERRO] Não foi possível listar pacotes. Verifique conexão ADB.")
            return packages
        
        # Filtra pacotes do Roblox
        roblox_keywords = ["com.roblox", "com.roblox.client", "roblox"]
        for line in output.split('\n'):
            if line.startswith("package:"):
                pkg = line.replace("package:", "").strip()
                if any(keyword in pkg.lower() for keyword in roblox_keywords):
                    packages.append(pkg)
        
        if packages:
            print(f"[DETECT] Encontrados {len(packages)} pacotes:")
            for i, pkg in enumerate(packages, 1):
                print(f"  {i}. {pkg}")
        else:
            print("[DETECT] Nenhum pacote do Roblox encontrado.")
            print("[DETECT] Instale o Roblox no dispositivo primeiro.")
        
        return packages
    
    def get_pid(self, package: str) -> Optional[str]:
        """Obtém o PID do pacote"""
        output = self.run_adb_command(f"shell pidof {package}")
        return output if output else None
    
    def get_cpu_by_pid(self, pid: str) -> float:
        """
        Obtém o uso de CPU pelo PID.
        Nova implementação: usa 'ps -p PID -o %cpu' para maior precisão.
        """
        try:
            # Método mais preciso para obter CPU
            cmd = f"shell ps -p {pid} -o %cpu 2>/dev/null || shell top -n 1 -b | grep '^{pid}'"
            output = self.run_adb_command(cmd)
            
            if not output:
                return 0.0
            
            # Processa a saída para extrair CPU
            for line in output.split('\n'):
                line = line.strip()
                if not line:
                    continue
                    
                # Remove caracteres não numéricos
                import re
                cpu_match = re.search(r'([\d.]+)', line)
                if cpu_match:
                    cpu_str = cpu_match.group(1)
                    try:
                        return float(cpu_str)
                    except ValueError:
                        pass
            
            return 0.0
            
        except Exception as e:
            print(f"[DEBUG] Erro ao obter CPU para PID {pid}: {e}")
            return 0.0
    
    def check_package_running(self, package: str) -> Dict:
        """
        Verifica o status completo de um pacote.
        Retorna dicionário com informações.
        """
        pid = self.get_pid(package)
        status = {
            "package": package,
            "pid": pid,
            "running": pid is not None,
            "cpu": 0.0,
            "needs_restart": False
        }
        
        if pid:
            cpu_usage = self.get_cpu_by_pid(pid)
            status["cpu"] = cpu_usage
            
            # Verifica se CPU está baixa
            if cpu_usage <= self.config["low_cpu_threshold"]:
                self.lowcpu_count[package] = self.lowcpu_count.get(package, 0) + 1
                status["low_cpu_count"] = self.lowcpu_count[package]
                
                # Se CPU baixa atingiu o limite, precisa reiniciar
                if self.lowcpu_count[package] >= self.max_count:
                    status["needs_restart"] = True
            else:
                # CPU normal, resetar contador
                self.lowcpu_count[package] = 0
                status["low_cpu_count"] = 0
        
        return status
    
    def open_vip(self, package: str):
        """
        Abre o servidor VIP no pacote.
        Método otimizado para UghPhone/VSPhone.
        """
        print(f"[OPEN] Abrindo VIP em {package}")
        
        # Fecha qualquer instância anterior
        self.run_adb_command(f"shell am force-stop {package}")
        time.sleep(1.5)
        
        # Limpa cache para garantir limpeza
        self.run_adb_command(f"shell pm clear {package}")
        time.sleep(1)
        
        # Abre o link VIP
        cmd = (
            f"shell am start -n {package}/{self.proto_activity} "
            f"-a android.intent.action.VIEW -d \"{self.config['web_link']}\""
        )
        result = self.run_adb_command(cmd)
        
        # Espera tempo otimizado
        wait_time = 8 if TermuxSetup.is_termux() else 6
        time.sleep(wait_time)
        
        # Verifica se abriu corretamente
        pid = self.get_pid(package)
        if pid:
            print(f"[SUCCESS] {package} iniciado com PID: {pid}")
            return True
        else:
            print(f"[WARN] {package} pode não ter aberto corretamente")
            # Tenta abrir novamente
            time.sleep(2)
            self.run_adb_command(cmd)
            time.sleep(wait_time)
            return self.get_pid(package) is not None
    
    def restart_package(self, package: str):
        """
        Reinicia completamente um pacote INDIVIDUALMENTE.
        Otimizado para 10s cooldown.
        """
        current_time = time.time()
        
        # Verifica se está em cooldown
        if package in self.cooldown and current_time < self.cooldown[package]:
            remaining = self.cooldown[package] - current_time
            print(f"[COOLDOWN] {package} aguardando {remaining:.1f}s")
            return False
        
        print(f"\n{'='*60}")
        print(f"[RESTART INDIVIDUAL] {package}")
        print(f"{'='*60}")
        
        pid_before = self.get_pid(package)
        print(f"[INFO] PID antes: {pid_before if pid_before else 'Nenhum'}")
        
        # Reinicia o pacote
        success = self.open_vip(package)
        
        pid_after = self.get_pid(package)
        print(f"[INFO] PID depois: {pid_after if pid_after else 'Nenhum'}")
        
        if success:
            print(f"[SUCESSO] {package} reiniciado")
        else:
            print(f"[FALHA] {package} não foi reiniciado corretamente")
        
        print(f"{'='*60}\n")
        
        # Define cooldown de 10 segundos
        self.cooldown[package] = time.time() + self.config["cooldown_time"]
        
        # Reseta contador de CPU baixa para este pacote
        self.lowcpu_count[package] = 0
        
        return success
    
    def send_webhook(self, message: str, package: str = ""):
        """Envia notificação para webhook com informações do pacote"""
        if not self.config.get("webhook_url"):
            return
        
        try:
            import requests
            data = {
                "content": message,
                "username": "Roblox AutoRejoin",
                "embeds": [{
                    "title": f"Reinício Individual - {package}" if package else "Status Geral",
                    "description": message,
                    "color": 0x00ff00 if "SUCESSO" in message else 0xff0000,
                    "timestamp": datetime.utcnow().isoformat(),
                    "fields": [
                        {"name": "Pacote", "value": package, "inline": True},
                        {"name": "Hora", "value": datetime.now().strftime("%H:%M:%S"), "inline": True}
                    ]
                }]
            }
            requests.post(self.config["webhook_url"], json=data, timeout=5)
        except ImportError:
            print("[INFO] Instale requests para usar webhook: pip install requests")
        except Exception as e:
            print(f"[ERRO] Webhook falhou: {e}")
    
    def check_device_connected(self) -> bool:
        """Verifica se há dispositivo Android conectado"""
        output = self.run_adb_command("devices")
        if not output:
            return False
        
        devices = [line for line in output.split('\n') if '\tdevice' in line]
        return len(devices) > 0
    
    def monitor(self):
        """
        Loop principal de monitoramento ATUALIZADO.
        Verifica cada pacote INDIVIDUALMENTE e reinicia apenas os que precisam.
        """
        print("\n" + "="*70)
        print("[MONITOR] Iniciando AutoRejoin ATUALIZADO")
        print("="*70)
        print(f"[CONFIG] CPU limite: {self.config['low_cpu_threshold']}%")
        print(f"[CONFIG] Intervalo: {self.config['check_interval']}s")
        print(f"[CONFIG] Cooldown: {self.config['cooldown_time']}s")
        print(f"[CONFIG] Pacotes: {len(self.config['packages'])}")
        print("="*70)
        print("[CTRL+C] para parar o monitoramento")
        print("="*70 + "\n")
        
        # Inicializa todos os pacotes uma vez
        print("[INIT] Iniciando todos os pacotes...")
        for package in self.config["packages"]:
            self.restart_package(package)
            time.sleep(2)  # Pequena pausa entre inícios
        
        cycle_count = 0
        
        # Loop de monitoramento
        while self.running:
            cycle_count += 1
            current_time = time.time()
            
            print(f"\n[🔁 CICLO {cycle_count}] {datetime.now().strftime('%H:%M:%S')}")
            print("-" * 50)
            
            for package in self.config["packages"]:
                # Verifica status do pacote
                status = self.check_package_running(package)
                
                if not status["running"]:
                    # Pacote não está em execução
                    print(f"[❌ OFFLINE] {package}")
                    self.restart_package(package)
                    self.send_webhook(f"❌ {package} reiniciado (offline)", package)
                    
                elif status["needs_restart"]:
                    # Pacote com CPU baixa por tempo suficiente
                    print(f"[⚠️ CPU BAIXA] {package}: {status['cpu']:.1f}% "
                          f"(contagem: {status['low_cpu_count']}/{self.max_count})")
                    self.restart_package(package)
                    self.send_webhook(f"⚠️ {package} reiniciado (CPU baixa: {status['cpu']:.1f}%)", package)
                    
                elif status["cpu"] <= self.config["low_cpu_threshold"]:
                    # CPU baixa mas ainda não atingiu limite
                    count = self.lowcpu_count.get(package, 0)
                    print(f"[📉 MONITOR] {package}: {status['cpu']:.1f}% "
                          f"({count}/{self.max_count})")
                    
                else:
                    # CPU normal
                    print(f"[✅ OK] {package}: {status['cpu']:.1f}%")
            
            # Aguarda intervalo de 10 segundos
            print("-" * 50)
            print(f"[⏱️ AGUARDANDO] {self.config['check_interval']} segundos...")
            time.sleep(self.config["check_interval"])

def load_config() -> dict:
    """Carrega a configuração do arquivo JSON"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # Garante que os novos campos existam
                if "check_interval" not in config:
                    config["check_interval"] = 10
                if "low_cpu_threshold" not in config:
                    config["low_cpu_threshold"] = 8.0
                if "max_lowcpu_time" not in config:
                    config["max_lowcpu_time"] = 10
                if "cooldown_time" not in config:
                    config["cooldown_time"] = 10
                return config
        except Exception as e:
            print(f"[ERRO] Falha ao carregar configuração: {e}")
    
    # Retorna configuração padrão atualizada
    return DEFAULT_CONFIG.copy()

def save_config(config: dict):
    """Salva a configuração no arquivo JSON"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"[CONFIG] Configuração salva em {CONFIG_FILE}")
    except Exception as e:
        print(f"[ERRO] Falha ao salvar configuração: {e}")

def setup_wizard():
    """Assistente de configuração inicial ATUALIZADO"""
    print("\n" + "="*60)
    print("[SETUP WIZARD] Configuração ATUALIZADA")
    print("="*60)
    
    config = load_config()
    
    # Configurar link VIP
    print(f"\n[1] Link VIP atual: {config['web_link']}")
    change = input("Deseja alterar o link VIP? (s/n): ").lower()
    if change == 's':
        new_link = input("Novo link VIP: ").strip()
        if new_link:
            config['web_link'] = new_link
            print("[OK] Link VIP atualizado")
    
    # Configurar webhook
    print(f"\n[2] Webhook atual: {config['webhook_url'] or 'Não configurado'}")
    change = input("Deseja configurar webhook? (s/n): ").lower()
    if change == 's':
        webhook = input("URL do webhook (Discord/Telegram): ").strip()
        if webhook:
            config['webhook_url'] = webhook
            print("[OK] Webhook configurado")
    
    # Configurar intervalos ATUALIZADOS
    print("\n[3] Configurações de monitoramento (ATUALIZADO):")
    print("   - Verificação a cada 10 segundos")
    print("   - CPU limite: 8%")
    print("   - Cooldown: 10 segundos")
    
    confirm = input("\nManter configurações otimizadas? (s/n): ").lower()
    if confirm == 'n':
        try:
            interval = int(input(f"Intervalo de verificação (segundos) [10]: ") or 10)
            threshold = float(input(f"Limite de CPU baixa (%) [8.0]: ") or 8.0)
            max_time = int(input(f"Tempo máximo de CPU baixa (segundos) [10]: ") or 10)
            cooldown = int(input(f"Tempo de cooldown (segundos) [10]: ") or 10)
            
            config.update({
                'check_interval': interval,
                'low_cpu_threshold': threshold,
                'max_lowcpu_time': max_time,
                'cooldown_time': cooldown
            })
        except ValueError:
            print("[ERRO] Valores inválidos. Mantendo configurações atuais.")
    
    save_config(config)
    return config

def main_menu():
    """Menu principal interativo ATUALIZADO"""
    while True:
        print("\n" + "="*60)
        print("[ROBLOX AUTOREJOIN - VERSÃO ATUALIZADA]")
        print("="*60)
        print("[CONFIGURAÇÃO ATUAL]")
        config = load_config()
        print(f"  • CPU limite: {config['low_cpu_threshold']}%")
        print(f"  • Intervalo: {config['check_interval']}s")
        print(f"  • Cooldown: {config['cooldown_time']}s")
        print(f"  • Pacotes: {len(config.get('packages', []))}")
        print("="*60)
        print("1. 🚀 Iniciar monitoramento (8% CPU, 10s)")
        print("2. ⚙️ Configurar (VIP, Webhook, Intervalos)")
        print("3. 🔍 Detectar pacotes do Roblox automaticamente")
        print("4. 📦 Instalar dependências (Termux-ADB)")
        print("5. 📖 Guia de configuração Android")
        print("6. 🔧 Verificar conexão ADB")
        print("7. ❌ Sair")
        print("="*60)
        
        choice = input("\nEscolha uma opção (1-7): ").strip()
        
        if choice == '1':
            # Iniciar monitoramento
            config = load_config()
            
            # Verifica se há pacotes configurados
            if not config.get("packages"):
                print("[INFO] Nenhum pacote configurado. Detectando automaticamente...")
                monitor = RobloxMonitor(config)
                packages = monitor.detect_roblox_packages()
                if packages:
                    config["packages"] = packages
                    save_config(config)
                else:
                    print("[ERRO] Não há pacotes para monitorar.")
                    continue
            
            # Verifica conexão ADB
            monitor = RobloxMonitor(config)
            if not monitor.check_device_connected():
                print("[ERRO] Nenhum dispositivo conectado.")
                print("[INFO] Execute a opção 4 para instalar dependências.")
                print("[INFO] Execute a opção 5 para guia de configuração.")
                continue
            
            # Inicia monitoramento
            monitor.monitor()
            
        elif choice == '2':
            # Configuração
            config = setup_wizard()
            
        elif choice == '3':
            # Detectar pacotes
            config = load_config()
            monitor = RobloxMonitor(config)
            packages = monitor.detect_roblox_packages()
            if packages:
                config["packages"] = packages
                save_config(config)
                print(f"[SUCESSO] {len(packages)} pacotes salvos na configuração")
            else:
                print("[INFO] Nenhum pacote detectado.")
        
        elif choice == '4':
            # Instalar dependências
            if not TermuxSetup.is_termux():
                print("[INFO] Esta opção é apenas para Termux.")
                continue
            
            print("\n[SETUP] Instalando dependências para Termux...")
            
            # Atualizar pacotes
            print("[SETUP] Atualizando pacotes Termux...")
            subprocess.run(["pkg", "update", "-y"], capture_output=True)
            subprocess.run(["pkg", "upgrade", "-y"], capture_output=True)
            
            # Instalar termux-adb
            if TermuxSetup.install_termux_adb():
                print("[SUCESSO] Dependências instaladas com sucesso!")
            else:
                print("[ERRO] Falha na instalação. Consulte o guia (opção 5).")
            
            # Instalar pacotes Python
            TermuxSetup.install_python_packages()
        
        elif choice == '5':
            # Guia de configuração
            TermuxSetup.setup_android_debugging()
            
        elif choice == '6':
            # Verificar conexão ADB
            print("\n[TESTE] Verificando conexão ADB...")
            monitor = RobloxMonitor(load_config())
            if monitor.check_device_connected():
                print("[✅] Dispositivo conectado!")
                # Listar dispositivos
                devices = monitor.run_adb_command("devices")
                print(f"\nDispositivos:\n{devices}")
                
                # Testar comandos básicos
                print("\n[TESTE] Testando comandos ADB...")
                version = monitor.run_adb_command("version")
                print(f"ADB Version:\n{version[:100]}...")
            else:
                print("[❌] Nenhum dispositivo conectado.")
                print("\n[SOLUÇÃO]")
                print("1. Conecte o dispositivo via USB")
                print("2. Ative Depuração USB")
                print("3. Execute: adb devices")
                print("4. Autorize no dispositivo")
        
        elif choice == '7':
            print("\n[INFO] Saindo...")
            sys.exit(0)
        
        else:
            print("[ERRO] Opção inválida. Tente novamente.")

def main():
    """Função principal"""
    print("\n" + "="*70)
    print("ROBLOX AUTOREJOIN - VERSÃO ATUALIZADA (8% CPU, 10s)")
    print("="*70)
    print("Especialmente otimizado para:")
    print("  • UghPhone / VSPhone / Termux")
    print("  • Monitoramento individual por pacote")
    print("  • Configuração: 8% CPU limite, 10s intervalos")
    print("  • Reinício apenas do pacote problemático")
    print("="*70)
    
    # Verificar se está no Termux
    if TermuxSetup.is_termux():
        print("[INFO] ✅ Ambiente Termux detectado (UghPhone/VSPhone)")
    else:
        print("[INFO] Ambiente padrão detectado")
    
    # Executar menu principal
    main_menu()

if __name__ == "__main__":
    main()
