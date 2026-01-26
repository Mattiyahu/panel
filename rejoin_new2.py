#!/usr/bin/env python3
import os
import subprocess
import time
import requests
import psutil
import datetime
import sqlite3
import json
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, IntPrompt
from rich.progress import Progress
from rich.live import Live
from rich.layout import Layout
from rich import print as rprint

# Configurações Globais
console = Console()
CONFIG_FILE = "config.json"
CHECK_INTERVAL = 15

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {"vip_link": "", "webhook_url": ""}

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

config = load_config()
VIP_LINK = config.get("vip_link", "")
WEBHOOK_URL = config.get("webhook_url", "")
LOW_CPU_THRESHOLD = 0.3
MAX_LOWCPU_TIME = 90
COOLDOWN_TIME = 120
PROTO_ACTIVITY = "com.roblox.client.ActivityProtocolLaunch"

class RobloxManager:
    def __init__(self):
        self.packages = []
        self.lowcpu_count = {}
        self.cooldowns = {}
        self.is_running = False

    def run_adb(self, command):
        try:
            result = subprocess.run(f"adb shell {command}", shell=True, capture_output=True, text=True)
            return result.stdout.strip()
        except:
            return ""

    def get_packages(self):
        output = self.run_adb("pm list packages roblox")
        self.packages = [line.replace("package:", "").strip() for line in output.splitlines() if "roblox" in line]
        for pkg in self.packages:
            if pkg not in self.lowcpu_count:
                self.lowcpu_count[pkg] = 0
                self.cooldowns[pkg] = 0
        return self.packages

    def clear_cache(self):
        rprint("[yellow]🧹 Limpando cache de todos os pacotes Roblox...[/yellow]")
        for pkg in self.get_packages():
            self.run_adb(f"pm clear {pkg}")
        rprint("[green]✅ Cache limpo com sucesso![/green]")

    def take_screenshot(self, pkg):
        filename = f"screen_{pkg}.png"
        self.run_adb(f"screencap -p /sdcard/{filename}")
        subprocess.run(f"adb pull /sdcard/{filename} .", shell=True, capture_output=True)
        return filename

    def send_webhook_with_print(self, message, pkg=None):
        if not WEBHOOK_URL: return
        
        payload = {"content": message}
        files = {}
        
        if pkg:
            img_path = self.take_screenshot(pkg)
            if os.path.exists(img_path):
                files = {"file": open(img_path, "rb")}
        
        try:
            requests.post(WEBHOOK_URL, data=payload, files=files)
            if pkg and os.path.exists(img_path):
                os.remove(img_path)
        except Exception as e:
            rprint(f"[red]Erro Webhook: {e}[/red]")

    def check_ui_state(self, package):
        focus = self.run_adb("dumpsys window windows | grep -E 'mCurrentFocus'")
        if package not in focus:
            return "bubble_or_background"

        ui_xml = self.run_adb("uiautomator dump /sdcard/view.xml > /dev/null 2>&1 && cat /sdcard/view.xml")
        if not ui_xml: return "ok"
        
        ui_lower = ui_xml.lower()
        if any(x in ui_lower for x in ["disconnected", "desconectado", "connection lost"]):
            return "disconnected"
        if all(x in ui_lower for x in ["home", "discover", "avatar"]):
            return "home"
        if "atlas" in ui_lower and ("key" in ui_lower or "enter" in ui_lower):
            return "key_request"
        return "ok"

    def reconnect(self, pkg):
        self.run_adb(f"am force-stop {pkg}")
        time.sleep(2)
        self.run_adb(f"am start --task-windowing-mode 5 -n {pkg}/{PROTO_ACTIVITY} -a android.intent.action.VIEW -d '{VIP_LINK}'")
        self.cooldowns[pkg] = time.time() + COOLDOWN_TIME

    def start_monitor(self):
        if not VIP_LINK:
            rprint("[red]❌ Configure o VIP LINK primeiro![/red]")
            return
        
        self.is_running = True
        self.get_packages()
        rprint(f"[green]🚀 Monitoramento iniciado para {len(self.packages)} pacotes.[/green]")
        
        try:
            while self.is_running:
                for pkg in self.packages:
                    if time.time() < self.cooldowns.get(pkg, 0): continue
                    
                    pid = self.run_adb(f"pidof {pkg}")
                    if not pid:
                        self.reconnect(pkg)
                        continue

                    state = self.check_ui_state(pkg)
                    if state in ["disconnected", "home", "bubble_or_background"]:
                        rprint(f"[yellow]⚠️ {pkg} estado: {state}. Reiniciando...[/yellow]")
                        self.reconnect(pkg)
                    elif state == "key_request":
                        rprint(f"[bold red]🔑 Atlas Key Request em {pkg}![/bold red]")
                        self.send_webhook_with_print(f"🔑 **Atlas Key Request** detectado em `{pkg}`", pkg)
                
                time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            self.is_running = False

