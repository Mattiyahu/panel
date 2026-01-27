#!/usr/bin/env python3
"""
Roblox Monitor - Professional Edition
Sistema profissional de monitoramento para Roblox Mobile

Funcionalidades:
- Detecção precisa de estados: Em jogo, Home, Fechado
- Captura automática de screenshots em eventos importantes
- Notificações via Discord Webhook
- Logging estruturado e configuração persistente
- Monitoramento multi-instância com threads

Autor: Professional Development
Versão: 2.0.0
"""

import os
import sys
import json
import time
import logging
import subprocess
import threading
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import requests


# ═══════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES E CONSTANTES
# ═══════════════════════════════════════════════════════════════════

class RobloxState(Enum):
    """Estados possíveis do Roblox"""
    CLOSED = "Fechado"
    HOME = "Tela Inicial"
    LOADING = "Carregando"
    IN_GAME = "Em Jogo"
    KEY_SCREEN = "Tela de Key"
    UNKNOWN = "Desconhecido"


@dataclass
class MonitorConfig:
    """Configuração do monitor"""
    webhook_url: str = ""
    server_link: str = ""
    check_interval: int = 3
    screenshot_on_state_change: bool = True
    screenshot_on_key_screen: bool = True
    enable_notifications: bool = True
    
    # Thresholds para detecção de estado
    cpu_in_game_min: float = 15.0
    cpu_loading_min: float = 5.0
    cpu_idle_max: float = 3.0
    ram_in_game_min: int = 400  # MB
    ram_home_typical: int = 200  # MB


@dataclass
class ProcessMetrics:
    """Métricas de um processo"""
    pid: str
    cpu_percent: float
    ram_mb: int
    threads: int
    timestamp: datetime


class ConfigManager:
    """Gerenciador de configurações"""
    
    def __init__(self, config_file: str = "monitor_config.json"):
        self.config_file = Path(config_file)
        self.config = self.load()
    
    def load(self) -> MonitorConfig:
        """Carrega configuração do arquivo"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return MonitorConfig(**data)
            except Exception as e:
                logging.error(f"Erro ao carregar config: {e}")
        return MonitorConfig()
    
    def save(self, config: MonitorConfig) -> bool:
        """Salva configuração no arquivo"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(config), f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            logging.error(f"Erro ao salvar config: {e}")
            return False


# ═══════════════════════════════════════════════════════════════════
# UTILITÁRIOS ADB
# ═══════════════════════════════════════════════════════════════════

