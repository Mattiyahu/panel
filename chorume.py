#!/usr/bin/env python3
"""
Roblox AutoRejoin para Termux (UghPhone/VSPhone)
Monitora e reinicia automaticamente múltiplas instâncias do Roblox.
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

# Configuração padrão
CONFIG_FILE = "autorejoin_config.json"
DEFAULT_CONFIG = {
    "web_link": "https://www.roblox.com/games/1537690962/Bee-Swarm-Simulator?privateServerLinkCode=05888256464342538313491710978310",
    "webhook_url": "",
    "check_interval": 15,
    "low_cpu_threshold": 0.3,
    "max_lowcpu_time": 90,
    "cooldown_time": 120,
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
        Baseado no projeto termux-adb do GitHub[reference:0].
        """
        print("\n[SETUP] Instalando termux-adb...")
        try:
            # Baixa e executa o script de instalação
            install_script = "https://raw.githubusercontent.com/nohajc/termux-adb/master/install.sh"
            curl_cmd = f"curl -s {install_script} | bash"
            result = subprocess.run(curl_cmd, shell=True, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                print("[SUCESSO] termux-adb instalado")
                return True
            else:
                print(f"[ERRO] Falha na instalação: {result.stderr}")
                return False
        except Exception as e:
            print(f"[ERRO] Exceção durante instalação: {e}")
            return False
    
    @staticmethod
    def install_python_packages():
        """Instala pacotes Python necessários"""
        required = ["requests"]
        try:
            import pkg_resources
            installed = {pkg.key for pkg in pkg_resources.working_set}
            
            for package in required:
                if package not in installed:
                    print(f"[SETUP] Instalando {package}...")
                    subprocess.run([sys.executable, "-m", "pip", "install", package], 
                                 capture_output=True, check=True)
                    print(f"[OK] {package} instalado")
        except Exception as e:
            print(f"[AVISO] Não foi possível instalar pacotes: {e}")
    
    @staticmethod
    def setup_android_debugging():
        """Guia para habilitar depuração USB no dispositivo"""
        print("\n" + "="*60)
        print("[CONFIGURAÇÃO ANDROID]")
        print("="*60)
        print("1. No dispositivo Android (UghPhone/VSPhone):")
        print("   - Acesse Configurações > Sobre o telefone")
        print("   - Toque 7 vezes em 'Número da versão' para habilitar Opções do desenvolvedor")
        print("   - Volte e acesse 'Opções do desenvolvedor'")
        print("   - Ative 'Depuração USB'")
        print("   - Ative 'Depuração via Wi-Fi' (se disponível)")
        print("2. No Termux, execute:")
        print("   termux-adb devices")
        print("   (Autorize a conexão quando solicitado no dispositivo)")
        print("="*60)

class RobloxMonitor:
    def __init__(self, config: dict):
        self.config = config
        self.proto_activity = "com.roblox.client.ActivityProtocolLaunch"
        self.lowcpu_count: Dict[str, int] = {}
        self.cooldown: Dict[str, float] = {}
        self.max_count = config["max_lowcpu_time"] // config["check_interval"]
        self.running = True
        
        # Usar termux-adb se estiver no Termux
        self.adb_cmd = "termux-adb" if TermuxSetup.is_termux() else "adb"
        
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
        Usa o comando 'pm list packages' para listar pacotes[reference:1].
        """
        print("[DETECT] Procurando pacotes do Roblox...")
        packages = []
        
        # Lista todos os pacotes
        output = self.run_adb_command("shell pm list packages")
        if not output:
            print("[ERRO] Não foi possível listar pacotes. Verifique conexão ADB.")
            return packages
        
        # Filtra pacotes do Roblox
        for line in output.split('\n'):
            if line.startswith("package:"):
                pkg = line.replace("package:", "").strip()
                if "com.roblox" in pkg.lower():
                    packages.append(pkg)
        
        if packages:
            print(f"[DETECT] Encontrados {len(packages)} pacotes: {', '.join(packages)}")
        else:
            print("[DETECT] Nenhum pacote do Roblox encontrado.")
            print("[DETECT] Instale o Roblox no dispositivo primeiro.")
        
        return packages
    
    def get_pid(self, package: str) -> Optional[str]:
        """Obtém o PID do pacote"""
        output = self.run_adb_command(f"shell pidof {package}")
        return output if output else None
    
    def get_cpu_by_pid(self, pid: str) -> float:
        """Obtém o uso de CPU pelo PID"""
        output = self.run_adb_command("shell top -n 1")
        if not output:
            return 0.0
        
        for line in output.split('\n'):
            if line.strip().startswith(pid):
                parts = line.split()
                if len(parts) >= 9:
                    cpu_str = parts[8].replace(',', '.').replace('%', '')
                    try:
                        return float(cpu_str)
                    except ValueError:
                        return 0.0
        return 0.0
    
    def open_vip(self, package: str):
        """Abre o servidor VIP no pacote"""
        print(f"[OPEN] Abrindo VIP em {package}")
        
        # Fecha qualquer instância anterior
        self.run_adb_command(f"shell am force-stop {package}")
        time.sleep(2)
        
        # Abre o link VIP
        cmd = (
            f"shell am start -n {package}/{self.proto_activity} "
            f"-a android.intent.action.VIEW -d \"{self.config['web_link']}\""
        )
        self.run_adb_command(cmd)
        time.sleep(6)
        
        # Verifica se abriu corretamente
        pid = self.get_pid(package)
        if pid:
            print(f"[SUCCESS] {package} iniciado com PID: {pid}")
        else:
            print(f"[WARN] {package} pode não ter aberto corretamente")
    
    def restart_package(self, package: str):
        """Reinicia completamente um pacote"""
        print(f"\n{'='*50}")
        print(f"[RESTART] {package}")
        
        pid_before = self.get_pid(package)
        print(f"[INFO] PID antes: {pid_before if pid_before else 'Nenhum'}")
        
        # Força parada
        self.run_adb_command(f"shell am force-stop {package}")
        time.sleep(2)
        
        # Abre VIP
        self.open_vip(package)
        
        pid_after = self.get_pid(package)
        print(f"[INFO] PID depois: {pid_after if pid_after else 'Nenhum'}")
        print(f"{'='*50}\n")
        
        # Define cooldown
        self.cooldown[package] = time.time() + self.config["cooldown_time"]
        self.lowcpu_count[package] = 0
    
    def send_webhook(self, message: str):
        """Envia notificação para webhook"""
        if not self.config.get("webhook_url"):
            return
        
        try:
            import requests
            data = {
                "content": message,
                "username": "Roblox AutoRejoin",
                "embeds": [{
                    "title": "Status do Monitoramento",
                    "description": message,
                    "timestamp": datetime.utcnow().isoformat(),
                    "color": 0x00ff00
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
        devices = [line for line in output.split('\n') if '\tdevice' in line]
        return len(devices) > 0
    
    def monitor(self):
        """Loop principal de monitoramento"""
        print("\n" + "="*60)
        print("[MONITOR] Iniciando AutoRejoin para Termux")
        print(f"[VIP LINK] {self.config['web_link']}")
        print(f"[PACKAGES] {len(self.config['packages'])} pacotes detectados")
        print("[CTRL+C] para parar o monitoramento")
        print("="*60 + "\n")
        
        # Inicializa todos os pacotes
        for package in self.config["packages"]:
            self.restart_package(package)
        
        # Loop de monitoramento
        while self.running:
            current_time = time.time()
            
            for package in self.config["packages"]:
                # Verifica cooldown
                if package in self.cooldown and current_time < self.cooldown[package]:
                    print(f"[COOLDOWN] {package} aguardando...")
                    continue
                
                # Obtém PID
                pid = self.get_pid(package)
                
                # Se não tem PID, reinicia
                if not pid:
                    print(f"[CLOSED] {package} não está em execução")
                    self.restart_package(package)
                    self.send_webhook(f"📱 {package} reiniciado (fechado)")
                    continue
                
                # Verifica uso de CPU
                cpu_usage = self.get_cpu_by_pid(pid)
                
                if cpu_usage <= self.config["low_cpu_threshold"]:
                    self.lowcpu_count[package] = self.lowcpu_count.get(package, 0) + 1
                    print(f"[LOW CPU] {package} CPU: {cpu_usage:.1f}% "
                          f"({self.lowcpu_count[package]}/{self.max_count})")
                    
                    # Se CPU baixa por muito tempo, reinicia
                    if self.lowcpu_count[package] >= self.max_count:
                        print(f"[STUCK] {package} parado por muito tempo")
                        self.restart_package(package)
                        self.send_webhook(f"⚠️ {package} reiniciado (travado)")
                else:
                    self.lowcpu_count[package] = 0
                    print(f"[OK] {package} CPU: {cpu_usage:.1f}%")
            
            # Aguarda intervalo
            time.sleep(self.config["check_interval"])

def load_config() -> dict:
    """Carrega a configuração do arquivo JSON"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERRO] Falha ao carregar configuração: {e}")
    
    # Retorna configuração padrão
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
    """Assistente de configuração inicial"""
    print("\n" + "="*60)
    print("[SETUP WIZARD] Configuração do Roblox AutoRejoin")
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
    
    # Configurar intervalos
    print("\n[3] Configurações de monitoramento:")
    try:
        interval = int(input(f"Intervalo de verificação (segundos) [{config['check_interval']}]: ") or config['check_interval'])
        threshold = float(input(f"Limite de CPU baixa (%) [{config['low_cpu_threshold']}]: ") or config['low_cpu_threshold'])
        max_time = int(input(f"Tempo máximo de CPU baixa (segundos) [{config['max_lowcpu_time']}]: ") or config['max_lowcpu_time'])
        cooldown = int(input(f"Tempo de cooldown (segundos) [{config['cooldown_time']}]: ") or config['cooldown_time'])
        
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
    """Menu principal interativo"""
    while True:
        print("\n" + "="*60)
        print("[ROBLOX AUTOREJOIN - TERMUX]")
        print("="*60)
        print("1. Iniciar monitoramento automático")
        print("2. Configurar (VIP, Webhook, Intervalos)")
        print("3. Detectar pacotes do Roblox automaticamente")
        print("4. Instalar dependências (Termux-ADB)")
        print("5. Guia de configuração Android")
        print("6. Sair")
        print("="*60)
        
        choice = input("\nEscolha uma opção (1-6): ").strip()
        
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
            print("\n[INFO] Saindo...")
            sys.exit(0)
        
        else:
            print("[ERRO] Opção inválida. Tente novamente.")

def main():
    """Função principal"""
    print("\n" + "="*60)
    print("ROBLOX AUTOREJOIN PARA TERMUX (UghPhone/VSPhone)")
    print("="*60)
    print("Versão: 2.0")
    print("Data: 2026-01-28")
    print("="*60)
    
    # Verificar se está no Termux
    if TermuxSetup.is_termux():
        print("[INFO] Ambiente Termux detectado (UghPhone/VSPhone)")
    else:
        print("[INFO] Ambiente padrão detectado")
    
    # Executar menu principal
    main_menu()

if __name__ == "__main__":
    main()
