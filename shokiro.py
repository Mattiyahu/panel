#!/data/data/com.termux/files/usr/bin/python
"""
Shouko Bot - Versão corrigida para Termux
Com autosetup de dependências
"""

import os
import sys
import subprocess
import time

# Função de autosetup para instalar dependências
def autosetup():
    """Instala automaticamente as dependências necessárias no Termux"""
    print("\033[1;36m" + "="*60 + "\033[0m")
    print("\033[1;32m[ Shouko.dev ] - INICIANDO AUTOSETUP PARA TERMUX\033[0m")
    print("\033[1;36m" + "="*60 + "\033[0m\n")
    
    # Lista de pacotes do Termux necessários
    termux_packages = [
        'python',
        'python-pip',
        'git',
        'wget',
        'curl'
    ]
    
    # Lista de módulos Python necessários
    python_packages = [
        'prettytable',
        'requests',
        'psutil',
        'rich'
    ]
    
    # Atualizar repositórios do Termux
    print("\033[1;33m[ Shouko.dev ] - Atualizando repositórios do Termux...\033[0m")
    try:
        subprocess.run(['pkg', 'update', '-y'], check=False)
        print("\033[1;32m[ Shouko.dev ] - Repositórios atualizados!\033[0m\n")
    except Exception as e:
        print(f"\033[1;31m[ Shouko.dev ] - Erro ao atualizar repositórios: {e}\033[0m\n")
    
    # Instalar pacotes do Termux
    print("\033[1;33m[ Shouko.dev ] - Instalando pacotes do Termux...\033[0m")
    for package in termux_packages:
        try:
            print(f"\033[96m  → Instalando {package}...\033[0m")
            subprocess.run(['pkg', 'install', '-y', package], 
                         stdout=subprocess.DEVNULL, 
                         stderr=subprocess.DEVNULL,
                         check=False)
            print(f"\033[1;32m  ✓ {package} instalado!\033[0m")
        except Exception as e:
            print(f"\033[1;31m  ✗ Erro ao instalar {package}: {e}\033[0m")
    
    print()
    
    # Instalar módulos Python
    print("\033[1;33m[ Shouko.dev ] - Instalando módulos Python...\033[0m")
    for package in python_packages:
        try:
            print(f"\033[96m  → Instalando {package}...\033[0m")
            subprocess.run([sys.executable, '-m', 'pip', 'install', package, '--upgrade'],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL,
                         check=False)
            print(f"\033[1;32m  ✓ {package} instalado!\033[0m")
        except Exception as e:
            print(f"\033[1;31m  ✗ Erro ao instalar {package}: {e}\033[0m")
    
    print()
    print("\033[1;32m" + "="*60 + "\033[0m")
    print("\033[1;32m[ Shouko.dev ] - AUTOSETUP CONCLUÍDO!\033[0m")
    print("\033[1;32m" + "="*60 + "\033[0m\n")
    time.sleep(2)

# Verificar se é primeira execução
if not os.path.exists('Shouko.dev/.setup_complete'):
    autosetup()
    os.makedirs('Shouko.dev', exist_ok=True)
    with open('Shouko.dev/.setup_complete', 'w') as f:
        f.write('1')

# Importações após setup
try:
    from prettytable import PrettyTable
    import threading
    import json
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
    print(f"\033[1;31m[ Shouko.dev ] - Erro ao importar módulos: {e}\033[0m")
    print("\033[1;33m[ Shouko.dev ] - Execute o script novamente para reinstalar dependências.\033[0m")
    if os.path.exists('Shouko.dev/.setup_complete'):
        os.remove('Shouko.dev/.setup_complete')
    sys.exit(1)

# Variáveis globais
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

system_boot_time = psutil.boot_time()

auto_android_id_enabled = False
auto_android_id_thread = None
auto_android_id_value = None

globals()["_disable_ui"] = "0"
globals()["package_statuses"] = {}
globals()["_uid_"] = {}
globals()["_user_"] = {}
globals()["is_runner_ez"] = False
globals()["check_exec_enable"] = "1"