class ADBManager:
    """Gerenciador de comandos ADB"""
    
    @staticmethod
    def execute(command: str, timeout: int = 5) -> str:
        """Executa comando ADB e retorna output"""
        try:
            result = subprocess.run(
                f"adb shell {command}",
                shell=True,
                capture_output=True,
                timeout=timeout,
                text=True
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            logging.warning(f"Timeout ao executar: {command}")
            return ""
        except Exception as e:
            logging.error(f"Erro no ADB: {e}")
            return ""
    
    @staticmethod
    def check_connection() -> bool:
        """Verifica se há dispositivo conectado"""
        try:
            result = subprocess.run(
                "adb devices",
                shell=True,
                capture_output=True,
                timeout=3,
                text=True
            )
            lines = result.stdout.strip().split('\n')
            return len(lines) > 1 and 'device' in lines[1]
        except:
            return False
    
    @staticmethod
    def get_roblox_packages() -> List[str]:
        """Retorna lista de pacotes Roblox instalados"""
        output = ADBManager.execute("pm list packages")
        packages = []
        for line in output.split('\n'):
            if 'roblox' in line.lower():
                pkg = line.replace('package:', '').strip()
                if pkg:
                    packages.append(pkg)
        return packages
    
    @staticmethod
    def get_pid(package: str) -> str:
        """Retorna PID do pacote"""
        return ADBManager.execute(f"pidof {package}")
    
    @staticmethod
    def get_process_metrics(pid: str) -> Optional[ProcessMetrics]:
        """Obtém métricas detalhadas do processo"""
        if not pid:
            return None
        
        try:
            # CPU via top
            top_output = ADBManager.execute(f"top -n 1 -p {pid} | grep {pid}")
            cpu = 0.0
            threads = 0
            
            if top_output:
                parts = top_output.split()
                for part in parts:
                    if '%' in part:
                        try:
                            cpu = float(part.replace('%', '').replace(',', '.'))
                        except:
                            pass
            
            # RAM via dumpsys
            mem_output = ADBManager.execute(f"dumpsys meminfo {pid} | grep 'TOTAL'")
            ram = 0
            
            match = re.search(r'TOTAL\s+(\d+)', mem_output)
            if match:
                ram = int(match.group(1)) // 1024  # KB para MB
            
            # Threads via status
            status = ADBManager.execute(f"cat /proc/{pid}/status | grep Threads")
            match = re.search(r'Threads:\s+(\d+)', status)
            if match:
                threads = int(match.group(1))
            
            return ProcessMetrics(
                pid=pid,
                cpu_percent=cpu,
                ram_mb=ram,
                threads=threads,
                timestamp=datetime.now()
            )
        
        except Exception as e:
            logging.error(f"Erro ao obter métricas: {e}")
            return None
    
    @staticmethod
    def capture_screenshot(output_path: str = "/tmp/roblox_screenshot.png") -> bool:
        """Captura screenshot do dispositivo"""
        try:
            # Captura no dispositivo
            ADBManager.execute("screencap -p /sdcard/temp_screen.png")
            time.sleep(0.3)
            
            # Pull para o computador
            result = subprocess.run(
                f"adb pull /sdcard/temp_screen.png {output_path}",
                shell=True,
                capture_output=True,
                timeout=10
            )
            
            # Limpa arquivo temporário
            ADBManager.execute("rm /sdcard/temp_screen.png")
            
            return result.returncode == 0 and Path(output_path).exists()
        
        except Exception as e:
            logging.error(f"Erro ao capturar screenshot: {e}")
            return False
    
    @staticmethod
    def get_current_activity(package: str) -> str:
        """Retorna a activity atual do pacote"""
        output = ADBManager.execute(f"dumpsys window | grep mCurrentFocus")
        if package in output:
            match = re.search(r'([^/]+)/([\w\.]+)}', output)
            if match:
                return match.group(2)
        return ""


# ═══════════════════════════════════════════════════════════════════
# DETECTOR DE ESTADO
# ═══════════════════════════════════════════════════════════════════

class StateDetector:
    """Detector inteligente de estado do Roblox"""
    
    def __init__(self, config: MonitorConfig):
        self.config = config
    
    def detect_state(
        self, 
        metrics: Optional[ProcessMetrics],
        activity: str,
        package: str
    ) -> RobloxState:
        """
        Detecta o estado atual do Roblox baseado em múltiplos fatores
        
        Lógica de detecção:
        - CLOSED: Sem PID ou métricas
        - IN_GAME: CPU alta (>15%) + RAM alta (>400MB)
        - LOADING: CPU média (5-15%) + mudança de activity
        - KEY_SCREEN: CPU muito baixa (<3%) + RAM baixa + activity específica
        - HOME: CPU baixa (<5%) + RAM média (~200MB)
        """
        
        if not metrics:
            return RobloxState.CLOSED
        
        cpu = metrics.cpu_percent
        ram = metrics.ram_mb
        
        # Detecção via activity name (mais confiável)
        if activity:
            activity_lower = activity.lower()
            
            if 'game' in activity_lower or 'play' in activity_lower:
                return RobloxState.IN_GAME
            elif 'key' in activity_lower or 'auth' in activity_lower:
                return RobloxState.KEY_SCREEN
            elif 'home' in activity_lower or 'main' in activity_lower:
                return RobloxState.HOME
            elif 'loading' in activity_lower or 'splash' in activity_lower:
                return RobloxState.LOADING
        
        # Detecção via métricas (fallback)
        if cpu >= self.config.cpu_in_game_min and ram >= self.config.ram_in_game_min:
            return RobloxState.IN_GAME
        
        elif cpu >= self.config.cpu_loading_min:
            return RobloxState.LOADING
        
        elif cpu <= self.config.cpu_idle_max and ram < self.config.ram_home_typical:
            # CPU muito baixa pode ser tela de key ou home parada
            if ram < 150:  # RAM muito baixa sugere tela de key
                return RobloxState.KEY_SCREEN
            return RobloxState.HOME
        
        elif ram >= self.config.ram_home_typical and ram < self.config.ram_in_game_min:
            return RobloxState.HOME
        
        return RobloxState.UNKNOWN


# ═══════════════════════════════════════════════════════════════════
# NOTIFICADOR DISCORD
# ═══════════════════════════════════════════════════════════════════

class DiscordNotifier:
    """Gerenciador de notificações Discord"""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    def send_message(
        self,
        content: str,
        embed: Optional[Dict] = None,
        screenshot_path: Optional[str] = None
    ) -> bool:
        """Envia mensagem para Discord"""
        
        if not self.webhook_url:
            logging.warning("Webhook não configurado")
            return False
        
        try:
            payload = {"content": content}
            
            if embed:
                payload["embeds"] = [embed]
            
            files = None
            if screenshot_path and Path(screenshot_path).exists():
                with open(screenshot_path, 'rb') as f:
                    files = {"file": (Path(screenshot_path).name, f.read(), "image/png")}
            
            if files:
                response = requests.post(
                    self.webhook_url,
                    data={"payload_json": json.dumps(payload)},
                    files=files,
                    timeout=10
                )
            else:
                response = requests.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10
                )
            
            return response.status_code in [200, 204]
        
        except Exception as e:
            logging.error(f"Erro ao enviar webhook: {e}")
            return False
    
    def create_embed(
        self,
        title: str,
        description: str,
        color: int = 0x5865F2,
        fields: Optional[List[Dict]] = None
    ) -> Dict:
        """Cria embed formatado"""
        
        embed = {
            "title": title,
            "description": description,
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {"text": "Roblox Monitor Professional"}
        }
        
        if fields:
            embed["fields"] = fields
        
        return embed


