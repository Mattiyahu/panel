from prettytable import PrettyTable

import threading

import time

import json

import requests

import subprocess

import sqlite3

import shutil

import traceback

import random

import gc

import os


# Importação condicional do psutil para compatibilidade com Termux

try:

    import psutil

    PSUTIL_AVAILABLE = True

except ImportError:

    PSUTIL_AVAILABLE = False


from rich.table import Table

from rich.panel import Panel

from rich.text import Text

from rich.align import Align

from rich.box import ROUNDED

from rich.console import Console

from datetime import datetime, timezone

from threading import Lock, Event
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


# Função segura para obter boot_time no Termux

def get_safe_boot_time():
    """Obtém o tempo de boot de forma segura, compatível com Termux."""

    # Método 1: Tentar psutil (pode falhar no Termux sem root)

    if PSUTIL_AVAILABLE:

        try:

            return psutil.boot_time()

        except (PermissionError, OSError):

            pass

    # Método 2: Ler /proc/uptime (mais permissivo no Termux)

    try:

        with open('/proc/uptime', 'r') as f:

            uptime_seconds = float(f.readline().split()[0])

            return time.time() - uptime_seconds

    except (PermissionError, FileNotFoundError, OSError):

        pass

    # Método 3: Usar o tempo atual como fallback

    return time.time()


system_boot_time = get_safe_boot_time()


auto_android_id_enabled = False

auto_android_id_thread = None

auto_android_id_value = None


globals()["_disable_ui"] = "0"

globals()["package_statuses"] = {}

globals()["_uid_"] = {}

globals()["_user_"] = {}

globals()["is_runner_ez"] = False

globals()["check_exec_enable"] = "1"


executors = {

    "Delta": "/storage/emulated/0/Delta/",

    "Codex": "/storage/emulated/0/Codex/",

    "Arceus X": "/storage/emulated/0/Arceus X/",

    "FluxusZ": "/storage/emulated/0/FluxusZ/",

    "Neutron": "/storage/emulated/0/Neutron/",

}


workspace_paths = [f"{base_path}Workspace" for base_path in executors.values()] +
   [f"{base_path}workspace" for base_path in executors.values()]

globals()["workspace_paths"] = workspace_paths

globals()["executors"] = executors


if not os.path.exists("Shako.dev"):

    os.makedirs("Shako.dev", exist_ok=True)

SERVER_LINKS_FILE = "Shako.dev/server-links.txt"

ACCOUNTS_FILE = "Shako.dev/accounts.txt"

CONFIG_FILE = "Shako.dev/config.json"


version = "1.0.4 | Shako Edition - Termux Compatible"


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

        os.system('cls' if os.name == 'nt' else 'clear')


class TermuxCompat:

    """Classe para funções compatíveis com Termux."""

    @staticmethod
    def get_cpu_percent(interval=None):
        """Obtém uso de CPU de forma segura no Termux."""

        if PSUTIL_AVAILABLE:

            try:

                return psutil.cpu_percent(interval=interval)

            except (PermissionError, OSError):

                pass

        # Fallback: ler /proc/stat

        try:

            with open('/proc/stat', 'r') as f:

                line = f.readline()

                if line.startswith('cpu '):

                    values = line.split()[1:8]

                    values = [int(v) for v in values]

                    idle = values[3]

                    total = sum(values)

                    return round((1 - idle / total) * 100, 1)

        except (PermissionError, FileNotFoundError, OSError):

            pass

        return 0.0

    @staticmethod
    def get_memory_info():
        """Obtém informações de memória de forma segura no Termux."""

        if PSUTIL_AVAILABLE:

            try:

                return psutil.virtual_memory()

            except (PermissionError, OSError):

                pass

        # Fallback: ler /proc/meminfo

        try:

            meminfo = {}

            with open('/proc/meminfo', 'r') as f:

                for line in f:

                    parts = line.split()

                    if len(parts) >= 2:

                        key = parts[0].rstrip(':')

                        value = int(parts[1]) * 1024  # Converter KB para bytes

                        meminfo[key] = value

            total = meminfo.get('MemTotal', 0)

            available = meminfo.get('MemAvailable', meminfo.get('MemFree', 0))

            used = total - available

            percent = (used / total * 100) if total > 0 else 0

            class MemInfo:

                pass

            info = MemInfo()

            info.total = total

            info.available = available

            info.used = used

            info.percent = percent

            return info

        except (PermissionError, FileNotFoundError, OSError):

            pass

        # Fallback final

        class MemInfo:

            total = 0

            available = 0

            used = 0

            percent = 0

        return MemInfo()

    @staticmethod
    def get_process_memory():
        """Obtém uso de memória do processo atual."""

        if PSUTIL_AVAILABLE:

            try:

                process = psutil.Process(os.getpid())

                return process.memory_info().rss / (1024 ** 2)

            except (PermissionError, OSError):

                pass

        # Fallback: ler /proc/self/status

        try:

            with open('/proc/self/status', 'r') as f:

                for line in f:

                    if line.startswith('VmRSS:'):

                        return int(line.split()[1]) / 1024  # KB para MB

        except (PermissionError, FileNotFoundError, OSError):

            pass

        return 0.0

    @staticmethod
    def process_iter(attrs=None):
        """Itera sobre processos de forma segura no Termux."""

        if PSUTIL_AVAILABLE:

            try:

                for proc in psutil.process_iter(attrs):

                    yield proc

                return

            except (PermissionError, OSError):

                pass

        # Fallback: usar /proc diretamente

        try:

            for pid_str in os.listdir('/proc'):

                if pid_str.isdigit():

                    try:

                        pid = int(pid_str)

                        cmdline_path = f'/proc/{pid}/cmdline'

                        comm_path = f'/proc/{pid}/comm'

                        name = ""

                        cmdline = []

                        if os.path.exists(comm_path):

                            with open(comm_path, 'r') as f:

                                name = f.read().strip()

                        if os.path.exists(cmdline_path):

                            with open(cmdline_path, 'r') as f:

                                cmdline = f.read().split('\x00')

                        class ProcInfo:

                            pass

                        proc = ProcInfo()

                        proc.info = {
    'pid': pid, 'name': name, 'cmdline': cmdline}

                        proc.pid = pid

                        yield proc

                    except (PermissionError, FileNotFoundError, OSError):

                        continue

        except (PermissionError, OSError):

            pass

    @staticmethod
    def kill_process(pid):
        """Mata um processo de forma segura."""

        if PSUTIL_AVAILABLE:

            try:

                proc = psutil.Process(pid)

                proc.kill()

                return True

            except (psutil.NoSuchProcess, PermissionError, OSError):

                pass

        # Fallback: usar kill do sistema

        try:

            os.kill(pid, 9)  # SIGKILL

            return True

        except (ProcessLookupError, PermissionError, OSError):

            pass

        return False

    @staticmethod
    def cpu_count():
        """Obtém número de CPUs."""

        if PSUTIL_AVAILABLE:

            try:

                return psutil.cpu_count(logical=True)

            except (PermissionError, OSError):

                pass

        try:

            return os.cpu_count() or 1

        except BaseException:

            return 1


