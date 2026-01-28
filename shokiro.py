#!/data/data/com.termux/files/usr/bin/python
# -*- coding: utf-8 -*-
"""
Shouko Bot - Versão Termux Corrigida
Multi-Account Roblox Manager
"""

import os
import sys
import subprocess
import time
import json

def check_and_install_dependencies():
    """Verifica e instala dependências se necessário"""
    required_modules = {
        'prettytable': 'prettytable',
        'requests': 'requests',
        'psutil': 'psutil',
        'rich': 'rich'
    }
    
    missing_modules = []
    
    for module_name, package_name in required_modules.items():
        try:
            __import__(module_name)
        except ImportError:
            missing_modules.append(package_name)
    
    if missing_modules:
        print("\033[1;33m[SETUP] Instalando dependências faltantes...\033[0m")
        for package in missing_modules:
            print(f"\033[96m → Instalando {package}...\033[0m")
            try:
                subprocess.check_call([
                    sys.executable, '-m', 'pip', 'install', 
                    package, '--upgrade', '--quiet'
                ])
                print(f"\033[1;32m ✓ {package} instalado!\033[0m")
            except Exception as e:
                print(f"\033[1;31m ✗ Erro ao instalar {package}: {e}\033[0m")
        print("\033[1;32m[SETUP] Instalação concluída!\033[0m\n")
        time.sleep(1)

# Executar verificação de dependências
check_and_install_dependencies()

# Importações após instalação
try:
    from prettytable import PrettyTable
    import threading
    import requests
    import sqlite3
    import shutil
    import traceback
    import random
    import psutil
    import gc
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.align import Align
    from rich.box import ROUNDED
    from rich.console import Console
    from datetime import datetime, timezone
    from threading import Lock, Event
except ImportError as e:
    print(f"\033[1;31m[ERRO] Falha ao importar módulos: {e}\033[0m")
    print("\033[1;33m[INFO] Tente executar: pip install prettytable requests psutil rich\033[0m")
    sys.exit(1)

# ==================== VARIÁVEIS GLOBAIS ====================
status_lock = Lock()
rejoin_lock = Lock()
bot_instance = None
bot_thread = None
socket_server = None
stop_webhook_thread = False
webhook_thread = None
webhook_url = None
device_name = None
webhook_interval = None
reset_tab_interval = None
close_and_rejoin_delay = None

try:
    system_boot_time = psutil.boot_time()
except Exception:
    system_boot_time = time.time()

auto_android_id_enabled = False
auto_android_id_thread = None
auto_android_id_value = None

package_statuses = {}
uid_data = {}
user_data = {}
is_runner_ez = False
check_exec_enable = "1"
package_prefix = "com.roblox"

# Executors paths
executors = {
    "Delta": "/storage/emulated/0/Delta/",
    "Codex": "/storage/emulated/0/Codex/",
    "Arceus X": "/storage/emulated/0/Arceus X/",
    "FluxusZ": "/storage/emulated/0/FluxusZ/",
    "Neutron": "/storage/emulated/0/Neutron/",
}

workspace_paths = []
for base_path in executors.values():
    workspace_paths.append(f"{base_path}Workspace")
    workspace_paths.append(f"{base_path}workspace")

# Criar diretório de configuração
if not os.path.exists("Shouko.dev"):
    os.makedirs("Shouko.dev", exist_ok=True)

SERVER_LINKS_FILE = "Shouko.dev/server-links.txt"
ACCOUNTS_FILE = "Shouko.dev/accounts.txt"
CONFIG_FILE = "Shouko.dev/config.json"

version = "1.0.4 - Termux Fixed | By Neyoshi & Nexus/Gemini"

# ==================== CLASSES UTILITÁRIAS ====================

class Utilities:
    """Funções utilitárias gerais"""
    
    @staticmethod
    def collect_garbage():
        """Coleta lixo da memória"""
        gc.collect()
    
    @staticmethod
    def log_error(error_message):
        """Registra erros em arquivo"""
        try:
            with open("error_log.txt", "a", encoding="utf-8") as error_log:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                error_log.write(f"[{timestamp}] {error_message}\n\n")
        except Exception:
            pass
    
    @staticmethod
    def clear_screen():
        """Limpa a tela"""
        os.system('clear')