# Caminhos para Termux (ajustados)
executors = {
    "Delta": "/storage/emulated/0/Delta/",
    "Codex": "/storage/emulated/0/Codex/",
    "Arceus X": "/storage/emulated/0/Arceus X/",
    "FluxusZ": "/storage/emulated/0/FluxusZ/",
    "Neutron": "/storage/emulated/0/Neutron/",
}

workspace_paths = [f"{base_path}Workspace" for base_path in executors.values()] + \
                  [f"{base_path}workspace" for base_path in executors.values()]
globals()["workspace_paths"] = workspace_paths
globals()["executors"] = executors

if not os.path.exists("Shouko.dev"):
    os.makedirs("Shouko.dev", exist_ok=True)
    
SERVER_LINKS_FILE = "Shouko.dev/server-links.txt"
ACCOUNTS_FILE = "Shouko.dev/accounts.txt"
CONFIG_FILE = "Shouko.dev/config.json"

version = "1.0.3 | Termux Edition | Created By Neyoshi And Improved By Nexus/Gemini"

class Utilities:
    @staticmethod
    def collect_garbage():
        gc.collect()

    @staticmethod
    def log_error(error_message):
        with open("error_log.txt", "a") as error_log:
            error_log.write(f"{error_message}\n\n")

    @staticmethod
    def clear_screen():
        os.system('clear')