# ═══════════════════════════════════════════════════════════════════
# INSTÂNCIA DE MONITORAMENTO
# ═══════════════════════════════════════════════════════════════════

class RobloxInstance:
    """Representa uma instância do Roblox sendo monitorada"""
    
    def __init__(self, package: str, config: MonitorConfig, notifier: DiscordNotifier):
        self.package = package
        self.name = self._extract_name(package)
        self.config = config
        self.notifier = notifier
        self.detector = StateDetector(config)
        
        # Estado
        self.current_state = RobloxState.UNKNOWN
        self.previous_state = RobloxState.UNKNOWN
        self.last_metrics: Optional[ProcessMetrics] = None
        self.state_change_count = 0
        self.last_notification_time = datetime.now()
        
        # Thread control
        self.running = False
        self.thread: Optional[threading.Thread] = None
    
    def _extract_name(self, package: str) -> str:
        """Extrai nome amigável do pacote"""
        parts = package.split('.')
        return parts[-1].upper() if parts else package.upper()
    
    def update(self) -> None:
        """Atualiza métricas e estado da instância"""
        try:
            # Obtém PID
            pid = ADBManager.get_pid(self.package)
            
            if not pid:
                self._handle_state_change(RobloxState.CLOSED)
                self.last_metrics = None
                return
            
            # Obtém métricas
            metrics = ADBManager.get_process_metrics(pid)
            self.last_metrics = metrics
            
            if not metrics:
                self._handle_state_change(RobloxState.UNKNOWN)
                return
            
            # Obtém activity atual
            activity = ADBManager.get_current_activity(self.package)
            
            # Detecta estado
            new_state = self.detector.detect_state(metrics, activity, self.package)
            
            # Verifica mudança de estado
            if new_state != self.current_state:
                self._handle_state_change(new_state)
        
        except Exception as e:
            logging.error(f"Erro ao atualizar {self.name}: {e}")
    
    def _handle_state_change(self, new_state: RobloxState) -> None:
        """Processa mudança de estado"""
        self.previous_state = self.current_state
        self.current_state = new_state
        self.state_change_count += 1
        
        # Log
        logging.info(f"{self.name}: {self.previous_state.value} → {new_state.value}")
        
        # Notificação
        if self.config.enable_notifications:
            self._send_state_notification(new_state)
    
    def _send_state_notification(self, state: RobloxState) -> None:
        """Envia notificação de mudança de estado"""
        
        # Evita spam (mínimo 10s entre notificações)
        time_since_last = (datetime.now() - self.last_notification_time).total_seconds()
        if time_since_last < 10:
            return
        
        # Captura screenshot se configurado
        screenshot_path = None
        
        should_screenshot = (
            (self.config.screenshot_on_state_change) or
            (state == RobloxState.KEY_SCREEN and self.config.screenshot_on_key_screen)
        )
        
        if should_screenshot:
            screenshot_path = f"/tmp/screenshot_{self.name}_{int(time.time())}.png"
            ADBManager.capture_screenshot(screenshot_path)
        
        # Prepara embed
        color_map = {
            RobloxState.IN_GAME: 0x57F287,      # Verde
            RobloxState.HOME: 0x5865F2,         # Azul
            RobloxState.LOADING: 0xFEE75C,      # Amarelo
            RobloxState.KEY_SCREEN: 0xED4245,   # Vermelho
            RobloxState.CLOSED: 0x99AAB5,       # Cinza
            RobloxState.UNKNOWN: 0x5865F2       # Azul
        }
        
        icon_map = {
            RobloxState.IN_GAME: "🎮",
            RobloxState.HOME: "🏠",
            RobloxState.LOADING: "⏳",
            RobloxState.KEY_SCREEN: "🔑",
            RobloxState.CLOSED: "❌",
            RobloxState.UNKNOWN: "❓"
        }
        
        fields = []
        
        if self.last_metrics:
            fields.extend([
                {
                    "name": "CPU",
                    "value": f"{self.last_metrics.cpu_percent:.1f}%",
                    "inline": True
                },
                {
                    "name": "RAM",
                    "value": f"{self.last_metrics.ram_mb} MB",
                    "inline": True
                },
                {
                    "name": "Threads",
                    "value": str(self.last_metrics.threads),
                    "inline": True
                }
            ])
        
        embed = self.notifier.create_embed(
            title=f"{icon_map[state]} {self.name}",
            description=f"**Estado:** {state.value}\n**Anterior:** {self.previous_state.value}",
            color=color_map[state],
            fields=fields
        )
        
        # Envia
        success = self.notifier.send_message(
            content=f"**Mudança de estado detectada**",
            embed=embed,
            screenshot_path=screenshot_path
        )
        
        if success:
            self.last_notification_time = datetime.now()
        
        # Limpa screenshot
        if screenshot_path and Path(screenshot_path).exists():
            try:
                os.remove(screenshot_path)
            except:
                pass
    
    def start_monitoring(self) -> None:
        """Inicia monitoramento em thread separada"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        logging.info(f"Monitoramento iniciado: {self.name}")
    
    def stop_monitoring(self) -> None:
        """Para o monitoramento"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        logging.info(f"Monitoramento parado: {self.name}")
    
    def _monitor_loop(self) -> None:
        """Loop principal de monitoramento"""
        while self.running:
            try:
                self.update()
                time.sleep(self.config.check_interval)
            except Exception as e:
                logging.error(f"Erro no loop de {self.name}: {e}")
                time.sleep(5)