manager = RobloxManager()

def show_menu():
    console.clear()
    header = Panel.fit(
        "[bold magenta]ROBLOX MULTI-ACCOUNT MANAGER[/bold magenta]\n[cyan]Advanced Auto-Rejoin & Setup Panel[/cyan]",
        border_style="magenta"
    )
    rprint(header)

    # Status das Configurações
    status_table = Table(show_header=False, box=None)
    status_table.add_row(f"🔗 VIP Link: {'[green]Configurado[/green]' if VIP_LINK else '[red]Não definido[/red]'}")
    status_table.add_row(f"⚓ Webhook: {'[green]Configurado[/green]' if WEBHOOK_URL else '[red]Não definido[/red]'}")
    rprint(Panel(status_table, title="Status", border_style="yellow"))

    table = Table(show_header=False, box=None)
    table.add_row("[1] 🚀 Start Auto-Rejoin", "[2] 🛠️ Run Auto-Setup")
    table.add_row("[3] 📋 Show Package List", "[4] 🧹 Clear Roblox Cache")
    table.add_row("[5] ⚙️ Manage Configs", "[6] 📸 Test Webhook + Print")
    table.add_row("[0] ❌ Exit", "")
    
    rprint(Panel(table, title="Menu Principal", border_style="blue"))

def manage_configs():
    global VIP_LINK, WEBHOOK_URL
    while True:
        console.clear()
        rprint(Panel("[bold cyan]Gerenciar Configurações[/bold cyan]", border_style="cyan"))
        rprint(f"1. [yellow]Editar VIP Link[/yellow] (Atual: {VIP_LINK[:30]}...)")
        rprint(f"2. [yellow]Editar Webhook URL[/yellow] (Atual: {WEBHOOK_URL[:30]}...)")
        rprint("3. [red]Remover VIP Link[/red]")
        rprint("4. [red]Remover Webhook URL[/red]")
        rprint("0. [green]Voltar[/green]")
        
        sub_choice = Prompt.ask("Escolha", choices=["1", "2", "3", "4", "0"])
        
        if sub_choice == "1":
            VIP_LINK = Prompt.ask("Novo VIP Link")
        elif sub_choice == "2":
            WEBHOOK_URL = Prompt.ask("Novo Webhook URL")
        elif sub_choice == "3":
            VIP_LINK = ""
            rprint("[red]VIP Link removido.[/red]")
            time.sleep(1)
        elif sub_choice == "4":
            WEBHOOK_URL = ""
            rprint("[red]Webhook URL removido.[/red]")
            time.sleep(1)
        elif sub_choice == "0":
            break
        
        # Salva sempre que houver alteração
        save_config({"vip_link": VIP_LINK, "webhook_url": WEBHOOK_URL})

def main():
    global VIP_LINK, WEBHOOK_URL
    
    while True:
        show_menu()
        choice = Prompt.ask("Escolha uma opção", choices=["1", "2", "3", "4", "5", "6", "0"])

        if choice == "1":
            manager.start_monitor()
        elif choice == "2":
            subprocess.run("bash setup.sh", shell=True)
            Prompt.ask("\nPressione Enter para voltar")
        elif choice == "3":
            pkgs = manager.get_packages()
            t = Table(title="Pacotes Roblox Encontrados")
            t.add_column("ID", style="cyan")
            t.add_column("Package Name", style="green")
            for i, p in enumerate(pkgs): t.add_row(str(i+1), p)
            rprint(t)
            Prompt.ask("\nPressione Enter para voltar")
        elif choice == "4":
            manager.clear_cache()
            Prompt.ask("\nPressione Enter para voltar")
        elif choice == "5":
            manage_configs()
        elif choice == "6":
            pkgs = manager.get_packages()
            if pkgs:
                rprint("[cyan]Enviando teste...[/cyan]")
                manager.send_webhook_with_print("📸 Teste de Webhook com Print", pkgs[0])
            else:
                rprint("[red]Nenhum pacote encontrado para print.[/red]")
            Prompt.ask("\nPressione Enter para voltar")
        elif choice == "0":
            break

if __name__ == "__main__":
    main()
