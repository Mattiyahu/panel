#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import time
import random
from datetime import datetime
from typing import Dict, List, Optional
import os
import sys

# Cores ANSI para terminal
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    BG_BLACK = '\033[40m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'
    BG_MAGENTA = '\033[45m'
    BG_CYAN = '\033[46m'
    BG_WHITE = '\033[47m'

class RobloxAutoRejoin:
    def __init__(self):
        self.web_link = "https://www.roblox.com/games/1537690962/Bee-Swarm-Simulator?privateServerLinkCode=05888256464342538313491710978310"
        self.packages = [
            "com.roblox.clienb",
            "com.roblox.cliend",
            "com.roblox.cliene"
        ]
        self.proto_activity = "com.roblox.client.ActivityProtocolLaunch"
        self.check_interval = 15
        self.low_cpu_threshold = 0.3
        self.max_lowcpu_time = 90
        self.cooldown_time = 120
        self.max_count = self.max_lowcpu_time // self.check_interval
        
        self.lowcpu_count: Dict[str, int] = {pkg: 0 for pkg in self.packages}
        self.cooldown: Dict[str, int] = {pkg: 0 for pkg in self.packages}
        self.logs: List[str] = []
        
        # Mensagens variadas para logs
        self.messages = {
            'start': ['🚀 Sistema iniciado com sucesso', '🎮 AutoRejoin ativado', '⚡ Monitoramento iniciado'],
            'restart': ['🔄 Reiniciando instância...', '🔧 Forçando fechamento do app', '♻️ Executando restart'],
            'open': ['🎮 Abrindo Roblox...', '🌐 Conectando ao servidor VIP', '📱 Carregando jogo'],
            'online': ['✅ Conta online e estável', '🎯 Jogando normalmente', '🟢 Conexão estabelecida'],
            'low_cpu': ['⚠️ CPU baixo detectado', '⏰ Possível travamento', '📊 Monitorando atividade'],
            'stuck': ['🔴 Conta travada detectada', '❌ Inatividade prolongada', '🚨 Executando restart automático'],
            'down': ['💀 Aplicativo fechado', '🔌 Processo não encontrado', '🔄 Reconectando automaticamente'],
            'cooldown': ['⏳ Aguardando cooldown...', '🕐 Evitando restart em loop', '⏱️ Período de espera ativo']
        }
    
    def clear_screen(self):
        """Limpa a tela do terminal"""
        os.system('clear' if os.name != 'nt' else 'cls')
    
    def print_header(self):
        """Imprime o cabeçalho do programa"""
        print(f"{Colors.CYAN}{Colors.BOLD}")
        print("╔══════════════════════════════════════════════════════════════╗")
        print("║          🎮 ROBLOX AUTOREJOIN MONITOR 🎮                    ║")
        print("║              Monitor de Contas em Tempo Real                 ║")
        print("╚══════════════════════════════════════════════════════════════╝")
        print(f"{Colors.RESET}\n")
    
    def print_config(self):
        """Mostra as configurações atuais"""
        print(f"{Colors.YELLOW}{Colors.BOLD}⚙️  CONFIGURAÇÕES:{Colors.RESET}")
        print(f"{Colors.DIM}├─ Link VIP: {Colors.GREEN}{self.web_link[:50]}...{Colors.RESET}")
        print(f"{Colors.DIM}├─ Intervalo de Checagem: {Colors.CYAN}{self.check_interval}s{Colors.RESET}")
        print(f"{Colors.DIM}├─ CPU Threshold: {Colors.CYAN}{self.low_cpu_threshold}%{Colors.RESET}")
        print(f"{Colors.DIM}├─ Tempo Cooldown: {Colors.CYAN}{self.cooldown_time}s{Colors.RESET}")
        print(f"{Colors.DIM}└─ Max Low CPU Time: {Colors.CYAN}{self.max_lowcpu_time}s{Colors.RESET}\n")
    
    def get_random_message(self, msg_type: str) -> str:
        """Retorna uma mensagem aleatória do tipo especificado"""
        return random.choice(self.messages.get(msg_type, ['Ação executada']))
    
    def add_log(self, msg_type: str, package: Optional[str] = None):
        """Adiciona um log com timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        message = self.get_random_message(msg_type)
        pkg_info = f" ({Colors.BLUE}{package}{Colors.RESET})" if package else ""
        log_entry = f"{Colors.DIM}[{timestamp}]{Colors.RESET} {message}{pkg_info}"
        self.logs.append(log_entry)
        if len(self.logs) > 20:  # Mantém apenas os últimos 20 logs
            self.logs.pop(0)
    
    def run_adb_command(self, command: str) -> str:
        """Executa um comando ADB e retorna a saída"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            return result.stdout.strip().replace('\r', '')
        except Exception as e:
            return ""
    
    def get_pid(self, package: str) -> Optional[str]:
        """Obtém o PID de um pacote"""
        pid = self.run_adb_command(f"adb shell pidof {package}")
        return pid if pid else None
    
    def get_cpu_by_pid(self, pid: str) -> Optional[float]:
        """Obtém o uso de CPU por PID"""
        top_output = self.run_adb_command("adb shell top -n 1")
        for line in top_output.split('\n'):
            parts = line.split()
            if parts and parts[0] == pid:
                try:
                    cpu = parts[8].replace('%', '').replace(',', '.')
                    return float(cpu)
                except (IndexError, ValueError):
                    return None
        return None
    
    def open_vip(self, package: str):
        """Abre o servidor VIP no Roblox"""
        cmd = f'adb shell am start -n "{package}/{self.proto_activity}" -a android.intent.action.VIEW -d "{self.web_link}"'
        self.run_adb_command(cmd)
        time.sleep(6)
    
    def restart_package(self, package: str):
        """Reinicia um pacote"""
        now = int(time.time())
        
        self.add_log('restart', package)
        
        # Força o fechamento
        pid_before = self.get_pid(package)
        self.run_adb_command(f"adb shell am force-stop {package}")
        time.sleep(2)
        
        # Abre novamente
        self.add_log('open', package)
        self.open_vip(package)
        
        # Define o cooldown
        self.cooldown[package] = now + self.cooldown_time
    
    def get_status_color(self, cpu: Optional[float], pid: Optional[str]) -> str:
        """Retorna a cor baseada no status"""
        if not pid:
            return Colors.RED
        elif cpu is not None and cpu < self.low_cpu_threshold:
            return Colors.YELLOW
        else:
            return Colors.GREEN
    
    def get_status_text(self, cpu: Optional[float], pid: Optional[str]) -> str:
        """Retorna o texto de status"""
        if not pid:
            return "OFFLINE"
        elif cpu is not None and cpu < self.low_cpu_threshold:
            return "CPU BAIXO"
        else:
            return "ONLINE"
    
    def print_status_panel(self):
        """Imprime o painel de status das contas"""
        print(f"{Colors.MAGENTA}{Colors.BOLD}📊 STATUS DAS CONTAS:{Colors.RESET}\n")
        
        for idx, pkg in enumerate(self.packages, 1):
            pid = self.get_pid(pkg)
            cpu = self.get_cpu_by_pid(pid) if pid else None
            
            status_color = self.get_status_color(cpu, pid)
            status_text = self.get_status_text(cpu, pid)
            
            print(f"{Colors.CYAN}{Colors.BOLD}┌─ Conta #{idx} ─────────────────────────────────────┐{Colors.RESET}")
            print(f"{Colors.CYAN}│{Colors.RESET} Package: {Colors.DIM}{pkg}{Colors.RESET}")
            print(f"{Colors.CYAN}│{Colors.RESET} Status:  {status_color}{Colors.BOLD}{status_text}{Colors.RESET}")
            print(f"{Colors.CYAN}│{Colors.RESET} PID:     {Colors.WHITE}{pid if pid else '---'}{Colors.RESET}")
            print(f"{Colors.CYAN}│{Colors.RESET} CPU:     {Colors.WHITE}{cpu:.1f}%{Colors.RESET}" if cpu else f"{Colors.CYAN}│{Colors.RESET} CPU:     {Colors.WHITE}0.0%{Colors.RESET}")
            
            if self.lowcpu_count[pkg] > 0:
                print(f"{Colors.CYAN}│{Colors.RESET} Alert:   {Colors.YELLOW}{self.lowcpu_count[pkg]}/{self.max_count}{Colors.RESET}")
            
            # Barra de CPU
            cpu_val = cpu if cpu else 0
            bar_length = 30
            filled = int((cpu_val / 100) * bar_length)
            bar = "█" * filled + "░" * (bar_length - filled)
            bar_color = Colors.GREEN if cpu_val > 50 else Colors.YELLOW if cpu_val > 20 else Colors.RED
            print(f"{Colors.CYAN}│{Colors.RESET} {bar_color}{bar}{Colors.RESET}")
            print(f"{Colors.CYAN}└────────────────────────────────────────────────────┘{Colors.RESET}\n")
    
    def print_logs(self):
        """Imprime os logs recentes"""
        print(f"{Colors.GREEN}{Colors.BOLD}📝 LOGS DO SISTEMA (últimos 10):{Colors.RESET}\n")
        for log in self.logs[-10:]:
            print(log)
        print()
    
    def monitor_loop(self):
        """Loop principal de monitoramento"""
        # Inicializa todas as contas
        self.add_log('start')
        for pkg in self.packages:
            self.restart_package(pkg)
        
        while True:
            self.clear_screen()
            self.print_header()
            self.print_config()
            self.print_status_panel()
            self.print_logs()
            
            now = int(time.time())
            
            for pkg in self.packages:
                # Verifica cooldown
                if pkg in self.cooldown and now < self.cooldown[pkg]:
                    self.add_log('cooldown', pkg)
                    continue
                
                pid = self.get_pid(pkg)
                
                # Verifica se o app caiu
                if not pid:
                    self.add_log('down', pkg)
                    self.lowcpu_count[pkg] = 0
                    self.restart_package(pkg)
                    continue
                
                # Verifica CPU
                cpu = self.get_cpu_by_pid(pid)
                if cpu is None:
                    continue
                
                if cpu <= self.low_cpu_threshold:
                    self.lowcpu_count[pkg] += 1
                    self.add_log('low_cpu', pkg)
                    
                    if self.lowcpu_count[pkg] >= self.max_count:
                        self.add_log('stuck', pkg)
                        self.lowcpu_count[pkg] = 0
                        self.restart_package(pkg)
                else:
                    self.lowcpu_count[pkg] = 0
                    if random.random() > 0.8:  # 20% de chance de logar quando OK
                        self.add_log('online', pkg)
            
            print(f"{Colors.DIM}Próxima checagem em {self.check_interval}s... (Ctrl+C para sair){Colors.RESET}")
            time.sleep(self.check_interval)
    
    def configure(self):
        """Menu de configuração interativo"""
        self.clear_screen()
        self.print_header()
        print(f"{Colors.YELLOW}{Colors.BOLD}⚙️  MENU DE CONFIGURAÇÃO{Colors.RESET}\n")
        
        print(f"{Colors.CYAN}1.{Colors.RESET} Alterar Link VIP")
        print(f"{Colors.CYAN}2.{Colors.RESET} Alterar Intervalo de Checagem")
        print(f"{Colors.CYAN}3.{Colors.RESET} Alterar CPU Threshold")
        print(f"{Colors.CYAN}4.{Colors.RESET} Alterar Tempo de Cooldown")
        print(f"{Colors.CYAN}5.{Colors.RESET} Voltar e Iniciar\n")
        
        choice = input(f"{Colors.GREEN}Escolha uma opção: {Colors.RESET}")
        
        if choice == '1':
            new_link = input(f"{Colors.GREEN}Digite o novo link VIP: {Colors.RESET}")
            if new_link.strip():
                self.web_link = new_link.strip()
                print(f"{Colors.GREEN}✅ Link atualizado!{Colors.RESET}")
        elif choice == '2':
            try:
                new_interval = int(input(f"{Colors.GREEN}Digite o intervalo (segundos): {Colors.RESET}"))
                self.check_interval = new_interval
                self.max_count = self.max_lowcpu_time // self.check_interval
                print(f"{Colors.GREEN}✅ Intervalo atualizado!{Colors.RESET}")
            except ValueError:
                print(f"{Colors.RED}❌ Valor inválido!{Colors.RESET}")
        elif choice == '3':
            try:
                new_threshold = float(input(f"{Colors.GREEN}Digite o threshold (%): {Colors.RESET}"))
                self.low_cpu_threshold = new_threshold
                print(f"{Colors.GREEN}✅ Threshold atualizado!{Colors.RESET}")
            except ValueError:
                print(f"{Colors.RED}❌ Valor inválido!{Colors.RESET}")
        elif choice == '4':
            try:
                new_cooldown = int(input(f"{Colors.GREEN}Digite o cooldown (segundos): {Colors.RESET}"))
                self.cooldown_time = new_cooldown
                print(f"{Colors.GREEN}✅ Cooldown atualizado!{Colors.RESET}")
            except ValueError:
                print(f"{Colors.RED}❌ Valor inválido!{Colors.RESET}")
        elif choice == '5':
            return
        
        time.sleep(2)
        self.configure()
    
    def main_menu(self):
        """Menu principal"""
        self.clear_screen()
        self.print_header()
        print(f"{Colors.CYAN}{Colors.BOLD}MENU PRINCIPAL{Colors.RESET}\n")
        print(f"{Colors.GREEN}1.{Colors.RESET} Iniciar Monitoramento")
        print(f"{Colors.YELLOW}2.{Colors.RESET} Configurações")
        print(f"{Colors.RED}3.{Colors.RESET} Sair\n")
        
        choice = input(f"{Colors.GREEN}Escolha uma opção: {Colors.RESET}")
        
        if choice == '1':
            try:
                self.monitor_loop()
            except KeyboardInterrupt:
                print(f"\n{Colors.YELLOW}⏹️  Monitoramento interrompido!{Colors.RESET}")
                time.sleep(2)
                self.main_menu()
        elif choice == '2':
            self.configure()
            self.main_menu()
        elif choice == '3':
            print(f"\n{Colors.CYAN}👋 Até logo!{Colors.RESET}\n")
            sys.exit(0)
        else:
            print(f"{Colors.RED}❌ Opção inválida!{Colors.RESET}")
            time.sleep(1)
            self.main_menu()

def main():
    try:
        monitor = RobloxAutoRejoin()
        monitor.main_menu()
    except KeyboardInterrupt:
        print(f"\n{Colors.CYAN}👋 Programa encerrado!{Colors.RESET}\n")
        sys.exit(0)

if __name__ == "__main__":
    main()