class FileManager:

    SERVER_LINKS_FILE = "Shako.dev/server-link.txt"

    ACCOUNTS_FILE = "Shako.dev/account.txt"

    CONFIG_FILE = "Shako.dev/config-wh.json"

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

            cursor.execute(
                "SELECT value FROM cookies WHERE name = '.ROBLOSECURITY'")

            result = cursor.fetchone()

            conn.close()

            if temp_path != file_path and os.path.exists(temp_path):

                try:

                    os.remove(temp_path)

                except BaseException:

                    pass

            if result:

                return result[0]

            return None

        except Exception as e:

            return None

    @staticmethod
    def setup_user_ids():

        print(
            "\033[1;32m[ Shako.dev ] - Auto-detecting User IDs from app packages...\033[0m")

        packages = RobloxManager.get_roblox_packages()

        accounts = []

        if not packages:

            print(
                "\033[1;31m[ Shako.dev ] - No Roblox packages detected to set up User IDs.\033[0m")

            return []

        for package_name in packages:

            file_path = f'/data/data/{package_name}/files/appData/LocalStorage/appStorage.json'

            try:

                user_id = FileManager.find_userid_from_file(file_path)

                if user_id and user_id != "-1":

                    accounts.append((package_name, user_id))

                    print(
                        f"\033[96m[ Shako.dev ] - Found UserID for {package_name}: {user_id}\033[0m")

                else:

                    print(
                        f"\033[1;31m[ Shako.dev ] - UserID not found for {package_name}.\033[0m")

            except Exception as e:

                print(
                    f"\033[1;31m[ Shako.dev ] - Error reading file for {package_name}: {e}\033[0m")

                Utilities.log_error(
                    f"Error reading appStorage.json for {package_name}: {e}")

        if accounts:

            FileManager.save_accounts(accounts)

            print(
                "\033[1;32m[ Shako.dev ] - User IDs have been successfully saved.\033[0m")

        else:

            print(
                "\033[1;31m[ Shako.dev ] - Could not find any valid User IDs to set up.\033[0m")

        return accounts

    @staticmethod
    def save_server_links(server_links):

        try:

            os.makedirs(
    os.path.dirname(
        FileManager.SERVER_LINKS_FILE),
         exist_ok=True)

            with open(FileManager.SERVER_LINKS_FILE, "w") as file:

                for package, link in server_links:

                    file.write(f"{package},{link}\n")

            print(
                "\033[1;32m[ Shako.dev ] - Server links saved successfully.\033[0m")

        except IOError as e:

            print(
                f"\033[1;31m[ Shako.dev ] - Error saving server links: {e}\033[0m")

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
    def save_accounts(accounts):

        with open(FileManager.ACCOUNTS_FILE, "w") as file:

            for package, user_id in accounts:

                file.write(f"{package},{user_id}\n")

    @staticmethod
    def load_accounts():

        accounts = []

        if os.path.exists(FileManager.ACCOUNTS_FILE):

            with open(FileManager.ACCOUNTS_FILE, "r") as file:

                for line in file:

                    line = line.strip()

                    if line:

                        try:

                            package, user_id = line.split(",", 1)

                            globals()["_user_"][package] = user_id

                            accounts.append((package, user_id))

                        except ValueError:

                            print(
                                f"\033[1;31m[ Shako.dev ] - Invalid line format: {line}. Expected format 'package,user_id'.\033[0m")

        return accounts

    @staticmethod
    def find_userid_from_file(file_path):

        try:

            cmd_cat = f"cat {file_path}"

            result = subprocess.run(
    cmd_cat, shell=True, capture_output=True, text=True)

            if result.returncode != 0:

                return None

            content = result.stdout

            userid_start = content.find('"UserId":"')

            if userid_start == -1:

                return None

            userid_start += len('"UserId":"')

            userid_end = content.find('"', userid_start)

            if userid_end == -1:

                return None

            userid = content[userid_start:userid_end]

            return userid

        except Exception as e:

            print(f"\033[1;31m[ Shako.dev ] - Error reading file: {e}\033[0m")

            return None

    @staticmethod
    def get_username(user_id):

        user = FileManager.load_saved_username(user_id)

        if user is not None:

            return user

        retry_attempts = 2

        for attempt in range(retry_attempts):

            try:

                url = f"https://users.roblox.com/v1/users/{user_id}"

                response = requests.get(url, timeout=10)

                response.raise_for_status()

                data = response.json()

                username = data.get("name", "Unknown")

                if username != "Unknown":

                    FileManager.save_username(user_id, username)

                    return username

            except requests.exceptions.RequestException as e:

                time.sleep(2 ** attempt)

        for attempt in range(retry_attempts):

            try:

                url = f"https://users.roproxy.com/v1/users/{user_id}"

                response = requests.get(url, timeout=10)

                response.raise_for_status()

                data = response.json()

                username = data.get("name", "Unknown")

                if username != "Unknown":

                    FileManager.save_username(user_id, username)

                    return username

            except requests.exceptions.RequestException as e:

                time.sleep(2 ** attempt)

        return "Unknown"

    @staticmethod
    def save_username(user_id, username):

        try:

            data = {}

            if os.path.exists("usernames.json"):

                try:

                    with open("usernames.json", "r") as file:

                        data = json.load(file)

                except json.JSONDecodeError:

                    data = {}

            data[user_id] = username

            with open("usernames.json", "w") as file:

                json.dump(data, file)

        except Exception as e:

            print(
                f"\033[1;31m[ Shako.dev ] - Error saving username: {e}\033[0m")

    @staticmethod
    def load_saved_username(user_id):

        try:

            if not os.path.exists("usernames.json"):

                return None

            with open("usernames.json", "r") as file:

                data = json.load(file)

                return data.get(str(user_id), None)

        except (FileNotFoundError, json.JSONDecodeError, IOError) as e:

            return None

    @staticmethod
    def download_file(url, destination, binary=False):

        try:

            response = requests.get(url, stream=True)

            if response.status_code == 200:

                mode = 'wb' if binary else 'w'

                encoding = 'utf-8' if not binary else None

                with open(destination, mode, encoding=encoding) as file:

                    if binary:

                        shutil.copyfileobj(response.raw, file)

                    else:

                        file.write(response.text)

                print(
                    f"\033[1;32m[ Shako.dev ] - {os.path.basename(destination)} downloaded successfully.\033[0m")

                return destination

            else:

                error_message = f"Failed to download {os.path.basename(destination)}. Status code: {response.status_code}"

                print(f"\033[1;31m[ Shako.dev ] - {error_message}\033[0m")

                Utilities.log_error(error_message)

                return None

        except Exception as e:

            error_message = f"Error while downloading {os.path.basename(destination)}: {e}"

            print(f"\033[1;31m[ Shako.dev ] - {error_message}\033[0m")

            Utilities.log_error(error_message)

            return None

    @staticmethod
    def _load_config():

        global webhook_url, device_name, webhook_interval, close_and_rejoin_delay, reset_tab_interval

        try:

            if os.path.exists(FileManager.CONFIG_FILE):

                with open(FileManager.CONFIG_FILE, "r") as file:

                    config = json.load(file)

                    webhook_url = config.get("webhook_url", None)

                    device_name = config.get("device_name", None)

                    webhook_interval = config.get("interval", float('inf'))

                    globals()["_disable_ui"] = config.get("disable_ui", "0")

                    globals()["check_exec_enable"] = config.get(
                        "check_executor", "1")

                    globals()["command_8_configured"] = config.get(
                        "command_8_configured", False)

                    globals()["lua_script_template"] = config.get(
                        "lua_script_template", None)

                    globals()["package_prefix"] = config.get(
                        "package_prefix", "com.roblox")

                    close_and_rejoin_delay = config.get(
                        "close_and_rejoin_delay", None)

                    reset_tab_interval = config.get("reset_tab_interval", None)

            else:

                webhook_url = None

                device_name = None

                webhook_interval = float('inf')

                globals()["_disable_ui"] = "0"

                globals()["check_exec_enable"] = "1"

                globals()["command_8_configured"] = False

                globals()["lua_script_template"] = None

                globals()["package_prefix"] = "com.roblox"

                close_and_rejoin_delay = None

                reset_tab_interval = None

        except Exception as e:

            print(
                f"\033[1;31m[ Shako.dev ] - Error loading configuration: {e}\033[0m")

            Utilities.log_error(f"Error loading configuration: {e}")

    @staticmethod
    def save_config():

        try:

            config = {
    "webhook_url": webhook_url,
    "device_name": device_name,
    "interval": webhook_interval,
    "disable_ui": globals().get(
        "_disable_ui",
        "0"),
        "check_executor": globals()["check_exec_enable"],
        "command_8_configured": globals().get(
            "command_8_configured",
            False),
            "lua_script_template": globals().get(
                "lua_script_template",
                None),
                "package_prefix": globals().get(
                    "package_prefix",
                    "com.roblox"),
                     }

            with open(FileManager.CONFIG_FILE, "w") as file:

                json.dump(config, file, indent=4, sort_keys=True)

            print(
                "\033[1;32m[ Shako.dev ] - Configuration saved successfully.\033[0m")

        except Exception as e:

            print(
                f"\033[1;31m[ Shako.dev ] - Error saving configuration: {e}\033[0m")

            Utilities.log_error(f"Error saving configuration: {e}")

    @staticmethod
    def check_and_create_cookie_file():

        folder_path = os.path.dirname(os.path.abspath(__file__))

        cookie_file_path = os.path.join(folder_path, 'cookie.txt')

        if not os.path.exists(cookie_file_path):

            with open(cookie_file_path, 'w') as f:

                f.write("")