class FileManager:
    """Gerenciador de arquivos e configurações"""
    
    SERVER_LINKS_FILE = "Shouko.dev/server-link.txt"
    ACCOUNTS_FILE = "Shouko.dev/account.txt"
    CONFIG_FILE = "Shouko.dev/config-wh.json"
    
    @staticmethod
    def xuat(file_path):
        """Extrai cookie do banco de dados"""
        try:
            if not os.path.exists(file_path):
                return None
            
            temp_path = file_path + ".temp_read"
            try:
                shutil.copy2(file_path, temp_path)
            except IOError:
                temp_path = file_path
            
            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM cookies WHERE name = '.ROBLOSECURITY'")
            result = cursor.fetchone()
            conn.close()
            
            if temp_path != file_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            
            if result:
                return result[0]
            return None
        except Exception as e:
            Utilities.log_error(f"Error in xuat: {e}")
            return None
    
    @staticmethod
    def find_userid_from_file(file_path):
        """Encontra User ID no arquivo appStorage.json"""
        try:
            if not os.path.exists(file_path):
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                user_id = data.get('RobloxUserIdentifier', '-1')
                return str(user_id)
        except Exception as e:
            Utilities.log_error(f"Error reading userid from {file_path}: {e}")
            return None
    
    @staticmethod
    def setup_user_ids():
        """Configura User IDs automaticamente"""
        print("\033[1;32m[ Shouko.dev ] - Auto-detecting User IDs...\033[0m")
        packages = RobloxManager.get_roblox_packages()
        accounts = []
        
        if not packages:
            print("\033[1;31m[ Shouko.dev ] - No Roblox packages detected.\033[0m")
            return []
        
        for package_name in packages:
            file_path = f'/data/data/{package_name}/files/appData/LocalStorage/appStorage.json'
            try:
                user_id = FileManager.find_userid_from_file(file_path)
                if user_id and user_id != "-1":
                    accounts.append((package_name, user_id))
                    print(f"\033[96m[ Shouko.dev ] - Found: {package_name} -> {user_id}\033[0m")
                else:
                    print(f"\033[1;33m[ Shouko.dev ] - UserID not found for {package_name}\033[0m")
            except Exception as e:
                print(f"\033[1;31m[ Shouko.dev ] - Error: {package_name}: {e}\033[0m")
                Utilities.log_error(f"Error in setup_user_ids for {package_name}: {e}")
        
        if accounts:
            FileManager.save_accounts(accounts)
            print("\033[1;32m[ Shouko.dev ] - User IDs saved successfully!\033[0m")
        else:
            print("\033[1;31m[ Shouko.dev ] - No valid User IDs found.\033[0m")
        
        return accounts
    
    @staticmethod
    def save_accounts(accounts):
        """Salva contas em arquivo"""
        try:
            os.makedirs(os.path.dirname(ACCOUNTS_FILE), exist_ok=True)
            with open(ACCOUNTS_FILE, "w", encoding="utf-8") as file:
                for package, user_id in accounts:
                    file.write(f"{package},{user_id}\n")
        except Exception as e:
            Utilities.log_error(f"Error saving accounts: {e}")
    
    @staticmethod
    def load_accounts():
        """Carrega contas do arquivo"""
        accounts = []
        if os.path.exists(ACCOUNTS_FILE):
            try:
                with open(ACCOUNTS_FILE, "r", encoding="utf-8") as file:
                    for line in file:
                        try:
                            package, user_id = line.strip().split(",", 1)
                            accounts.append((package, user_id))
                        except ValueError:
                            continue
            except Exception as e:
                Utilities.log_error(f"Error loading accounts: {e}")
        return accounts
    
    @staticmethod
    def save_server_links(server_links):
        """Salva links de servidor"""
        try:
            os.makedirs(os.path.dirname(FileManager.SERVER_LINKS_FILE), exist_ok=True)
            with open(FileManager.SERVER_LINKS_FILE, "w", encoding="utf-8") as file:
                for package, link in server_links:
                    file.write(f"{package},{link}\n")
            print("\033[1;32m[ Shouko.dev ] - Server links saved!\033[0m")
        except Exception as e:
            print(f"\033[1;31m[ Shouko.dev ] - Error saving server links: {e}\033[0m")
            Utilities.log_error(f"Error saving server links: {e}")
    
    @staticmethod
    def load_server_links():
        """Carrega links de servidor"""
        server_links = []
        if os.path.exists(FileManager.SERVER_LINKS_FILE):
            try:
                with open(FileManager.SERVER_LINKS_FILE, "r", encoding="utf-8") as file:
                    for line in file:
                        try:
                            package, link = line.strip().split(",", 1)
                            server_links.append((package, link))
                        except ValueError:
                            continue
            except Exception as e:
                Utilities.log_error(f"Error loading server links: {e}")
        return server_links
    
    @staticmethod
    def save_config():
        """Salva configuração geral"""
        global package_prefix, check_exec_enable
        try:
            config = {
                'package_prefix': package_prefix,
                'check_exec_enable': check_exec_enable
            }
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            Utilities.log_error(f"Error saving config: {e}")
    
    @staticmethod
    def load_config():
        """Carrega configuração geral"""
        global package_prefix, check_exec_enable
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    package_prefix = config.get('package_prefix', 'com.roblox')
                    check_exec_enable = config.get('check_exec_enable', '1')
            else:
                package_prefix = 'com.roblox'
                check_exec_enable = '1'
        except Exception as e:
            Utilities.log_error(f"Error loading config: {e}")
            package_prefix = 'com.roblox'
            check_exec_enable = '1'