# ═══════════════════════════════════════════════════════════════════
# MONITOR PRINCIPAL
# ═══════════════════════════════════════════════════════════════════

class RobloxMonitor:
    """Monitor principal que gerencia todas as instâncias"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.config = self.config_manager.config
        self.notifier = DiscordNotifier(self.config.webhook_url)
        self.instances: Dict[str, RobloxInstance] = {}
        self.running = False
        
        # Setup logging
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """Configura sistema de logging"""
        log_format = '%(asctime)s | %(levelname)-8s | %(message)s'
        date_format = '%Y-%m-%d %H:%M:%S'
        
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            datefmt=date_format,
            handlers=[
                logging.FileHandler('roblox_monitor.log', encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
    
    def start(self) -> bool:
        """Inicia o monitor"""
        
        # Verifica conexão ADB
        if not ADBManager.check_connection():
            logging.error("❌ Nenhum dispositivo ADB conectado!")
            return False
        
        # Busca pacotes Roblox
        packages = ADBManager.get_roblox_packages()
        
        if not packages:
            logging.error("❌ Nenhum pacote Roblox encontrado!")
            return False
        
        logging.info(f"✅ Encontrados {len(packages)} pacote(s) Roblox")
        
        # Cria instâncias
        for package in packages:
            instance = RobloxInstance(package, self.config, self.notifier)
            self.instances[package] = instance
            instance.start_monitoring()
        
        self.running = True
        
        # Notificação de início
        if self.config.enable_notifications:
            embed = self.notifier.create_embed(
                title="🚀 Monitor Iniciado",
                description=f"Monitorando {len(packages)} instância(s) do Roblox",
                color=0x57F287
            )
            self.notifier.send_message("", embed=embed)
        
        logging.info("✅ Monitor iniciado com sucesso!")
        return True
    
    def stop(self) -> None:
        """Para o monitor"""
        logging.info("Parando monitor...")
        
        for instance in self.instances.values():
            instance.stop_monitoring()
        
        self.running = False
        
        # Notificação de parada
        if self.config.enable_notifications:
            embed = self.notifier.create_embed(
                title="⏹️ Monitor Parado",
                description="Sistema de monitoramento encerrado",
                color=0x99AAB5
            )
            self.notifier.send_message("", embed=embed)
        
        logging.info("✅ Monitor parado")
    
    def get_status(self) -> Dict:
        """Retorna status atual de todas as instâncias"""
        status = {}
        
        for package, instance in self.instances.items():
            status[instance.name] = {
                "state": instance.current_state.value,
                "cpu": instance.last_metrics.cpu_percent if instance.last_metrics else 0,
                "ram": instance.last_metrics.ram_mb if instance.last_metrics else 0,
                "state_changes": instance.state_change_count
            }
        
        return status
    
    def display_status(self) -> None:
        """Exibe status formatado no console"""
        os.system('clear' if os.name == 'posix' else 'cls')
        
        print("╔════════════════════════════════════════════════════════════╗")
        print("║         ROBLOX MONITOR - PROFESSIONAL EDITION             ║")
        print("╚════════════════════════════════════════════════════════════╝")
        print()
        
        if not self.instances:
            print("  ⚠️  Nenhuma instância sendo monitorada")
            return
        
        print("  INSTÂNCIAS ATIVAS:")
        print("  " + "─" * 56)
        
        for instance in self.instances.values():
            state_icon = {
                RobloxState.IN_GAME: "🎮",
                RobloxState.HOME: "🏠",
                RobloxState.LOADING: "⏳",
                RobloxState.KEY_SCREEN: "🔑",
                RobloxState.CLOSED: "❌",
                RobloxState.UNKNOWN: "❓"
            }.get(instance.current_state, "❓")
            
            metrics_str = "N/A"
            if instance.last_metrics:
                metrics_str = f"CPU: {instance.last_metrics.cpu_percent:5.1f}% | RAM: {instance.last_metrics.ram_mb:4d} MB"
            
            print(f"  {state_icon} {instance.name:12} | {instance.current_state.value:15} | {metrics_str}")
        
        print("  " + "─" * 56)
        print()
        print("  Pressione Ctrl+C para parar o monitor")


# ═══════════════════════════════════════════════════════════════════
# INTERFACE DE LINHA DE COMANDO
# ═══════════════════════════════════════════════════════════════════

class CLI:
    """Interface de linha de comando"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.monitor = RobloxMonitor()
    
    def clear_screen(self):
        """Limpa a tela"""
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def print_header(self):
        """Imprime cabeçalho"""
        self.clear_screen()
        print("╔════════════════════════════════════════════════════════════╗")
        print("║         ROBLOX MONITOR - PROFESSIONAL EDITION             ║")
        print("║                    Versão 2.0.0                           ║")
        print("╚════════════════════════════════════════════════════════════╝")
        print()
    
    def main_menu(self):
        """Menu principal"""
        while True:
            self.print_header()
            
            # Status da configuração
            config = self.config_manager.config
            webhook_status = "✅" if config.webhook_url else "❌"
            server_status = "✅" if config.server_link else "❌"
            
            print(f"  Webhook: {webhook_status}  |  Server Link: {server_status}")
            print()
            print("  ┌────────────────────────────────────────────────────┐")
            print("  │  [1] 🚀 Iniciar Monitor                            │")
            print("  │  [2] ⚙️  Configurações                              │")
            print("  │  [3] 🧪 Testar Captura de Screenshot               │")
            print("  │  [4] 📊 Ver Logs                                    │")
            print("  │  [0] ❌ Sair                                        │")
            print("  └────────────────────────────────────────────────────┘")
            print()
            
            choice = input("  Selecione uma opção: ").strip()
            
            if choice == "1":
                self.start_monitor()
            elif choice == "2":
                self.configure()
            elif choice == "3":
                self.test_screenshot()
            elif choice == "4":
                self.view_logs()
            elif choice == "0":
                print("\n  👋 Até logo!\n")
                break
            else:
                print("\n  ⚠️  Opção inválida!")
                time.sleep(1)
    
    def start_monitor(self):
        """Inicia o monitor"""
        self.print_header()
        print("  🚀 Iniciando monitor...\n")
        
        if not self.monitor.config.webhook_url:
            print("  ⚠️  Configure o webhook primeiro!")
            input("\n  Pressione Enter para continuar...")
            return
        
        if self.monitor.start():
            try:
                while self.monitor.running:
                    self.monitor.display_status()
                    time.sleep(2)
            except KeyboardInterrupt:
                print("\n\n  ⏹️  Parando monitor...")
                self.monitor.stop()
                time.sleep(1)
        else:
            print("\n  ❌ Falha ao iniciar monitor!")
            input("\n  Pressione Enter para continuar...")
    
    def configure(self):
        """Menu de configurações"""
        while True:
            self.print_header()
            config = self.config_manager.config
            
            print("  ⚙️  CONFIGURAÇÕES")
            print("  " + "─" * 56)
            print(f"  Webhook URL: {config.webhook_url[:50] if config.webhook_url else 'Não configurado'}")
            print(f"  Server Link: {config.server_link[:50] if config.server_link else 'Não configurado'}")
            print(f"  Intervalo de verificação: {config.check_interval}s")
            print(f"  Screenshot em mudança de estado: {'Sim' if config.screenshot_on_state_change else 'Não'}")
            print(f"  Screenshot em tela de key: {'Sim' if config.screenshot_on_key_screen else 'Não'}")
            print("  " + "─" * 56)
            print()
            print("  [1] Configurar Webhook URL")
            print("  [2] Configurar Server Link")
            print("  [3] Ajustar Intervalo de Verificação")
            print("  [4] Toggle Screenshots")
            print("  [0] Voltar")
            print()
            
            choice = input("  Selecione: ").strip()
            
            if choice == "1":
                webhook = input("\n  Cole o Webhook URL: ").strip()
                if webhook:
                    config.webhook_url = webhook
                    self.config_manager.save(config)
                    self.monitor.notifier.webhook_url = webhook
                    print("  ✅ Webhook salvo!")
                    time.sleep(1)
            
            elif choice == "2":
                server = input("\n  Cole o Server Link: ").strip()
                if server:
                    config.server_link = server
                    self.config_manager.save(config)
                    print("  ✅ Server link salvo!")
                    time.sleep(1)
            
            elif choice == "3":
                try:
                    interval = int(input("\n  Intervalo em segundos (recomendado: 3-5): ").strip())
                    if 1 <= interval <= 60:
                        config.check_interval = interval
                        self.config_manager.save(config)
                        print("  ✅ Intervalo atualizado!")
                    else:
                        print("  ⚠️  Valor deve estar entre 1 e 60")
                    time.sleep(1)
                except:
                    print("  ⚠️  Valor inválido!")
                    time.sleep(1)
            
            elif choice == "4":
                print("\n  [1] Toggle Screenshot em mudança de estado")
                print("  [2] Toggle Screenshot em tela de key")
                sub = input("\n  Selecione: ").strip()
                
                if sub == "1":
                    config.screenshot_on_state_change = not config.screenshot_on_state_change
                    self.config_manager.save(config)
                    print(f"  ✅ Screenshot em mudança: {'Ativado' if config.screenshot_on_state_change else 'Desativado'}")
                elif sub == "2":
                    config.screenshot_on_key_screen = not config.screenshot_on_key_screen
                    self.config_manager.save(config)
                    print(f"  ✅ Screenshot em tela de key: {'Ativado' if config.screenshot_on_key_screen else 'Desativado'}")
                time.sleep(1)
            
            elif choice == "0":
                break
    
    def test_screenshot(self):
        """Testa captura de screenshot"""
        self.print_header()
        print("  🧪 TESTE DE SCREENSHOT\n")
        
        if not self.monitor.config.webhook_url:
            print("  ⚠️  Configure o webhook primeiro!")
            input("\n  Pressione Enter para continuar...")
            return
        
        print("  📸 Capturando screenshot...")
        screenshot_path = "/tmp/test_screenshot.png"
        
        if ADBManager.capture_screenshot(screenshot_path):
            print("  ✅ Screenshot capturado!")
            print("  📤 Enviando para webhook...")
            
            notifier = DiscordNotifier(self.monitor.config.webhook_url)
            embed = notifier.create_embed(
                title="🧪 Teste de Screenshot",
                description="Se você está vendo isso, o sistema está funcionando corretamente!",
                color=0x5865F2
            )
            
            if notifier.send_message("**Teste de Screenshot**", embed=embed, screenshot_path=screenshot_path):
                print("  ✅ Screenshot enviado com sucesso!")
            else:
                print("  ❌ Falha ao enviar screenshot")
            
            # Limpa arquivo
            try:
                os.remove(screenshot_path)
            except:
                pass
        else:
            print("  ❌ Falha ao capturar screenshot")
        
        input("\n  Pressione Enter para continuar...")
    
    def view_logs(self):
        """Visualiza logs"""
        self.print_header()
        print("  📊 LOGS RECENTES\n")
        
        log_file = Path("roblox_monitor.log")
        
        if not log_file.exists():
            print("  ℹ️  Nenhum log disponível ainda")
        else:
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    # Mostra últimas 20 linhas
                    for line in lines[-20:]:
                        print(f"  {line.rstrip()}")
            except Exception as e:
                print(f"  ❌ Erro ao ler logs: {e}")
        
        input("\n  Pressione Enter para continuar...")


# ═══════════════════════════════════════════════════════════════════
# PONTO DE ENTRADA
# ═══════════════════════════════════════════════════════════════════

def main():
    """Função principal"""
    try:
        cli = CLI()
        cli.main_menu()
    except KeyboardInterrupt:
        print("\n\n  👋 Programa encerrado pelo usuário\n")
    except Exception as e:
        logging.error(f"Erro fatal: {e}", exc_info=True)
        print(f"\n  ❌ Erro fatal: {e}\n")


if __name__ == "__main__":
    main()