class FileManager:
    SERVER_LINKS_FILE = "Shouko.dev/server-link.txt"
    ACCOUNTS_FILE = "Shouko.dev/account.txt"
    CONFIG_FILE = "Shouko.dev/config-wh.json"

    @staticmethod
    def xuat(file_path):
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
                except:
                    pass

            if result:
                return result[0]
            return None
        except Exception as e:
            return None

    @staticmethod
    def setup_user_ids():
        print("\033[1;32m[ Shouko.dev ] - Auto-detecting User IDs from app packages...\033[0m")
        packages = RobloxManager.get_roblox_packages()
        accounts = []
        if not packages:
            print("\033[1;31m[ Shouko.dev ] - No Roblox packages detected to set up User IDs.\033[0m")
            return []

        for package_name in packages:
            file_path = f'/data/data/{package_name}/files/appData/LocalStorage/appStorage.json'
            try:
                user_id = FileManager.find_userid_from_file(file_path)
                if user_id and user_id != "-1":
                    accounts.append((package_name, user_id))
                    print(f"\033[96m[ Shouko.dev ] - Found UserID for {package_name}: {user_id}\033[0m")
                else:
                    print(f"\033[1;31m[ Shouko.dev ] - UserID not found for {package_name}.\033[0m")
            except Exception as e:
                print(f"\033[1;31m[ Shouko.dev ] - Error reading file for {package_name}: {e}\033[0m")
                Utilities.log_error(f"Error reading appStorage.json for {package_name}: {e}")

        if accounts:
            FileManager.save_accounts(accounts)
            print("\033[1;32m[ Shouko.dev ] - User IDs have been successfully saved.\033[0m")
        else:
            print("\033[1;31m[ Shouko.dev ] - Could not find any valid User IDs to set up.\033[0m")
            
        return accounts

    @staticmethod
    def find_userid_from_file(file_path):
        """Encontra o User ID no arquivo appStorage.json"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                return str(data.get('RobloxUserIdentifier', '-1'))
        except Exception:
            return None

    @staticmethod
    def save_accounts(accounts):
        """Salva as contas no arquivo"""
        try:
            os.makedirs(os.path.dirname(ACCOUNTS_FILE), exist_ok=True)
            with open(ACCOUNTS_FILE, "w") as file:
                for package, user_id in accounts:
                    file.write(f"{package},{user_id}\n")
        except Exception as e:
            Utilities.log_error(f"Error saving accounts: {e}")

    @staticmethod
    def load_accounts():
        """Carrega as contas do arquivo"""
        accounts = []
        if os.path.exists(ACCOUNTS_FILE):
            with open(ACCOUNTS_FILE, "r") as file:
                for line in file:
                    try:
                        package, user_id = line.strip().split(",", 1)
                        accounts.append((package, user_id))
                    except ValueError:
                        continue
        return accounts

    @staticmethod
    def save_server_links(server_links):
        try:
            os.makedirs(os.path.dirname(FileManager.SERVER_LINKS_FILE), exist_ok=True)
            with open(FileManager.SERVER_LINKS_FILE, "w") as file:
                for package, link in server_links:
                    file.write(f"{package},{link}\n")
            print("\033[1;32m[ Shouko.dev ] - Server links saved successfully.\033[0m")
        except IOError as e:
            print(f"\033[1;31m[ Shouko.dev ] - Error saving server links: {e}\033[0m")
            Utilities.log_error(f"Error saving server links: {e}")

    @staticmethod
    def load_server_links():
        server_links = []
        if os.path.exists(FileManager.SERVER_LINKS_FILE):
            with open(FileManager.SERVER_LINKS_FILE, "r") as file:
                for line in file:
                    try:
                        package, link = line.strip().split(",", 1)
                        server_links.append((package, link))
                    except ValueError:
                        continue
        return server_links

    @staticmethod
    def save_config():
        """Salva a configuração"""
        try:
            config = {
                'package_prefix': globals().get('package_prefix', 'com.roblox'),
                'check_exec_enable': globals().get('check_exec_enable', '1')
            }
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            Utilities.log_error(f"Error saving config: {e}")

    @staticmethod
    def load_config():
        """Carrega a configuração"""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    globals()['package_prefix'] = config.get('package_prefix', 'com.roblox')
                    globals()['check_exec_enable'] = config.get('check_exec_enable', '1')
        except Exception as e:
            Utilities.log_error(f"Error loading config: {e}")
            globals()['package_prefix'] = 'com.roblox'
            globals()['check_exec_enable'] = '1'

class RobloxManager:
    @staticmethod
    def get_roblox_packages():
        """Obtém lista de pacotes Roblox instalados"""
        try:
            prefix = globals().get('package_prefix', 'com.roblox')
            result = subprocess.run(
                f"pm list packages | grep '{prefix}'",
                shell=True,
                capture_output=True,
                text=True
            )
            packages = [line.replace('package:', '').strip() 
                       for line in result.stdout.split('\n') if line]
            return packages
        except Exception as e:
            Utilities.log_error(f"Error getting packages: {e}")
            return []

    @staticmethod
    def format_server_link(link):
        """Formata o link do servidor"""
        if link.startswith("https://www.roblox.com/games/"):
            return link
        elif link.startswith("https://"):
            return link
        else:
            return f"https://www.roblox.com/games/{link}"

    @staticmethod
    def inject_cookies_and_appstorage():
        """Injeta cookies e appStorage"""
        print("\033[1;33m[ Shouko.dev ] - Cookie injection feature requires root access\033[0m")
        print("\033[1;33m[ Shouko.dev ] - This feature may not work in all Termux setups\033[0m")
        input("\033[1;32mPress Enter to continue...\033[0m")

class Runner:
    @staticmethod
    def logout_all_packages():
        """Faz logout de todos os pacotes"""
        print("\033[1;33m[ Shouko.dev ] - Logging out all packages...\033[0m")
        packages = RobloxManager.get_roblox_packages()
        for package in packages:
            try:
                # Limpar dados do app
                subprocess.run(f"pm clear {package}", shell=True, 
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"\033[1;32m[ Shouko.dev ] - Logged out: {package}\033[0m")
            except Exception as e:
                print(f"\033[1;31m[ Shouko.dev ] - Error with {package}: {e}\033[0m")

class WebhookManager:
    @staticmethod
    def setup_webhook():
        """Configura webhook"""
        print("\033[1;33m[ Shouko.dev ] - Webhook Setup\033[0m")
        webhook_url = input("\033[1;93m[ Shouko.dev ] - Enter webhook URL: \033[0m").strip()
        
        if webhook_url:
            config = {
                'webhook_url': webhook_url,
                'device_name': input("\033[1;93m[ Shouko.dev ] - Enter device name: \033[0m").strip(),
                'webhook_interval': input("\033[1;93m[ Shouko.dev ] - Enter webhook interval (seconds): \033[0m").strip()
            }
            
            try:
                with open(FileManager.CONFIG_FILE, 'w') as f:
                    json.dump(config, f, indent=4)
                print("\033[1;32m[ Shouko.dev ] - Webhook configuration saved!\033[0m")
            except Exception as e:
                print(f"\033[1;31m[ Shouko.dev ] - Error saving webhook config: {e}\033[0m")
        else:
            print("\033[1;31m[ Shouko.dev ] - Webhook URL cannot be empty.\033[0m")

def auto_change_android_id():
    """Auto change Android ID (requires root)"""
    global auto_android_id_enabled, auto_android_id_value
    while auto_android_id_enabled:
        try:
            if auto_android_id_value:
                subprocess.run(
                    f"settings put secure android_id {auto_android_id_value}",
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            time.sleep(5)
        except Exception as e:
            Utilities.log_error(f"Android ID change error: {e}")
            time.sleep(5)

def display_banner():
    """Exibe o banner do Shouko"""
    Utilities.clear_screen()
    console = Console()
    
    banner_text = """
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   ███████╗██╗  ██╗ ██████╗ ██╗   ██╗██╗  ██╗ ██████╗    ║
║   ██╔════╝██║  ██║██╔═══██╗██║   ██║██║ ██╔╝██╔═══██╗   ║
║   ███████╗███████║██║   ██║██║   ██║█████╔╝ ██║   ██║   ║
║   ╚════██║██╔══██║██║   ██║██║   ██║██╔═██╗ ██║   ██║   ║
║   ███████║██║  ██║╚██████╔╝╚██████╔╝██║  ██╗╚██████╔╝   ║
║   ╚══════╝╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═╝ ╚═════╝    ║
║                                                           ║
║              Roblox Multi-Account Manager                ║
║                   Termux Edition                         ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """
    
    console.print(Panel(
        banner_text,
        style="cyan",
        border_style="bright_blue"
    ))
    
    console.print(f"\n[yellow]Version:[/yellow] [cyan]{version}[/cyan]")
    console.print("[yellow]Status:[/yellow] [green]Ready[/green]\n")

def main():
    """Função principal"""
    FileManager.load_config()
    
    while True:
        display_banner()
        
        print("\033[1;36m╔══════════════════════════════════════════════════════════╗\033[0m")
        print("\033[1;36m║                     MENU PRINCIPAL                       ║\033[0m")
        print("\033[1;36m╚══════════════════════════════════════════════════════════╝\033[0m\n")
        
        print("\033[1;32m[1]\033[0m Setup User IDs (Auto-detect)")
        print("\033[1;32m[2]\033[0m Setup Server Links")
        print("\033[1;32m[3]\033[0m Inject Cookies (Requires Root)")
        print("\033[1;32m[4]\033[0m Setup Webhook")
        print("\033[1;32m[5]\033[0m Configure Check Method")
        print("\033[1;32m[6]\033[0m Change Package Prefix")
        print("\033[1;32m[7]\033[0m Toggle Auto Android ID")
        print("\033[1;32m[8]\033[0m Launch All Packages")
        print("\033[1;32m[9]\033[0m Logout All Packages")
        print("\033[1;31m[0]\033[0m Exit")
        
        print("\n\033[1;36m" + "="*60 + "\033[0m")
        
        setup_type = input("\033[1;93m[ Shouko.dev ] - Select option: \033[0m").strip()
        
        if setup_type == "0":
            print("\033[1;32m[ Shouko.dev ] - Goodbye!\033[0m")
            sys.exit(0)
        
        elif setup_type == "1":
            try:
                FileManager.setup_user_ids()
            except Exception as e:
                print(f"\033[1;31m[ Shouko.dev ] - Error: {e}\033[0m")
                Utilities.log_error(f"Setup User IDs error: {e}")
            input("\033[1;32mPress Enter to return...\033[0m")
            continue
        
        elif setup_type == "2":
            try:
                accounts = FileManager.load_accounts()
                if not accounts:
                    print("\033[1;31m[ Shouko.dev ] - No accounts found. Please setup User IDs first.\033[0m")
                    input("\033[1;32mPress Enter to return...\033[0m")
                    continue
                
                print("\n\033[1;32m[ Shouko.dev ] - Available Games:\033[0m\n")
                games = [
                    "1. Blox Fruits", "2. Pet Simulator 99", "3. Anime Defenders",
                    "4. Fisch", "5. Brookhaven", "6. Sols RNG", "7. Type Soul",
                    "8. Jujutsu Infinite", "9. Cursed Arena", "10. Dragon Adventures",
                    "11. Steal A Brainrot", "12. Blue Lock Rivals", "13. Arise Crossover",
                    "14. Other game or Private Server Link"
                ]
                for game in games:
                    print(f"\033[96m{game}\033[0m")
                
                choice = input("\033[93m[ Shouko.dev ] - Enter choice: \033[0m").strip()
                game_ids = {
                    "1": "2753915549", "2": "126884695634066", "3": "4520749081",
                    "4": "16732694052", "5": "1537690962", "6": "12886143095",
                    "7": "116495829188952", "8": "17687504411", "9": "79546208627805",
                    "10": "142823291", "11": "109983668079237", "12": "18668065416",
                    "13": "87039211657390"
                }
                
                if choice in game_ids:
                    server_link = game_ids[choice]
                elif choice == "14":
                    server_link = input("\033[93m[ Shouko.dev ] - Enter game ID or private server link: \033[0m")
                else:
                    print("\033[1;31m[ Shouko.dev ] - Invalid choice.\033[0m")
                    input("\033[1;32mPress Enter to return...\033[0m")
                    continue
                
                formatted_link = RobloxManager.format_server_link(server_link)
                if formatted_link:
                    server_links = [(package_name, formatted_link) for package_name, _ in accounts]
                    FileManager.save_server_links(server_links)
                else:
                    print("\033[1;31m[ Shouko.dev ] - Invalid server link.\033[0m")
                
            except Exception as e:
                print(f"\033[1;31m[ Shouko.dev ] - Error: {e}\033[0m")
                Utilities.log_error(f"Setup error: {e}")
            
            input("\033[1;32mPress Enter to return...\033[0m")
            continue
        
        elif setup_type == "3":
            RobloxManager.inject_cookies_and_appstorage()
            input("\033[1;32m\nPress Enter to exit...\033[0m")
            continue
        
        elif setup_type == "4":
            WebhookManager.setup_webhook()
            input("\033[1;32m\nPress Enter to exit...\033[0m")
            continue
        
        elif setup_type == "5":
            try:
                print("\033[1;35m[1]\033[1;32m Executor Check\033[0m \033[1;35m[2]\033[1;36m Online Check\033[0m")
                config_choice = input("\033[1;93m[ Shouko.dev ] - Select check method (1-2, 'q' to keep default): \033[0m").strip()
                
                if config_choice.lower() == "q":
                    globals()["check_exec_enable"] = "1"
                    print("\033[1;32m[ Shouko.dev ] - Default set: Executor + Shouko Check\033[0m")
                elif config_choice == "1":
                    globals()["check_exec_enable"] = "1"
                    print("\033[1;32m[ Shouko.dev ] - Set to Executor + Shouko Check\033[0m")
                elif config_choice == "2":
                    globals()["check_exec_enable"] = "0"
                    print("\033[1;36m[ Shouko.dev ] - Set to Online Check.\033[0m")
                else:
                    print("\033[1;31m[ Shouko.dev ] - Invalid choice. Keeping default.\033[0m")
                    globals()["check_exec_enable"] = "1"
                
                FileManager.save_config()
                print("\033[1;32m[ Shouko.dev ] - Check method configuration saved.\033[0m")
            except Exception as e:
                print(f"\033[1;31m[ Shouko.dev ] - Error setting up check method: {e}\033[0m")
                Utilities.log_error(f"Check method setup error: {e}")
            
            input("\033[1;32mPress Enter to return...\033[0m")
            continue
        
        elif setup_type == "6":
            try:
                current_prefix = globals().get("package_prefix", "com.roblox")
                print(f"\033[1;32m[ Shouko.dev ] - Current package prefix: {current_prefix}\033[0m")
                new_prefix = input("\033[1;93m[ Shouko.dev ] - Enter new package prefix (or press Enter to keep current): \033[0m").strip()
                
                if new_prefix:
                    globals()["package_prefix"] = new_prefix
                    FileManager.save_config()
                    print(f"\033[1;32m[ Shouko.dev ] - Package prefix updated to: {new_prefix}\033[0m")
                else:
                    print(f"\033[1;33m[ Shouko.dev ] - Package prefix unchanged: {current_prefix}\033[0m")
            except Exception as e:
                print(f"\033[1;31m[ Shouko.dev ] - Error setting package prefix: {e}\033[0m")
                Utilities.log_error(f"Error setting package prefix: {e}")
            
            input("\033[1;32mPress Enter to return...\033[0m")
            continue
        
        elif setup_type == "7":
            global auto_android_id_enabled, auto_android_id_value, auto_android_id_thread
            
            if not auto_android_id_enabled:
                android_id = input("\033[1;93m[ Shouko.dev ] - Enter Android ID to spam set: \033[0m").strip()
                if not android_id:
                    print("\033[1;31m[ Shouko.dev ] - Android ID cannot be empty.\033[0m")
                    input("\033[1;32mPress Enter to return...\033[0m")
                    continue
                auto_android_id_value = android_id
                auto_android_id_enabled = True
                if auto_android_id_thread is None or not auto_android_id_thread.is_alive():
                    auto_android_id_thread = threading.Thread(target=auto_change_android_id, daemon=True)
                    auto_android_id_thread.start()
                print("\033[1;32m[ Shouko.dev ] - Auto change Android ID enabled.\033[0m")
            else:
                auto_android_id_enabled = False
                print("\033[1;31m[ Shouko.dev ] - Auto change Android ID disabled.\033[0m")
            
            input("\033[1;32mPress Enter to return...\033[0m")
            continue
        
        elif setup_type == "8":
            try:
                print("\033[1;32m[ Shouko.dev ] - Scanning for packages...\033[0m")
                packages = RobloxManager.get_roblox_packages()
                if not packages:
                    print("\033[1;31m[ Shouko.dev ] - No Roblox packages found!\033[0m")
                else:
                    print(f"\033[1;32m[ Shouko.dev ] - Found {len(packages)} packages. Launching...\033[0m")
                    for pkg in packages:
                        print(f"\033[1;33m[ Shouko.dev ] - Launching {pkg}...\033[0m")
                        subprocess.run(f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1",
                                     shell=True,
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
                        time.sleep(1.5)
                    print("\033[1;32m[ Shouko.dev ] - All packages launched!\033[0m")
            except Exception as e:
                print(f"\033[1;31m[ Shouko.dev ] - Error: {e}\033[0m")
            
            input("\033[1;32mPress Enter to return...\033[0m")
            continue
        
        elif setup_type == "9":
            try:
                Runner.logout_all_packages()
            except Exception as e:
                print(f"\033[1;31m[ Shouko.dev ] - Error: {e}\033[0m")
            
            input("\033[1;32mPress Enter to return...\033[0m")
            continue

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\033[1;33m[ Shouko.dev ] - Interrupted by user\033[0m")
        sys.exit(0)
    except Exception as e:
        print(f"\033[1;31m[ Shouko.dev ] - Error: {e}\033[0m")
        Utilities.log_error(f"CRITICAL MAIN ERROR: {e}\n{traceback.format_exc()}")
        raise