class RobloxManager:
    """Gerenciador de funcionalidades do Roblox"""
    
    @staticmethod
    def get_roblox_packages():
        """Obtém lista de pacotes Roblox instalados"""
        global package_prefix
        try:
            result = subprocess.run(
                f"pm list packages | grep '{package_prefix}'",
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            packages = [
                line.replace('package:', '').strip() 
                for line in result.stdout.split('\n') 
                if line and 'package:' in line
            ]
            return packages
        except Exception as e:
            Utilities.log_error(f"Error getting packages: {e}")
            return []
    
    @staticmethod
    def format_server_link(link):
        """Formata link do servidor"""
        link = link.strip()
        if link.startswith("https://www.roblox.com/games/"):
            return link
        elif link.startswith("https://"):
            return link
        else:
            return f"https://www.roblox.com/games/{link}"
    
    @staticmethod
    def inject_cookies_and_appstorage():
        """Injeta cookies (requer root)"""
        print("\033[1;33m╔════════════════════════════════════════════════╗\033[0m")
        print("\033[1;33m║   COOKIE INJECTION - REQUIRES ROOT ACCESS      ║\033[0m")
        print("\033[1;33m╚════════════════════════════════════════════════╝\033[0m")
        print("\n\033[1;31m[!] Esta funcionalidade requer acesso ROOT\033[0m")
        print("\033[1;33m[!] Nem todos os setups do Termux suportam isso\033[0m")
        print("\n\033[96m[INFO] Para usar esta função você precisa:\033[0m")
        print("  1. Termux com root")
        print("  2. Permissões de superusuário")
        print("  3. Apps Roblox instalados\n")

class Runner:
    """Gerenciador de execução de pacotes"""
    
    @staticmethod
    def logout_all_packages():
        """Faz logout de todos os pacotes"""
        print("\033[1;33m[ Shouko.dev ] - Logging out all packages...\033[0m")
        packages = RobloxManager.get_roblox_packages()
        
        if not packages:
            print("\033[1;31m[ Shouko.dev ] - No packages found!\033[0m")
            return
        
        for package in packages:
            try:
                print(f"\033[96m → Clearing {package}...\033[0m")
                subprocess.run(
                    f"pm clear {package}",
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10
                )
                print(f"\033[1;32m ✓ {package} logged out!\033[0m")
            except Exception as e:
                print(f"\033[1;31m ✗ Error with {package}: {e}\033[0m")
                Utilities.log_error(f"Logout error for {package}: {e}")

class WebhookManager:
    """Gerenciador de webhooks"""
    
    @staticmethod
    def setup_webhook():
        """Configura webhook"""
        print("\033[1;36m╔════════════════════════════════════════════════╗\033[0m")
        print("\033[1;36m║           WEBHOOK CONFIGURATION                ║\033[0m")
        print("\033[1;36m╚════════════════════════════════════════════════╝\033[0m\n")
        
        webhook_url = input("\033[1;93m[ Shouko.dev ] - Webhook URL: \033[0m").strip()
        
        if webhook_url:
            device_name = input("\033[1;93m[ Shouko.dev ] - Device Name: \033[0m").strip()
            interval = input("\033[1;93m[ Shouko.dev ] - Interval (seconds): \033[0m").strip()
            
            config = {
                'webhook_url': webhook_url,
                'device_name': device_name or 'Termux-Device',
                'webhook_interval': interval or '60'
            }
            
            try:
                with open(FileManager.CONFIG_FILE, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=4)
                print("\n\033[1;32m[ Shouko.dev ] - Webhook configured!\033[0m")
            except Exception as e:
                print(f"\n\033[1;31m[ Shouko.dev ] - Error: {e}\033[0m")
                Utilities.log_error(f"Webhook config error: {e}")
        else:
            print("\n\033[1;31m[ Shouko.dev ] - Webhook URL cannot be empty.\033[0m")

def auto_change_android_id():
    """Muda Android ID automaticamente (requer root)"""
    global auto_android_id_enabled, auto_android_id_value
    
    while auto_android_id_enabled:
        try:
            if auto_android_id_value:
                subprocess.run(
                    f"settings put secure android_id {auto_android_id_value}",
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5
                )
            time.sleep(5)
        except Exception as e:
            Utilities.log_error(f"Android ID change error: {e}")
            time.sleep(5)

def display_banner():
    """Exibe banner do Shouko"""
    Utilities.clear_screen()
    console = Console()
    
    banner = """
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   ███████╗██╗  ██╗ ██████╗ ██╗   ██╗██╗  ██╗ ██████╗    ║
║   ██╔════╝██║  ██║██╔═══██╗██║   ██║██║ ██╔╝██╔═══██╗   ║
║   ███████╗███████║██║   ██║██║   ██║█████╔╝ ██║   ██║   ║
║   ╚════██║██╔══██║██║   ██║██║   ██║██╔═██╗ ██║   ██║   ║
║   ███████║██║  ██║╚██████╔╝╚██████╔╝██║  ██╗╚██████╔╝   ║
║   ╚══════╝╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═╝ ╚═════╝    ║
║                                                           ║
║          Roblox Multi-Account Manager v1.0.4             ║
║                   TERMUX EDITION                         ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """
    
    console.print(banner, style="cyan")
    console.print(f"\n[yellow]Version:[/yellow] [cyan]{version}[/cyan]")
    console.print("[yellow]Status:[/yellow] [green]Ready[/green]\n")

def main():
    """Função principal do programa"""
    global auto_android_id_enabled, auto_android_id_value, auto_android_id_thread
    global package_prefix, check_exec_enable
    
    # Carregar configuração
    FileManager.load_config()
    
    while True:
        try:
            display_banner()
            
            print("\033[1;36m╔══════════════════════════════════════════════════════════╗\033[0m")
            print("\033[1;36m║                     MENU PRINCIPAL                       ║\033[0m")
            print("\033[1;36m╚══════════════════════════════════════════════════════════╝\033[0m\n")
            
            print("\033[1;32m[1]\033[0m Setup User IDs (Auto-detect)")
            print("\033[1;32m[2]\033[0m Setup Server Links")
            print("\033[1;32m[3]\033[0m Inject Cookies (Root Required)")
            print("\033[1;32m[4]\033[0m Setup Webhook")
            print("\033[1;32m[5]\033[0m Configure Check Method")
            print("\033[1;32m[6]\033[0m Change Package Prefix")
            print("\033[1;32m[7]\033[0m Toggle Auto Android ID (Root)")
            print("\033[1;32m[8]\033[0m Launch All Packages")
            print("\033[1;32m[9]\033[0m Logout All Packages")
            print("\033[1;31m[0]\033[0m Exit")
            
            print("\n\033[1;36m" + "="*60 + "\033[0m")
            
            choice = input("\033[1;93m[ Shouko.dev ] - Select option: \033[0m").strip()
            
            if choice == "0":
                print("\n\033[1;32m[ Shouko.dev ] - Goodbye!\033[0m")
                sys.exit(0)
            
            elif choice == "1":
                try:
                    FileManager.setup_user_ids()
                except Exception as e:
                    print(f"\033[1;31m[ Shouko.dev ] - Error: {e}\033[0m")
                    Utilities.log_error(f"Setup User IDs error: {e}\n{traceback.format_exc()}")
                input("\n\033[1;32mPress Enter to continue...\033[0m")
            
            elif choice == "2":
                try:
                    accounts = FileManager.load_accounts()
                    if not accounts:
                        print("\033[1;31m[ Shouko.dev ] - No accounts found!\033[0m")
                        print("\033[1;33m[ Shouko.dev ] - Please setup User IDs first (option 1)\033[0m")
                        input("\n\033[1;32mPress Enter to continue...\033[0m")
                        continue
                    
                    print("\n\033[1;32m╔════════════════ AVAILABLE GAMES ═══════════════╗\033[0m")
                    games = [
                        "1. Blox Fruits", "2. Pet Simulator 99", "3. Anime Defenders",
                        "4. Fisch", "5. Brookhaven", "6. Sols RNG",
                        "7. Type Soul", "8. Jujutsu Infinite", "9. Cursed Arena",
                        "10. Dragon Adventures", "11. Steal A Brainrot",
                        "12. Blue Lock Rivals", "13. Arise Crossover",
                        "14. Other game (Custom ID/Link)"
                    ]
                    for game in games:
                        print(f"\033[96m  {game}\033[0m")
                    print("\033[1;32m╚═══════════════════════════════════════════════╝\033[0m\n")
                    
                    game_choice = input("\033[93m[ Shouko.dev ] - Enter choice (1-14): \033[0m").strip()
                    
                    game_ids = {
                        "1": "2753915549", "2": "126884695634066", "3": "4520749081",
                        "4": "16732694052", "5": "1537690962", "6": "12886143095",
                        "7": "116495829188952", "8": "17687504411", "9": "79546208627805",
                        "10": "142823291", "11": "109983668079237", "12": "18668065416",
                        "13": "87039211657390"
                    }
                    
                    if game_choice in game_ids:
                        server_link = game_ids[game_choice]
                    elif game_choice == "14":
                        server_link = input("\033[93m[ Shouko.dev ] - Enter game ID or link: \033[0m").strip()
                        if not server_link:
                            print("\033[1;31m[ Shouko.dev ] - Link cannot be empty!\033[0m")
                            input("\n\033[1;32mPress Enter to continue...\033[0m")
                            continue
                    else:
                        print("\033[1;31m[ Shouko.dev ] - Invalid choice!\033[0m")
                        input("\n\033[1;32mPress Enter to continue...\033[0m")
                        continue
                    
                    formatted_link = RobloxManager.format_server_link(server_link)
                    if formatted_link:
                        server_links = [(pkg, formatted_link) for pkg, _ in accounts]
                        FileManager.save_server_links(server_links)
                        print(f"\n\033[1;32m[ Shouko.dev ] - Server link set: {formatted_link}\033[0m")
                    else:
                        print("\033[1;31m[ Shouko.dev ] - Invalid link format!\033[0m")
                
                except Exception as e:
                    print(f"\033[1;31m[ Shouko.dev ] - Error: {e}\033[0m")
                    Utilities.log_error(f"Server links error: {e}\n{traceback.format_exc()}")
                
                input("\n\033[1;32mPress Enter to continue...\033[0m")
            
            elif choice == "3":
                RobloxManager.inject_cookies_and_appstorage()
                input("\n\033[1;32mPress Enter to continue...\033[0m")
            
            elif choice == "4":
                WebhookManager.setup_webhook()
                input("\n\033[1;32mPress Enter to continue...\033[0m")
            
            elif choice == "5":
                try:
                    print("\n\033[1;35m[1]\033[1;32m Executor Check\033[0m")
                    print("\033[1;35m[2]\033[1;36m Online Check\033[0m")
                    
                    method = input("\n\033[1;93m[ Shouko.dev ] - Select (1-2, 'q' for default): \033[0m").strip()
                    
                    if method.lower() == "q" or method == "1":
                        check_exec_enable = "1"
                        print("\033[1;32m[ Shouko.dev ] - Set to Executor Check\033[0m")
                    elif method == "2":
                        check_exec_enable = "0"
                        print("\033[1;36m[ Shouko.dev ] - Set to Online Check\033[0m")
                    else:
                        print("\033[1;31m[ Shouko.dev ] - Invalid choice, keeping default\033[0m")
                        check_exec_enable = "1"
                    
                    FileManager.save_config()
                    print("\033[1;32m[ Shouko.dev ] - Configuration saved!\033[0m")
                    
                except Exception as e:
                    print(f"\033[1;31m[ Shouko.dev ] - Error: {e}\033[0m")
                    Utilities.log_error(f"Check method error: {e}")
                
                input("\n\033[1;32mPress Enter to continue...\033[0m")
            
            elif choice == "6":
                try:
                    print(f"\n\033[1;32m[ Shouko.dev ] - Current prefix: {package_prefix}\033[0m")
                    new_prefix = input("\033[1;93m[ Shouko.dev ] - New prefix (Enter to keep): \033[0m").strip()
                    
                    if new_prefix:
                        package_prefix = new_prefix
                        FileManager.save_config()
                        print(f"\033[1;32m[ Shouko.dev ] - Updated to: {package_prefix}\033[0m")
                    else:
                        print(f"\033[1;33m[ Shouko.dev ] - Unchanged: {package_prefix}\033[0m")
                    
                except Exception as e:
                    print(f"\033[1;31m[ Shouko.dev ] - Error: {e}\033[0m")
                    Utilities.log_error(f"Package prefix error: {e}")
                
                input("\n\033[1;32mPress Enter to continue...\033[0m")
            
            elif choice == "7":
                if not auto_android_id_enabled:
                    android_id = input("\033[1;93m[ Shouko.dev ] - Android ID: \033[0m").strip()
                    if not android_id:
                        print("\033[1;31m[ Shouko.dev ] - ID cannot be empty!\033[0m")
                        input("\n\033[1;32mPress Enter to continue...\033[0m")
                        continue
                    
                    auto_android_id_value = android_id
                    auto_android_id_enabled = True
                    
                    if auto_android_id_thread is None or not auto_android_id_thread.is_alive():
                        auto_android_id_thread = threading.Thread(
                            target=auto_change_android_id, 
                            daemon=True
                        )
                        auto_android_id_thread.start()
                    
                    print("\033[1;32m[ Shouko.dev ] - Auto Android ID enabled!\033[0m")
                else:
                    auto_android_id_enabled = False
                    print("\033[1;31m[ Shouko.dev ] - Auto Android ID disabled!\033[0m")
                
                input("\n\033[1;32mPress Enter to continue...\033[0m")
            
            elif choice == "8":
                try:
                    print("\n\033[1;32m[ Shouko.dev ] - Scanning packages...\033[0m")
                    packages = RobloxManager.get_roblox_packages()
                    
                    if not packages:
                        print("\033[1;31m[ Shouko.dev ] - No Roblox packages found!\033[0m")
                    else:
                        print(f"\033[1;32m[ Shouko.dev ] - Found {len(packages)} package(s)\033[0m\n")
                        
                        for pkg in packages:
                            print(f"\033[1;33m → Launching {pkg}...\033[0m")
                            try:
                                subprocess.run(
                                    f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1",
                                    shell=True,
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL,
                                    timeout=5
                                )
                                print(f"\033[1;32m ✓ Launched!\033[0m")
                                time.sleep(1.5)
                            except Exception as e:
                                print(f"\033[1;31m ✗ Error: {e}\033[0m")
                        
                        print(f"\n\033[1;32m[ Shouko.dev ] - Done!\033[0m")
                
                except Exception as e:
                    print(f"\033[1;31m[ Shouko.dev ] - Error: {e}\033[0m")
                    Utilities.log_error(f"Launch packages error: {e}")
                
                input("\n\033[1;32mPress Enter to continue...\033[0m")
            
            elif choice == "9":
                try:
                    Runner.logout_all_packages()
                except Exception as e:
                    print(f"\033[1;31m[ Shouko.dev ] - Error: {e}\033[0m")
                    Utilities.log_error(f"Logout error: {e}")
                
                input("\n\033[1;32mPress Enter to continue...\033[0m")
            
            else:
                print("\033[1;31m[ Shouko.dev ] - Invalid option!\033[0m")
                time.sleep(1)
        
        except KeyboardInterrupt:
            print("\n\n\033[1;33m[ Shouko.dev ] - Interrupted by user\033[0m")
            sys.exit(0)
        except Exception as e:
            print(f"\n\033[1;31m[ Shouko.dev ] - Critical error: {e}\033[0m")
            Utilities.log_error(f"CRITICAL ERROR: {e}\n{traceback.format_exc()}")
            input("\n\033[1;32mPress Enter to continue...\033[0m")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\033[1;33m[ Shouko.dev ] - Goodbye!\033[0m")
        sys.exit(0)
    except Exception as e:
        print(f"\n\033[1;31m[ Shouko.dev ] - Fatal error: {e}\033[0m")
        Utilities.log_error(f"FATAL ERROR: {e}\n{traceback.format_exc()}")
        sys.exit(1)