class SystemMonitor:

    @staticmethod
    def capture_screenshot():

        screenshot_path = "/storage/emulated/0/Download/screenshot.png"

        try:

            os.system(f"/system/bin/screencap -p {screenshot_path}")

            if not os.path.exists(screenshot_path):

                raise FileNotFoundError("Screenshot file was not created.")

            return screenshot_path

        except Exception as e:

            print(
                f"\033[1;31m[ Shako.dev ] - Error capturing screenshot: {e}\033[0m")

            Utilities.log_error(f"Error capturing screenshot: {e}")

            return None

    @staticmethod
    def get_uptime():
        """Obtém uptime de forma segura, compatível com Termux."""

        try:

            # Método 1: Ler /proc/uptime diretamente (mais confiável no Termux)

            with open('/proc/uptime', 'r') as f:

                uptime_seconds = float(f.readline().split()[0])

        except (PermissionError, FileNotFoundError, OSError):

            # Fallback: usar boot_time calculado

            uptime_seconds = time.time() - system_boot_time

        days = int(uptime_seconds // (24 * 3600))

        hours = int((uptime_seconds % (24 * 3600)) // 3600)

        minutes = int((uptime_seconds % 3600) // 60)

        seconds = int(uptime_seconds % 60)

        return f"{days}d {hours}h {minutes}m {seconds}s"

    @staticmethod
    def get_pids_for_package(package_name):

        pids = []

        for proc in TermuxCompat.process_iter(['pid', 'name', 'cmdline']):

            try:

                if package_name in proc.info['name']:

                    pids.append(proc.info['pid'])

                    continue

                cmdline = proc.info.get('cmdline')

                if cmdline and any(package_name in s for s in cmdline):

                    pids.append(proc.info['pid'])

            except (AttributeError, KeyError):

                continue

        return list(set(pids))

    @staticmethod
    def roblox_processes():

        package_names = []

        package_namez = RobloxManager.get_roblox_packages()

        for proc in TermuxCompat.process_iter(
            ['name', 'pid', 'memory_info', 'cpu_percent']):

            try:

                proc_name = proc.info['name']

                for package_name in package_namez:

                    if package_name in proc_name or proc_name.lower(
                    ) == package_name[-15:].lower():

                        # Usar valores simplificados no Termux

                        mem_usage = 0

                        cpu_usage = 0

                        if PSUTIL_AVAILABLE:

                            try:

                                p = psutil.Process(proc.pid)

                                mem_usage = round(
                                    p.memory_info().rss / (1024 ** 2), 2)

                                cpu_usage = round(
    p.cpu_percent(
        interval=None) /
        TermuxCompat.cpu_count(),
         2)

                            except BaseException:

                                pass

                        full_name = package_name

                        package_names.append(
                            f"{full_name} (PID: {proc.pid}, CPU: {cpu_usage}%, MEM: {mem_usage}MB)")

                        break

            except (AttributeError, KeyError):

                continue

        return package_names

    @staticmethod
    def get_memory_usage():

        try:

            return round(TermuxCompat.get_process_memory(), 2)

        except Exception as e:

            print(
                f"\033[1;31m[ Shako.dev ] - Error getting memory usage: {e}\033[0m")

            Utilities.log_error(f"Error getting memory usage: {e}")

            return None

    @staticmethod
    def get_system_info():

        try:

            cpu_usage = TermuxCompat.get_cpu_percent(interval=1)

            memory_info = TermuxCompat.get_memory_info()

            system_info = {

                "cpu_usage": cpu_usage,

                "memory_total": round(memory_info.total / (1024 ** 3), 2),

                "memory_used": round(memory_info.used / (1024 ** 3), 2),

                "memory_percent": memory_info.percent,

                "uptime": SystemMonitor.get_uptime(),

                "roblox_packages": SystemMonitor.roblox_processes()

            }

            return system_info

        except Exception as e:

            print(
                f"\033[1;31m[ Shako.dev ] - Error retrieving system information: {e}\033[0m")

            Utilities.log_error(f"Error retrieving system information: {e}")

            return False


class UIManager:

    @staticmethod
    def print_header(version):

        console = Console()

        header = Text(r"""

      _           _                 _

  ___| |__   __ _| | _____       __| | _____   __

 / __| '_ \ / _` | |/ / _ \     / _` |/ _ \ \ / /

 \__ \ | | | (_| |   < (_) |   | (_| |  __/\ V /

 |___/_| |_|\__,_|_|\_\___(_)   \__,_|\___| \_/

        """, style="bold cyan")

        config_file = os.path.join("Shako.dev", "config.json")

        check_executor = "1"

        if os.path.exists(config_file):

            try:

                with open(config_file, "r") as f:

                    config = json.load(f)

                    check_executor = config.get("check_executor", "0")

            except Exception as e:

                console.print(
                    f"[bold red][ Shako.dev ] - Error reading {config_file}: {e}[/bold red]")

        console.print(header)

        console.print(
            f"[bold cyan]- Version: [/bold cyan][bold white]{version}[/bold white]")

        console.print(
            f"[bold cyan]- Credit: [/bold cyan][bold white]Shako.dev[/bold white]")

        if check_executor == "1":

            console.print(
                "[bold cyan]- Method: [/bold cyan][bold white]Check Executor[/bold white]")

        else:

            console.print(
                "[bold cyan]- Method: [/bold cyan][bold white]Check Online[/bold white]")

        console.print("\n")

    @staticmethod
    def create_dynamic_menu(options):

        console = Console()

        table = Table(

            header_style="bold white",

            border_style="bright_white",

            box=ROUNDED

        )

        table.add_column("No", justify="center", style="bold cyan", width=6)

        table.add_column("Service Name", style="bold magenta", justify="left")

        for i, service in enumerate(options, start=1):

            table.add_row(
    f"[bold cyan][ {i} ][/bold cyan]",
     f"[bold blue]{service}[/bold blue]")

        panel = Panel(
    table,
    title="[bold cyan]discord.gg/ghmaDgNzDa - Shako Edition[/bold cyan]",
    border_style="cyan",
     box=ROUNDED)

        console.print(Align.left(panel))

    @staticmethod
    def create_dynamic_table(headers, rows):

        table = PrettyTable(field_names=headers, border=True, align="l")

        for huy in rows:

            table.add_row(list(huy))

        print(table)

    last_update_time = 0

    update_interval = 5

    @staticmethod
    def update_status_table():

        current_time = time.time()

        if current_time - UIManager.last_update_time < UIManager.update_interval:

            return

        UIManager.last_update_time = current_time

        cpu_usage = TermuxCompat.get_cpu_percent(interval=None)

        memory_info = TermuxCompat.get_memory_info()

        ram = round(memory_info.used / memory_info.total *
                    100, 2) if memory_info.total > 0 else 0

        title = f"CPU: {cpu_usage}% | RAM: {ram}%"

        table_packages = PrettyTable(

            field_names=["Package", "Username", "Package Status"],

            title=title,

            border=True,

            align="l"

        )

        for package, info in globals().get("package_statuses", {}).items():

            username = str(info.get("Username", "Unknown"))

            if username != "Unknown":

                obfuscated_username = "******" + \
                    username[6:] if len(username) > 6 else "******"

                username = obfuscated_username

            table_packages.add_row([

                str(package),

                username,

                str(info.get("Status", "Unknown"))

            ])

        Utilities.clear_screen()

        UIManager.print_header(version)

        print(table_packages)


class RobloxManager:

    @staticmethod
    def get_cookie():

        try:

            current_dir = os.getcwd()

            cookie_txt_path = os.path.join(current_dir, "cookie.txt")

            new_dir_path = os.path.join(
    current_dir, "Shako.dev/Shako.dev - Data")

            new_cookie_path = os.path.join(new_dir_path, "cookie.txt")

            if not os.path.exists(new_dir_path):

                os.makedirs(new_dir_path)

            if not os.path.exists(cookie_txt_path):

                print(
                    "\033[1;31m[ Shako.dev ] - cookie.txt not found in the current directory!\033[0m")

                Utilities.log_error(
                    "cookie.txt not found in the current directory.")

                return False

            cookies = []

            org = []

            with open(cookie_txt_path, "r") as file:

                for line in file.readlines():

                    parts = str(line).strip().split(":")

                    if len(parts) == 4:

                        ck = ":".join(parts[2:])

                    else:

                        ck = str(line).strip()

                    if ck.startswith(
                        "_|WARNING:") or ".ROBLOSECURITY" in ck or len(ck) > 100:

                        org.append(str(line).strip())

                        cookies.append(ck)

            if len(cookies) == 0:

                print(
                    "\033[1;31m[ Shako.dev ] - No valid cookies found in cookie.txt. Please add cookies.\033[0m")

                Utilities.log_error("No valid cookies found in cookie.txt.")

                return False

            cookie = cookies.pop(0)

            original_line = org.pop(0)

            with open(new_cookie_path, "a") as new_file:

                new_file.write(original_line + "\n")

            with open(cookie_txt_path, "w") as file:

                file.write("\n".join(org))

            return cookie

        except Exception as e:

            print(f"\033[1;31m[ Shako.dev ] - Error: {e}\033[0m")

            Utilities.log_error(f"Error in get_cookie: {e}")

            return False

    @staticmethod
    def verify_cookie(cookie_value):

        try:

            headers = {

                'Cookie': f'.ROBLOSECURITY={cookie_value}',

                'User-Agent': 'Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Mobile Safari/537.36',

                'Referer': 'https://www.roblox.com/',

                'Origin': 'https://www.roblox.com',

            }

            time.sleep(1)

            response = requests.get(
    'https://users.roblox.com/v1/users/authenticated',
     headers=headers)

            if response.status_code == 200:

                print(
                    "\033[1;32m[ Shako.dev ] - Cookie is valid! User is authenticated.\033[0m")

                return response.json().get("id", False)

            elif response.status_code == 401:

                print(
                    "\033[1;31m[ Shako.dev ] - Invalid cookie. The user is not authenticated.\033[0m")

                return False

            else:

                error_message = f"Error verifying cookie: {response.status_code}"

                print(f"\033[1;31m[ Shako.dev ] - {error_message}\033[0m")

                return False

        except Exception as e:

            print(f"\033[1;31m[ Shako.dev ] - Error verify cookie: {e}\033[0m")

            return False

    @staticmethod
    def check_user_online(user_id, cookie=None):

        max_retries = 2

        delay = 2

        body = {"userIds": [user_id]}

        headers = {"Content-Type": "application/json"}

        if cookie is not None:

            headers["Cookie"] = f".ROBLOSECURITY={cookie}"

        for attempt in range(max_retries):

            try:

                with requests.Session() as session:

                    primary_response = session.post(
    "https://presence.roblox.com/v1/presence/users",
    headers=headers,
    json=body,
     timeout=7)

                primary_response.raise_for_status()

                primary_data = primary_response.json()

                primary_presence_type = primary_data["userPresences"][0]["userPresenceType"]

                return primary_presence_type

            except Exception:

                if attempt < max_retries - 1:

                    time.sleep(delay)

                    delay *= 2

        for attempt in range(max_retries):

            try:

                with requests.Session() as session:

                    primary_response = session.post(
    "https://presence.roproxy.com/v1/presence/users",
    headers=headers,
    json=body,
     timeout=7)

                primary_response.raise_for_status()

                primary_data = primary_response.json()

                primary_presence_type = primary_data["userPresences"][0]["userPresenceType"]

                return primary_presence_type

            except Exception:

                if attempt < max_retries - 1:

                    time.sleep(delay)

                    delay *= 2

                else:

                    return None


@staticmethod
   def get_roblox_packages():
        packages = []
        try:
            # Tenta listar pacotes com o comando padrão do Android
            cmd = "pm list packages"
            result = subprocess.run(
    cmd, shell=True, capture_output=True, text=True)

            # CORREÇÃO CRÍTICA: Só tenta o comando alternativo se o primeiro FALHAR (ou vier vazio)
            # Antes estava '== 0', o que causava o erro de sobrescrever o
            # resultado bom
            if result.returncode != 0 or not result.stdout.strip():
                result = subprocess.run(
    "/system/bin/pm list packages",
    shell=True,
    capture_output=True,
     text=True)

            package_prefix = globals().get("package_prefix", "com.roblox")

            if result.returncode == 0:
                for line in result.stdout.strip().splitlines():
                    if line.startswith("package:"):
                        name = line.replace("package:", "").strip()

                        # CORREÇÃO PARA VARIANTES (client, clienb, etc):
                        # Verifica se o prefixo bate OU se tem "roblox" em
                        # qualquer parte do nome
                        if (package_prefix in name) or (
                            "roblox" in name.lower()):
                            packages.append(name)
            else:
                print(
                    f"\033[1;31m[ Shako.dev ] - Failed to list packages (System Error).\033[0m")

        except Exception as e:
            print(
                f"\033[1;31m[ Shako.dev ] - Error retrieving packages: {e}\033[0m")

        unique_packages = sorted(list(set(packages)))

        if not unique_packages:
            print(
                f"\033[1;33m[ Shako.dev ] - Warning: No Roblox packages found. Check if they are installed.\033[0m")

        return unique_packages

    @staticmethod
    def kill_roblox_processes():

        packages = RobloxManager.get_roblox_packages()

        if not packages:

            print(
                "\033[1;32m[ Shako.dev ] - No Roblox packages found to kill.\033[0m")

            return


        print(
            f"\033[1;93m[ Shako.dev ] - Found {len(packages)} packages. Starting FAST clean kill for all...\033[0m")


        all_pids_to_kill = set()


        # Stage 1: Issue 'am force-stop' and collect all PIDs

        print(
            "\033[1;96m[ Shako.dev ] - Stage 1: Issuing 'am force-stop' for all packages...\033[0m")

        for package_name in packages:

            # Issue command

            subprocess.run(

                ["/system/bin/am", "force-stop", package_name],

                capture_output=True, text=True, check=False

            )

            # Collect PIDs

            try:

                pids = SystemMonitor.get_pids_for_package(package_name)

                if pids:

                    all_pids_to_kill.update(pids)

            except Exception as e:

                print(
                    f"\033[1;31m[ Shako.dev ] - Error getting PIDs for {package_name}: {e}\033[0m")


        # Short delay for 'am force-stop' commands to propagate

        time.sleep(0.25)


        # Stage 2: Kill all collected lingering PIDs

        if all_pids_to_kill:

            print(
                f"\033[1;93m[ Shako.dev ] - Stage 2: Found {len(all_pids_to_kill)} lingering PIDs. Sending SIGKILL...\033[0m")

            for pid in all_pids_to_kill:

                TermuxCompat.kill_process(pid)

        else:

            print(
                "\033[1;32m[ Shako.dev ] - Stage 2: No lingering PIDs found. 'am force-stop' was successful.\033[0m")


        print(
            "\033[1;32m[ Shako.dev ] - All Roblox processes have been issued kill commands.\033[0m")


    @staticmethod
    def kill_roblox_process(package_name):

        try:

            print(
                f"\033[1;96m[ Shako.dev ] - Sending 'am force-stop' for {package_name}...\033[0m")

            subprocess.run(

                ["/system/bin/am", "force-stop", package_name],

                capture_output=True, text=True, check=False

            )

            time.sleep(0.25)


            pids = SystemMonitor.get_pids_for_package(package_name)

            if pids:

                print(
                    f"\033[1;93m[ Shako.dev ] - Found lingering PIDs for {package_name}: {pids}. Sending SIGKILL...\033[0m")

                for pid in pids:

                    TermuxCompat.kill_process(pid)

            else:

                print(
                    f"\033[1;32m[ Shako.dev ] - No lingering PIDs found for {package_name}.\033[0m")


            print(
                f"\033[1;32m[ Shako.dev ] - Clean kill complete for {package_name}\033[0m")

            time.sleep(0.1)


        except Exception as e:

            print(
                f"\033[1;31m[ Shako.dev ] - Error during kill process for {package_name}: {e}\033[0m")

            Utilities.log_error(
                f"Error in kill_roblox_process for {package_name}: {e}\n{traceback.format_exc()}")


    @staticmethod
    def delete_cache_for_package(package_name):

        cache_paths = [

            f'/data/data/{package_name}/cache/',

            f'/data/data/{package_name}/code_cache/',

            f'/data/data/{package_name}/app_webview/gpu_cache/',

            f'/data/data/{package_name}/app_webview/Service Worker/',

            f'/data/data/{package_name}/app_webview/Web Storage/'

        ]

        cleared = False

        for path in cache_paths:

            if os.path.exists(path):

                subprocess.run(
                    ["rm", "-rf", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                cleared = True

        if cleared:

            print(
                f"\033[1;32m[ Shako.dev ] - Deep cache cleaned for {package_name} (Fix Update/Freeze)\033[0m")

        else:

            print(
                f"\033[1;93m[ Shako.dev ] - Cache already clean for {package_name}\033[0m")


    @staticmethod
    def launch_roblox(package_name, server_link):

        try:

            RobloxManager.kill_roblox_process(package_name)

            RobloxManager.delete_cache_for_package(package_name)


            with status_lock:

                user_id_val = globals()["_user_"].get(package_name, "Unknown")

                globals()["_uid_"][user_id_val] = time.time()

                if package_name in globals()["package_statuses"]:

                    globals()[
                            "package_statuses"][package_name]["Status"] = f"\033[1;36mJoining Game (Skip Home/Update) for {package_name}...\033[0m"

                    UIManager.update_status_table()


            print(
                f"\033[1;35m[ Shako.dev ] - Executing Direct Launch (Skip Home) for {package_name}...\033[0m")


            launch_cmd = [
    'am',
    'start',
    '-n',
    f'{package_name}/com.roblox.client.ActivityProtocolLaunch',
    '-a',
    'android.intent.action.VIEW',
    '-d',
    server_link,
    '-f',
     '0x14000000' ]


            subprocess.run(
    launch_cmd,
    stdout=subprocess.DEVNULL,
     stderr=subprocess.DEVNULL)

            time.sleep(12)


            with status_lock:

                if package_name in globals()["package_statuses"]:

                    globals()[
                            "package_statuses"][package_name]["Status"] = "\033[1;32mJoined Roblox (Direct Launch)\033[0m"

                    UIManager.update_status_table()


        except Exception as e:

            error_message = f"Error launching Roblox for {package_name}: {e}"

            with status_lock:

                if package_name in globals()["package_statuses"]:

                    globals()[
                            "package_statuses"][package_name]["Status"] = f"\033[1;31m{error_message}\033[0m"

                    UIManager.update_status_table()

            print(f"\033[1;31m[ Shako.dev ] - {error_message}\033[0m")

            Utilities.log_error(
                f"Error in launch_roblox for {package_name}: {e}\n{traceback.format_exc()}")


    @staticmethod
    def fix_permissions(path, package_name):

        try:

            cmd_get_owner = f"stat -c '%u:%g' /data/data/{package_name}"

            result = subprocess.run(
    cmd_get_owner,
    shell=True,
    capture_output=True,
     text=True)

            owner = result.stdout.strip()


            if owner:

                cmd_chown = f"chown -R {owner} {path}"

                subprocess.run(cmd_chown, shell=True)

                cmd_chmod = f"chmod 660 {path}"

                subprocess.run(cmd_chmod, shell=True)

                subprocess.run(
    f"restorecon {path}",
    shell=True,
    stdout=subprocess.DEVNULL,
     stderr=subprocess.DEVNULL)

                return True

        except Exception as e:

            print(
                f"\033[1;31mFailed to fix permissions for {path}: {e}\033[0m")

        return False


    @staticmethod
    def update_app_storage_userid(file_path, user_id):

        try:

            with open(file_path, 'r') as f:

                data = json.load(f)


            data['UserId'] = str(user_id)


            with open(file_path, 'w') as f:

                json.dump(data, f, indent=4)

            return True

        except Exception as e:

            print(
                f"\033[1;31mError updating appStorage.json UserID: {e}\033[0m")

            return False


    @staticmethod
    def inject_cookies_and_appstorage():

        RobloxManager.kill_roblox_processes()

        db_url = "https://raw.githubusercontent.com/ENMN11/Tool-Rejoin/refs/heads/main/Cookies"

        appstorage_url = "https://raw.githubusercontent.com/ENMN11/Tool-Rejoin/refs/heads/main/appStorage.json"


        downloaded_db_path = FileManager.download_file(
            db_url, "Cookies.db", binary=True)

        downloaded_appstorage_path = FileManager.download_file(
            appstorage_url, "appStorage.json", binary=False)


        if not downloaded_db_path or not downloaded_appstorage_path:

            print(
                "\033[1;31m[ Shako.dev ] - Failed to download necessary files. Exiting.\033[0m")

            return


        packages = RobloxManager.get_roblox_packages()

        if not packages:

            print("\033[1;31m[ Shako.dev ] - No Roblox packages detected.\033[0m")

            return


        for package_name in packages:

            try:

                cookie = RobloxManager.get_cookie()

                if not cookie:

                    print(
                        f"\033[1;31m[ Shako.dev ] - Failed to retrieve a cookie for {package_name}. Skipping...\033[0m")

                    break


                user_id = RobloxManager.verify_cookie(cookie)

                if user_id:

                    print(
                        f"\033[1;32m[ Shako.dev ] - Cookie for {package_name} is valid! User ID: {user_id}\033[0m")

                else:

                    print(
                        f"\033[1;31m[ Shako.dev ] - Cookie for {package_name} is invalid. Skipping injection...\033[0m")

                    continue


                print(
                    f"\033[1;32m[ Shako.dev ] - Injecting cookie for {package_name}...\033[0m")


                destination_db_dir = f"/data/data/{package_name}/app_webview/Default/"

                destination_appstorage_dir = f"/data/data/{package_name}/files/appData/LocalStorage/"


                subprocess.run(f"mkdir -p {destination_db_dir}", shell=True)

                subprocess.run(
    f"mkdir -p {destination_appstorage_dir}",
     shell=True)


                destination_db_path = os.path.join(
                    destination_db_dir, "Cookies")

                destination_appstorage_path = os.path.join(
                    destination_appstorage_dir, "appStorage.json")


                RobloxManager.update_app_storage_userid(
                    downloaded_appstorage_path, user_id)

                shutil.copyfile(
    downloaded_appstorage_path,
     destination_appstorage_path)


                shutil.copyfile(downloaded_db_path, destination_db_path)

                RobloxManager.replace_cookie_value_in_db(
                    destination_db_path, cookie)


                print(
                    f"\033[1;33m[ Shako.dev ] - Fixing permissions for {package_name}...\033[0m")

                RobloxManager.fix_permissions(
                    destination_db_path, package_name)

                RobloxManager.fix_permissions(
    destination_appstorage_path, package_name)


                print(
                    f"\033[1;36m[ Shako.dev ] - Launching {package_name} to check login...\033[0m")

                subprocess.run(
    f"monkey -p {package_name} -c android.intent.category.LAUNCHER 1",
    shell=True,
    stdout=subprocess.DEVNULL,
     stderr=subprocess.DEVNULL)

                time.sleep(5)


            except Exception as e:

                error_message = f"Error injecting cookie for {package_name}: {e}"

                print(f"\033[1;31m[ Shako.dev ] - {error_message}\033[0m")

                traceback.print_exc()


        print("\033[1;33m[ Shako.dev ] - Injection & Auto Launch done.\033[0m")


    @staticmethod
    def replace_cookie_value_in_db(db_path, new_cookie_value):

        try:

            conn = sqlite3.connect(db_path)

            cursor = conn.cursor()

            cursor.execute("UPDATE cookies SET value = ?, last_access_utc = ?, expires_utc = ? WHERE host_key = '.roblox.com' AND name = '.ROBLOSECURITY'",
                           (new_cookie_value, int(time.time() + 11644473600) * 1000000, int(time.time() + 11644473600 + 31536000) * 1000000))

            if cursor.rowcount == 0:

                print(
                    "\033[1;33mWarning: Cookie row not found, attempting insert...\033[0m")

            conn.commit()

            conn.close()

            print(
                "\033[1;32mCookie value replaced successfully in the database!\033[0m")

        except Exception as e:

            print(
                f"\033[1;31mError replacing cookie value in database: {e}\033[0m")


    @staticmethod
    def format_server_link(input_link):

        if 'roblox.com' in input_link:

            return input_link

        elif input_link.isdigit():

            return f'roblox://placeID={input_link}'

        else:

            print(
                "\033[1;31m[ Shako.dev ] - Invalid input! Please enter a valid game ID or private server link.\033[0m")

            return None


class ExecutorManager:

    @staticmethod
    def detect_executors():

        console = Console()

        detected_executors = []


        for executor_name, base_path in executors.items():

            possible_autoexec_paths = [

                os.path.join(base_path, "Autoexec"),

                os.path.join(base_path, "Autoexecute"),

                os.path.join(base_path, "autoexec")

            ]


            for path in possible_autoexec_paths:

                if os.path.exists(path):

                    detected_executors.append(executor_name)

                    console.print(
                        f"[bold green][ Shako.dev ] - Detected executor: {executor_name}[/bold green]")

                    break


        return detected_executors


    @staticmethod
    def write_lua_script(detected_executors):

        console = Console()

        config_file = os.path.join("Shako.dev", "checkui.lua")


        if not os.path.exists(config_file):

            with open(config_file, "w") as f:

                f.write(globals()["lua_script_template"] or "")


        try:

            with open(config_file, "r") as f:

                lua_script_content = f.read()

        except Exception as e:

            console.print(
                f"[bold red][ Shako.dev ] - Error reading config from {config_file}: {e}[/bold red]")

            return


        for executor_name in detected_executors:

            base_path = executors[executor_name]

            possible_autoexec_paths = [

                os.path.join(base_path, "Autoexec"),

                os.path.join(base_path, "Autoexecute"),

                os.path.join(base_path, "autoexec")

            ]


            lua_written = False

            if executor_name.upper() == "KRNL":

                pass


            if not lua_written:

                for path in possible_autoexec_paths:

                    if os.path.exists(path):

                        lua_script_path = os.path.join(
                            path, "executor_check.lua")

                        try:

                            with open(lua_script_path, 'w') as file:

                                file.write(lua_script_content)

                                lua_written = True

                                console.print(
                                    f"[bold green][ Shako.dev ] - Lua script written to: {lua_script_path}[/bold green]")

                                break

                        except Exception as e:

                            console.print(
                                f"[bold red][ Shako.dev ] - Error writing Lua script to {lua_script_path}: {e}[/bold red]")


            if not lua_written:

                console.print(
                    f"[bold yellow][ Shako.dev ] - No valid path found to write Lua script for {executor_name}[/bold yellow]")


    @staticmethod
    def check_executor_status(
    package_name,
    continuous=True,
     max_wait_time=240):

        retry_timeout = time.time() + max_wait_time

        while True:

            for workspace in globals()["workspace_paths"]:

                id = globals()["_user_"][package_name]

                file_path = os.path.join(workspace, f"{id}.main")

                if os.path.exists(file_path):

                    return True

            if continuous and time.time() > retry_timeout:

                return False

            time.sleep(10)


    @staticmethod
    def reset_executor_file(package_name):

        try:

            for workspace in globals()["workspace_paths"]:

                id = globals()["_user_"][package_name]

                file_path = os.path.join(workspace, f"{id}.main")

                if os.path.exists(file_path):

                    os.remove(file_path)

        except BaseException:

            pass


class WebhookManager:

    @staticmethod
    def start_webhook_thread():

        global webhook_thread, stop_webhook_thread

        if (webhook_thread is None or not webhook_thread.is_alive()
            ) and not stop_webhook_thread:

            stop_webhook_thread = False

            webhook_thread = threading.Thread(
                target=WebhookManager.send_webhook)

            webhook_thread.start()


    @staticmethod
    def send_webhook():

        global stop_webhook_thread

        while not stop_webhook_thread:

            try:

                screenshot_path = SystemMonitor.capture_screenshot()

                if not screenshot_path:

                    time.sleep(60)

                    continue


                info = SystemMonitor.get_system_info()

                if not info:

                    time.sleep(60)

                    continue


                cpu = f"{info['cpu_usage']:.1f}%"

                mem_used = f"{info['memory_used']:.2f} GB"

                mem_total = f"{info['memory_total']:.2f} GB"

                mem_percent = f"{info['memory_percent']:.1f}%"

                uptime = info['uptime']

                roblox_count = len(info['roblox_packages'])

                roblox_status = f"Running: {roblox_count} instance{'s' if roblox_count != 1 else ''}"

                roblox_details = "\n".join(
    info['roblox_packages']) if info['roblox_packages'] else "None"


                tool_mem_usage = SystemMonitor.get_memory_usage()

                tool_mem_display = f"{tool_mem_usage} MB" if tool_mem_usage is not None else "Unavailable"


                if roblox_count > 0:

                    status_text = f"🟢 Online"

                else:

                    status_text = "🔴 Offline"


                random_color = random.randint(0, 16777215)


                embed = {

                    "color": random_color,

                    "title": "📈 System Status Monitor",

                    "description": f"Real-time report for **{device_name}**",

                    "fields": [

                        {"name": "🏷️ Device", "value": f"```{device_name}```", "inline": True},

                        {"name": "💾 Total Memory", "value": f"```{mem_total}```", "inline": True},

                        {"name": "⏰ Uptime", "value": f"```{uptime}```", "inline": True},

                        {"name": "⚡ CPU Usage", "value": f"```{cpu}```", "inline": True},

                        {"name": "📊 Memory Usage", "value": f"```{mem_used} ({mem_percent})```", "inline": True},

                        {"name": "🛠️ Tool Memory Usage", "value": f"```{tool_mem_display}```", "inline": True},

                        {"name": "🎮 Total Roblox Processes", "value": f"```{roblox_status}```", "inline": True},

                        {"name": "🔍 Roblox Details", "value": f"```{roblox_details}```", "inline": False},

                        {"name": "✅ Status", "value": f"```{status_text}```", "inline": True}

                    ],

                    "thumbnail": {"url": "https://i.imgur.com/5yXNxU4.png"},

                    "image": {"url": "attachment://screenshot.png"},

                    "footer": {"text": f"Made with 💖 by Shako.dev | Join us at discord.gg/rokidmanager",

                               "icon_url": "https://i.imgur.com/5yXNxU4.png"},

                    "timestamp": datetime.now(timezone.utc).isoformat(),

                    "author": {"name": "Shako.dev",

                               "url": "https://discord.gg/rokidmanager",

                               "icon_url": "https://i.imgur.com/5yXNxU4.png"}

                }


                with open(screenshot_path, "rb") as file:

                    response = requests.post(
    webhook_url,
    data={
        "payload_json": json.dumps(
            {
                "embeds": [embed],
                "username": "Shako.dev",
                "avatar_url": "https://i.imgur.com/5yXNxU4.png"})},
                files={
                    "file": (
                        "screenshot.png",
                         file)} )


                if response.status_code not in (200, 204):

                    print(
                        f"\033[1;31m[ Shako.dev ] - Error sending device info: {response.status_code}\033[0m")

                    Utilities.log_error(
                        f"Error sending webhook: Status code {response.status_code}")


            except Exception as e:

                print(f"\033[1;31m[ Shako.dev ] - Webhook error: {e}\033[0m")

                Utilities.log_error(f"Error in webhook thread: {e}")


            time.sleep(webhook_interval * 60)


    @staticmethod
    def stop_webhook():

        global stop_webhook_thread

        stop_webhook_thread = True


    @staticmethod
    def setup_webhook():

        global webhook_url, device_name, webhook_interval, stop_webhook_thread

        try:

            stop_webhook_thread = True

            webhook_url = input(
                "\033[1;35m[ Shako.dev ] - Enter your Webhook URL: \033[0m")

            device_name = input(
                "\033[1;35m[ Shako.dev ] - Enter your device name: \033[0m")

            webhook_interval = int(input(
                "\033[1;35m[ Shako.dev ] - Enter the interval to send Webhook (minutes): \033[0m"))

            FileManager.save_config()

            stop_webhook_thread = False

            threading.Thread(target=WebhookManager.send_webhook).start()

        except Exception as e:

            print(
                f"\033[1;31m[ Shako.dev ] - Error during webhook setup: {e}\033[0m")

            Utilities.log_error(f"Error during webhook setup: {e}")


class PackageMonitor:

    def __init__(self, package_name, server_link, user_id):

        self.package_name = package_name

        self.server_link = server_link

        self.user_id = user_id


        self.stop_event = Event()

        self.ready_event = Event()

        self.thread = None


        self.last_seen_time = time.time()

        self.is_first_load = True


    def start(self):

        if self.thread is None or not self.thread.is_alive():

            self.stop_event.clear()

            self.ready_event.clear()

            self.last_seen_time = time.time()

            self.is_first_load = True


            ExecutorManager.reset_executor_file(self.package_name)


            self.thread = threading.Thread(
    target=self._monitor_loop, daemon=True)

            self.thread.start()

            print(
                f"\033[1;35m[ Shako.dev ] - Monitor thread started for {self.package_name}\033[0m")


    def stop(self):

        self.stop_event.set()

        if self.thread and self.thread.is_alive():

            self.thread.join(timeout=5)

        print(
            f"\033[1;31m[ Shako.dev ] - Monitor thread stopped for {self.package_name}\033[0m")


    def wait_for_ready(self, timeout=240):

        print(
            f"\033[1;33m[ Shako.dev ] - Waiting for executor signal from {self.package_name} (Timeout: {timeout}s)...\033[0m")

        with status_lock:

            if self.package_name in globals()["package_statuses"]:

                globals()[
                        "package_statuses"][self.package_name]["Status"] = "\033[1;33mWaiting for Executor...\033[0m"

                UIManager.update_status_table()


        if not self.ready_event.wait(timeout=timeout):

            print(
                f"\033[1;31m[ Shako.dev ] - Timeout waiting for executor on {self.package_name}!\033[0m")

            with status_lock:

                if self.package_name in globals()["package_statuses"]:

                    globals()[
                            "package_statuses"][self.package_name]["Status"] = "\033[1;31mExecutor Timeout!\033[0m"

                    UIManager.update_status_table()

            return False


        print(
            f"\033[1;32m[ Shako.dev ] - Executor signal RECEIVED from {self.package_name}.\033[0m")

        return True


    def _monitor_loop(self):

        while not self.stop_event.is_set():

            try:

                file_found = False


                for workspace in globals()["workspace_paths"]:

                    check_path = os.path.join(
    workspace, f"{self.user_id}.main")

                    if os.path.exists(check_path):

                        file_found = True

                        try:

                            os.remove(check_path)

                        except BaseException:

                            pass

                        break


                current_time = time.time()


                if file_found:

                    if self.is_first_load:

                        self.ready_event.set()

                        self.is_first_load = False


                    self.last_seen_time = current_time


                    msg = "\033[1;32mExecutor Active (Monitoring)\033[0m"

                    with status_lock:

                        if self.package_name in globals()["package_statuses"] and globals()[
                                                        "package_statuses"][self.package_name]["Status"] != msg:

                            globals()[
                                    "package_statuses"][self.package_name]["Status"] = msg

                            UIManager.update_status_table()


                    self.stop_event.wait(20)


                else:

                    elapsed_time = current_time - self.last_seen_time


                    if elapsed_time > 240:

                        print(
                            f"\033[1;31m[ Shako.dev ] - {self.package_name}: Executor crash detected (No signal for 240s). Restarting...\033[0m")


                        with status_lock:

                            if self.package_name in globals()[
                                                            "package_statuses"]:

                                globals()[
                                        "package_statuses"][self.package_name]["Status"] = "\033[1;31mCrash Detected -> Restarting...\033[0m"

                                UIManager.update_status_table()


                        with rejoin_lock:

                            if self.stop_event.is_set():

                                break


                            RobloxManager.kill_roblox_process(
                                self.package_name)

                            RobloxManager.delete_cache_for_package(
                                self.package_name)

                            time.sleep(5)


                            ExecutorManager.reset_executor_file(
                                self.package_name)


                            print(
                                f"\033[1;33m[ Shako.dev ] - Re-launching {self.package_name}...\033[0m")

                            RobloxManager.launch_roblox(
                                self.package_name, self.server_link)


                            self.last_seen_time = time.time()

                            self.is_first_load = True


                    else:

                        status_msg = f"\033[1;33mNo signal: {int(elapsed_time)}s/240s\033[0m"

                        if not self.is_first_load:

                            status_msg = f"\033[1;33mExecutor Idle/Crash? {int(elapsed_time)}s/240s\033[0m"


                        with status_lock:

                            if self.package_name in globals()[
                                                            "package_statuses"]:

                                globals()[
                                        "package_statuses"][self.package_name]["Status"] = status_msg

                                UIManager.update_status_table()


                        self.stop_event.wait(10)


            except Exception as e:

                print(
                    f"\033[1;31m[ Shako.dev ] - Error in monitor loop for {self.package_name}: {e}\033[0m")

                Utilities.log_error(
                    f"Error in monitor loop for {self.package_name}: {e}\n{traceback.format_exc()}")

                self.stop_event.wait(10)


        print(
            f"\033[1;31m[ Shako.dev ] - Monitor loop for {self.package_name} terminated.\033[0m")


class Runner:

    @staticmethod
    def launch_package_sequentially(
    server_links,
    package_monitors,
     main_stop_event):

        packages_to_launch = []

        for package_name, server_link in server_links:

            user_id = globals()["_user_"].get(package_name, "Unknown")

            if user_id == "Unknown":

                print(
                    f"\033[1;31m[ Shako.dev ] - No UserID found for {package_name}, skipping...\033[0m")

                continue

            username = FileManager.get_username(user_id)

            with status_lock:

                globals()["package_statuses"][package_name] = {

                    "Username": username,

                    "Status": "\033[1;33mWaiting to Join\033[0m"

                }

            packages_to_launch.append((package_name, server_link, user_id))


        total_packages = len(packages_to_launch)

        for index, (package_name, server_link,
                    user_id) in enumerate(packages_to_launch):


            if main_stop_event.is_set():

                print(
                    "\033[1;31m[ Shako.dev ] - Main stop event triggered. Aborting launch sequence.\033[0m")

                break


            with rejoin_lock:

                print(
                    f"\033[1;32m[ Shako.dev ] - Launching package {index + 1}/{total_packages}: {package_name}\033[0m")


                try:

                    RobloxManager.launch_roblox(package_name, server_link)


                    if globals()["check_exec_enable"] == "1":

                        if package_name in package_monitors:

                            package_monitors[package_name].stop()


                        detected_executors = ExecutorManager.detect_executors()

                        if not detected_executors:

                            print(
                                f"\033[1;41m[ Shako.dev ] - NO EXECUTOR DETECTED FOR {package_name}! EXITING TOOL.\033[0m")

                            globals()[
                                    "package_statuses"][package_name]["Status"] = "\033[1;31mNO EXECUTOR - EXITING\033[0m"

                            UIManager.update_status_table()

                            RobloxManager.kill_roblox_processes()

                            os._exit(1)

                        else:

                            ExecutorManager.write_lua_script(
                                detected_executors)


                        monitor = PackageMonitor(
    package_name, server_link, user_id)

                        package_monitors[package_name] = monitor

                        monitor.start()


                        if not monitor.wait_for_ready():

                            print(
                                f"\033[1;31m[ Shako.dev ] - Executor for {package_name} failed to load. Check logs. Continuing to next package...\033[0m")


                        time.sleep(5)


                    else:

                        time.sleep(10)


                except Exception as e:

                    print(
                        f"\033[1;31mError launching Roblox for {package_name}: {e}\033[0m")

                    globals()[
                            "package_statuses"][package_name]["Status"] = "\033[1;31mLaunch failed\033[0m"

                    UIManager.update_status_table()

                    Utilities.log_error(
                        f"Error in launch_package_sequentially for {package_name}: {e}\n{traceback.format_exc()}")


    @staticmethod
    def monitor_presence(server_links, stop_event):

        if globals()["check_exec_enable"] == "1":

            return


        in_game_status = {
    package_name: False for package_name,
     _ in server_links}


        while not stop_event.is_set():

            try:

                for package_name, server_link in server_links:

                    if stop_event.is_set():

                        break


                    ckhuy = FileManager.xuat(
                        f"/data/data/{package_name}/app_webview/Default/Cookies")

                    user_id = globals()["_user_"][package_name]


                    presence_type = RobloxManager.check_user_online(
                        user_id, ckhuy)


                    if presence_type != 2:

                        with status_lock:

                            globals()[
                                    "package_statuses"][package_name]["Status"] = "\033[1;31mOffline Detected. Rejoining...\033[0m"

                            UIManager.update_status_table()


                        with rejoin_lock:

                            if stop_event.is_set():
                                break

                            RobloxManager.kill_roblox_process(package_name)

                            RobloxManager.delete_cache_for_package(
                                package_name)

                            time.sleep(2)

                            RobloxManager.launch_roblox(
                                package_name, server_link)

                    else:

                        with status_lock:

                            globals()[
                                    "package_statuses"][package_name]["Status"] = "\033[1;32mIn-Game (Online Check)\033[0m"

                            UIManager.update_status_table()


                stop_event.wait(240)

            except Exception as e:

                print(
                    f"\033[1;31m[ Shako.dev ] - Error in presence monitor: {e}\033[0m")

                Utilities.log_error(
                    f"Error in presence monitor: {e}\n{traceback.format_exc()}")

                stop_event.wait(240)


        print("\033[1;31m[ Shako.dev ] - Presence monitor terminated.\033[0m")


    @staticmethod
    def force_rejoin(server_links, interval, stop_event, package_monitors):

        start_time = time.time()

        force_rejoin_interval = float(interval) if interval and isinstance(
            interval, (int, float)) else float('inf')


        while not stop_event.is_set():

            current_time = time.time()

            if force_rejoin_interval != float('inf') and (
    current_time - start_time >= force_rejoin_interval):

                print(
                    "\033[1;31m[ Shako.dev ] - Force killing Roblox processes due to time limit.\033[0m")



                with rejoin_lock:

                    print(
                        "\033[1;31m[ Shako.dev ] - Stopping all package monitors for force rejoin...\033[0m")

                    for monitor in package_monitors.values():

                        monitor.stop()

                    package_monitors.clear()


                    RobloxManager.kill_roblox_processes()

                    start_time = time.time()

                    print(
                        "\033[1;33m[ Shako.dev ] - Waiting before starting the rejoin process...\033[0m")

                    time.sleep(5)


                    Runner.launch_package_sequentially(
    server_links, package_monitors, stop_event)


            wait_time = max(
                0, min(600, force_rejoin_interval - (time.time() - start_time)))

            if force_rejoin_interval == float('inf'):

                wait_time = 600


            stop_event.wait(wait_time)


        print("\033[1;31m[ Shako.dev ] - Force rejoin monitor terminated.\033[0m")


    @staticmethod
    def update_status_table_periodically():

        while True:

            UIManager.update_status_table()

            time.sleep(30)


    @staticmethod
    def logout_all_packages():

        print("\033[1;32m[ Shako.dev ] - Scanning packages to Log Out...\033[0m")

        packages = RobloxManager.get_roblox_packages()


        if not packages:

            print("\033[1;31m[ Shako.dev ] - No Roblox packages found!\033[0m")

            return


        print(
            f"\033[1;33m[ Shako.dev ] - Found {len(packages)} packages. Cleaning data...\033[0m")


        for package_name in packages:

            try:

                RobloxManager.kill_roblox_process(package_name)


                cookie_path = f"/data/data/{package_name}/app_webview/Default/Cookies"

                cookie_journal = f"/data/data/{package_name}/app_webview/Default/Cookies-journal"

                app_storage_path = f"/data/data/{package_name}/files/appData/LocalStorage/appStorage.json"


                subprocess.run(

                    ["rm", "-f", cookie_path, cookie_journal, app_storage_path],

                    stdout=subprocess.DEVNULL,

                    stderr=subprocess.DEVNULL

                )


                print(
                    f"\033[1;32m[ Shako.dev ] - Logged out {package_name} (Deleted Cookies & appStorage)\033[0m")


            except Exception as e:

                print(
                    f"\033[1;31m[ Shako.dev ] - Error logging out {package_name}: {e}\033[0m")


        print("\033[1;33m[ Shako.dev ] - Logout Process Completed.\033[0m")


def check_activation_status():

    return True


def set_android_id(android_id):

    try:

        subprocess.run(["settings", "put", "secure",
                       "android_id", android_id], check=True)

    except Exception as e:

        Utilities.log_error(f"Failed to set Android ID: {e}")


def auto_change_android_id():

    global auto_android_id_enabled, auto_android_id_value

    while auto_android_id_enabled:

        if auto_android_id_value:

            set_android_id(auto_android_id_value)

        time.sleep(2)


def main():

    global stop_webhook_thread, webhook_interval

    global auto_android_id_enabled, auto_android_id_thread, auto_android_id_value


    if not check_activation_status():

        return


    FileManager._load_config()


    if not globals().get("command_8_configured", False):

        globals()["check_exec_enable"] = "1"

        globals()["lua_script_template"] = 'if not game:IsLoaded() then game.Loaded:Wait() end local f = tostring(game.Players.LocalPlayer.UserId)..".main" local c = "https://discord.gg/FcEGmkNDDe" local function w() local g = pcall(writefile, f, c) if not g then game:GetService("TeleportService"):Teleport(game.PlaceId, game.Players.LocalPlayer) end end task.spawn(function() w() while true do task.wait(5) w() end end)'

        config_file = os.path.join("Shako.dev", "checkui.lua")

        try:

            os.makedirs("Shako.dev", exist_ok=True)

            with open(config_file, "w") as f:

                f.write(globals()["lua_script_template"])

        except Exception as e:

            print(f"\033[1;31mError: {e}\033[0m")

        FileManager.save_config()


    if webhook_interval is None:

        webhook_interval = float('inf')

    if webhook_url and device_name and webhook_interval != float('inf'):

        WebhookManager.start_webhook_thread()


    monitoring_threads = []

    main_stop_event = threading.Event()

    package_monitors = {}


    while True:

        Utilities.clear_screen()

        UIManager.print_header(version)

        FileManager.check_and_create_cookie_file()


        menu_options = [

            "Start Auto Rejoin (Auto setup User ID)",

            "Setup Game ID for Packages",

            "Auto Login with Cookie",

            "Enable Discord Webhook",

            "Auto Check User Setup",

            "Configure Package Prefix",

            "Auto Change Android ID",

            "Launch All Packages to Main Menu",

            "Log Out All Packages"

        ]


        UIManager.create_dynamic_menu(menu_options)

        setup_type = input("\033[1;93m[ Shako.dev ] - Enter command: \033[0m")


        if setup_type == "1":

            try:

                print(
                    "\033[1;33m[ Shako.dev ] - Stopping all existing monitoring tasks...\033[0m")

                main_stop_event.set()

                for t in monitoring_threads:

                    t.join(timeout=5)

                monitoring_threads.clear()


                for monitor in package_monitors.values():

                    monitor.stop()

                package_monitors.clear()

                print("\033[1;32m[ Shako.dev ] - All tasks stopped.\033[0m")


                main_stop_event.clear()


                FileManager.setup_user_ids()

                globals()["accounts"] = FileManager.load_accounts()


                if not globals()["accounts"]:

                    print(
                        "\033[1;31m[ Shako.dev ] - No User IDs were found.\033[0m")

                    input("\033[1;32mPress Enter to return...\033[0m")

                    continue


                server_links = FileManager.load_server_links()

                globals()["_uid_"] = {}


                if not server_links:

                    print(
                        "\033[1;31m[ Shako.dev ] - No game ID link set up.\033[0m")

                    input("\033[1;32mPress Enter to return...\033[0m")

                    continue


                force_rejoin_input = input(
                    "\033[1;93m[ Shako.dev ] - Force rejoin interval (minutes, 'q' to skip): \033[0m")

                force_rejoin_interval = float('inf') if force_rejoin_input.lower(
                ) == 'q' else int(force_rejoin_input) * 60


                RobloxManager.kill_roblox_processes()

                time.sleep(3)


                print(
                    "\033[1;32m[ Shako.dev ] - Starting background monitoring services...\033[0m")


                tasks_to_start = [
    (Runner.monitor_presence,
    (server_links,
    main_stop_event)),
    (Runner.force_rejoin,
    (server_links,
    force_rejoin_interval,
    main_stop_event,
    package_monitors)),
    (Runner.update_status_table_periodically,
     ()) ]


                for target_func, args in tasks_to_start:

                    t = threading.Thread(
    target=target_func, args=args, daemon=True)

                    t.start()

                    if target_func != Runner.update_status_table_periodically:

                        monitoring_threads.append(t)


                Runner.launch_package_sequentially(
    server_links, package_monitors, main_stop_event)

                globals()["is_runner_ez"] = True


                print(
                    "\033[1;32m[ Shako.dev ] - All initial launches complete. Continuous monitoring is now active.\033[0m")


                while not main_stop_event.is_set():

                    time.sleep(10)

                    Utilities.collect_garbage()


                print(
                    "\033[1;31m[ Shako.dev ] - Monitoring has been stopped. Returning to main menu.\033[0m")


            except Exception as e:

                print(f"\033[1;31m[ Shako.dev ] - Error: {e}\033[0m")

                Utilities.log_error(
                    f"Error in main loop (1): {e}\n{traceback.format_exc()}")

                input("\033[1;32mPress Enter to return...\033[0m")

                continue


        elif setup_type == "2":

            try:

                print(
                    "\033[1;32m[ Shako.dev ] - Auto Setup User IDs from appStorage.json...\033[0m")

                packages = RobloxManager.get_roblox_packages()

                accounts = []


                for package_name in packages:

                    file_path = f'/data/data/{package_name}/files/appData/LocalStorage/appStorage.json'

                    try:

                        user_id = FileManager.find_userid_from_file(file_path)

                        if user_id and user_id != "-1":

                            accounts.append((package_name, user_id))

                            print(
                                f"\033[96m[ Shako.dev ] - Found UserId for {package_name}: {user_id}\033[0m")

                        else:

                            print(
                                f"\033[1;31m[ Shako.dev ] - UserId not found for {package_name}.\033[0m")

                    except Exception as e:

                        print(
                            f"\033[1;31m[ Shako.dev ] - Error reading file for {package_name}: {e}\033[0m")

                        Utilities.log_error(
                            f"Error reading appStorage.json for {package_name}: {e}")


                if accounts:

                    FileManager.save_accounts(accounts)

                    print("\033[1;32m[ Shako.dev ] - User IDs saved!\033[0m")

                else:

                    print("\033[1;31m[ Shako.dev ] - No User IDs found.\033[0m")

                    input("\033[1;32mPress Enter to return...\033[0m")

                    continue


                print("\033[93m[ Shako.dev ] - Select game:\033[0m")

                games = [
    "1. Blox Fruits",
    "2. Grow A Garden",
    "3. King Legacy",
    "4. Fisch",
    "5. Bee Swarm Simulator",
    "6. Anime Last Stand",
    "7. Dead Rails Alpha",
    "8. All Star Tower Defense X",
    "9. 99 Nights In The Forest",
    "10. Murder Mystery 2",
    "11. Steal A Brainrot",
    "12. Blue Lock Rivals",
    "13. Arise Crossover",
     "14. Other game or Private Server Link" ]

                for game in games:

                    print(f"\033[96m{game}\033[0m")


                choice = input(
                    "\033[93m[ Shako.dev ] - Enter choice: \033[0m").strip()

                game_ids = {
    "1": "2753915549",
    "2": "126884695634066",
    "3": "4520749081",
    "4": "16732694052",
    "5": "1537690962",
    "6": "12886143095",
    "7": "116495829188952",
    "8": "17687504411",
    "9": "79546208627805",
    "10": "142823291",
    "11": "109983668079237",
    "12": "18668065416",
     "13": "87039211657390" }


                if choice in game_ids:

                    server_link = game_ids[choice]

                elif choice == "14":

                    server_link = input(
                        "\033[93m[ Shako.dev ] - Enter game ID or private server link: \033[0m")

                else:

                    print("\033[1;31m[ Shako.dev ] - Invalid choice.\033[0m")

                    input("\033[1;32mPress Enter to return...\033[0m")

                    continue


                formatted_link = RobloxManager.format_server_link(server_link)

                if formatted_link:

                    server_links = [(package_name, formatted_link)
                                     for package_name, _ in accounts]

                    FileManager.save_server_links(server_links)

                else:

                    print(
                        "\033[1;31m[ Shako.dev ] - Invalid server link.\033[0m")


            except Exception as e:

                print(f"\033[1;31m[ Shako.dev ] - Error: {e}\033[0m")

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

                print(
                    "\033[1;35m[1]\033[1;32m Executor Check\033[0m \033[1;35m[2]\033[1;36m Online Check\033[0m")

                config_choice = input(
                    "\033[1;93m[ Shako.dev ] - Select check method (1-2, 'q' to keep default): \033[0m").strip()


                if config_choice.lower() == "q":

                    globals()["check_exec_enable"] = "1"

                    globals()["lua_script_template"] = 'if not game:IsLoaded() then game.Loaded:Wait() end local f = tostring(game.Players.LocalPlayer.UserId)..".main" local c = "https://discord.gg/FcEGmkNDDe" local function w() local g = pcall(writefile, f, c) if not g then game:GetService("TeleportService"):Teleport(game.PlaceId, game.Players.LocalPlayer) end end task.spawn(function() w() while true do task.wait(5) w() end end)'

                    print(
                        "\033[1;32m[ Shako.dev ] - Default set: Executor + Shako Check\033[0m")

                elif config_choice == "1":

                    globals()["check_exec_enable"] = "1"

                    globals()["lua_script_template"] = 'if not game:IsLoaded() then game.Loaded:Wait() end local f = tostring(game.Players.LocalPlayer.UserId)..".main" local c = "https://discord.gg/FcEGmkNDDe" local function w() local g = pcall(writefile, f, c) if not g then game:GetService("TeleportService"):Teleport(game.PlaceId, game.Players.LocalPlayer) end end task.spawn(function() w() while true do task.wait(5) w() end end)'

                    print(
                        "\033[1;32m[ Shako.dev ] - Set to Executor + Shako Check\033[0m")

                elif config_choice == "2":

                    globals()["check_exec_enable"] = "0"

                    globals()["lua_script_template"] = None

                    print(
                        "\033[1;36m[ Shako.dev ] - Set to Online Check.\033[0m")

                else:

                    print(
                        "\033[1;31m[ Shako.dev ] - Invalid choice. Keeping default.\033[0m")

                    globals()["check_exec_enable"] = "1"

                    globals()["lua_script_template"] = 'if not game:IsLoaded() then game.Loaded:Wait() end local f = tostring(game.Players.LocalPlayer.UserId)..".main" local c = "https://discord.gg/FcEGmkNDDe" local function w() local g = pcall(writefile, f, c) if not g then game:GetService("TeleportService"):Teleport(game.PlaceId, game.Players.LocalPlayer) end end task.spawn(function() w() while true do task.wait(5) w() end end)'


                config_file = os.path.join("Shako.dev", "checkui.lua")

                if globals()["lua_script_template"]:

                    try:

                        os.makedirs("Shako.dev", exist_ok=True)

                        with open(config_file, "w") as f:

                            f.write(globals()["lua_script_template"])

                        print(
                            f"\033[1;36m[ Shako.dev ] - Script saved to {config_file}\033[0m")

                    except Exception as e:

                        print(
                            f"\033[1;31m[ Shako.dev ] - Error saving script: {e}\033[0m")

                        Utilities.log_error(
                            f"Error saving script to {config_file}: {e}")

                else:

                    if os.path.exists(config_file):

                        try:

                            os.remove(config_file)

                            print(
                                f"\033[1;36m[ Shako.dev ] - Removed {config_file} for Online Check.\033[0m")

                        except Exception as e:

                            print(
                                f"\033[1;31m[ Shako.dev ] - Error removing {config_file}: {e}\033[0m")

                            Utilities.log_error(
                                f"Error removing {config_file}: {e}")


                globals()["command_8_configured"] = True


                FileManager.save_config()

                print(
                    "\033[1;32m[ Shako.dev ] - Check method configuration saved.\033[0m")

            except Exception as e:

                print(
                    f"\033[1;31m[ Shako.dev ] - Error setting up check method: {e}\033[0m")

                Utilities.log_error(f"Check method setup error: {e}")

                input("\033[1;32mPress Enter to return...\033[0m")

                continue

            input("\033[1;32mPress Enter to return...\033[0m")

            continue


        elif setup_type == "6":

            try:

                current_prefix = globals().get("package_prefix", "com.roblox")

                print(
                    f"\033[1;32m[ Shako.dev ] - Current package prefix: {current_prefix}\033[0m")

                new_prefix = input(
                    "\033[1;93m[ Shako.dev ] - Enter new package prefix (or press Enter to keep current): \033[0m").strip()


                if new_prefix:

                    globals()["package_prefix"] = new_prefix

                    FileManager.save_config()

                    print(
                        f"\033[1;32m[ Shako.dev ] - Package prefix updated to: {new_prefix}\033[0m")

                else:

                    print(
                        "\033[1;33m[ Shako.dev ] - Keeping current prefix.\033[0m")

            except Exception as e:

                print(f"\033[1;31m[ Shako.dev ] - Error: {e}\033[0m")

                Utilities.log_error(f"Package prefix error: {e}")

            input("\033[1;32mPress Enter to return...\033[0m")

            continue


        elif setup_type == "7":

            try:

                print(
                    "\033[1;35m[1]\033[1;32m Enable Auto Android ID\033[0m \033[1;35m[2]\033[1;31m Disable\033[0m")

                choice = input(
                    "\033[1;93m[ Shako.dev ] - Select option: \033[0m").strip()


                if choice == "1":

                    auto_android_id_value = input(
                        "\033[1;93m[ Shako.dev ] - Enter Android ID to set: \033[0m").strip()

                    if auto_android_id_value:

                        auto_android_id_enabled = True

                        if auto_android_id_thread is None or not auto_android_id_thread.is_alive():

                            auto_android_id_thread = threading.Thread(
                                target=auto_change_android_id, daemon=True)

                            auto_android_id_thread.start()

                        print(
                            f"\033[1;32m[ Shako.dev ] - Auto Android ID enabled with value: {auto_android_id_value}\033[0m")

                    else:

                        print(
                            "\033[1;31m[ Shako.dev ] - Invalid Android ID.\033[0m")

                elif choice == "2":

                    auto_android_id_enabled = False

                    print(
                        "\033[1;31m[ Shako.dev ] - Auto Android ID disabled.\033[0m")

                else:

                    print("\033[1;31m[ Shako.dev ] - Invalid choice.\033[0m")

            except Exception as e:

                print(f"\033[1;31m[ Shako.dev ] - Error: {e}\033[0m")

                Utilities.log_error(f"Android ID error: {e}")

            input("\033[1;32mPress Enter to return...\033[0m")

            continue


        elif setup_type == "8":

            try:

                print(
                    "\033[1;32m[ Shako.dev ] - Launching all packages to main menu...\033[0m")

                packages = RobloxManager.get_roblox_packages()

                for package_name in packages:

                    subprocess.run(
    f"monkey -p {package_name} -c android.intent.category.LAUNCHER 1",
    shell=True,
    stdout=subprocess.DEVNULL,
     stderr=subprocess.DEVNULL)

                    print(
                        f"\033[1;36m[ Shako.dev ] - Launched {package_name}\033[0m")

                    time.sleep(2)

                print("\033[1;32m[ Shako.dev ] - All packages launched.\033[0m")

            except Exception as e:

                print(f"\033[1;31m[ Shako.dev ] - Error: {e}\033[0m")

                Utilities.log_error(f"Launch all error: {e}")

            input("\033[1;32mPress Enter to return...\033[0m")

            continue


        elif setup_type == "9":

            Runner.logout_all_packages()

            input("\033[1;32mPress Enter to return...\033[0m")

            continue


        else:

            print(
                "\033[1;31m[ Shako.dev ] - Invalid command. Please try again.\033[0m")

            input("\033[1;32mPress Enter to return...\033[0m")

            continue


if __name__ == "__main__":

    main()
