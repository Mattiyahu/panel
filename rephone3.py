#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RE_PHONE v9.1 VSPhone FINAL by MSA
Auto Rejoin Roblox Clones (Termux + ADB)

✅ Detecta clones automaticamente (pm list packages)
✅ Monitor passivo (PID + CPU + Rede UID)
✅ Focus Lock (1 foco por vez)
✅ UI check só quando SUSPECT/DEAD
✅ Detecta: HOME / DISCONNECTED / RECONNECT / KEY
✅ HOME -> força restart e reabre VIP (como você pediu)
✅ Webhook com screenshot (funciona no Termux do VSPhone)

Requisitos:
  pkg update -y
  pkg install python -y
  pip install rich requests
"""

import os
import subprocess
import time
import requests
import datetime
import json
import threading
import re

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from rich.layout import Layout
from rich.live import Live
from rich.align import Align
from rich.box import DOUBLE, ROUNDED

console = Console()
CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "vip_link": "",
    "webhook_url": "",
    "auto_key": False,  # você pode ligar depois
    "close_browser_on_restart": True,
    "browser_packages": [
        "com.android.chrome",
        "com.brave.browser",
        "com.microsoft.emmx",
        "org.mozilla.firefox",
    ],
}

# =============================
# TUNING (ajuste fino)
# =============================
CHECK_INTERVAL = 3
FOCUS_DELAY = 0.9
COOLDOWN_AFTER_RESTART = 120

CPU_THRESHOLD_ACTIVE = 15.0
CPU_THRESHOLD_SUSPECT = 5.0
SUSPECT_COUNT_LIMIT = 5

NET_MIN_BYTES_ALIVE = 200  # bytes por ciclo >= isso = tem vida


def now_ts():
    return datetime.datetime.now().strftime("%H:%M:%S")


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = DEFAULT_CONFIG.copy()
            merged.update(data)
            return merged
        except:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)


CONFIG = load_config()


def adb(cmd, timeout=10):
    """adb shell command"""
    try:
        out = subprocess.check_output(
            f"adb shell {cmd}",
            shell=True,
            stderr=subprocess.DEVNULL,
            timeout=timeout
        )
        return out.decode(errors="ignore").strip()
    except:
        return ""


def adb_host(cmd, timeout=12):
    """host cmd"""
    try:
        out = subprocess.check_output(
            cmd,
            shell=True,
            stderr=subprocess.DEVNULL,
            timeout=timeout
        )
        return out.decode(errors="ignore").strip()
    except:
        return ""


def ensure_adb_ok():
    out = adb_host("adb devices", timeout=8)
    if "offline" in out or "unauthorized" in out:
        return False
    return "device" in out


def force_portrait():
    adb("settings put system accelerometer_rotation 0")
    adb("settings put system user_rotation 0")


def stabilize_focus():
    # tap no meio pra “ativar” a janela flutuante do DeltaClone
    adb("input tap 300 300", timeout=4)
    time.sleep(0.2)


def send_webhook(url, msg, screenshot=False):
    if not url:
        return
    try:
        if screenshot:
            adb("screencap -p /sdcard/re_phone_screen.png", timeout=10)
            adb_host("adb pull /sdcard/re_phone_screen.png ./re_phone_screen.png", timeout=15)

            if os.path.exists("./re_phone_screen.png"):
                with open("./re_phone_screen.png", "rb") as f:
                    requests.post(
                        url,
                        data={"content": msg},
                        files={"file": ("screen.png", f)},
                        timeout=15
                    )
                return

        requests.post(url, json={"content": msg}, timeout=8)
    except:
        pass


# =============================
# PACKAGES / PROCESS
# =============================
def get_packages():
    out = adb("pm list packages", timeout=12)
    pkgs = []
    for l in out.splitlines():
        l = l.strip()
        if l.startswith("package:"):
            pkg = l.replace("package:", "").strip()
            if "roblox" in pkg.lower():
                pkgs.append(pkg)
    pkgs = sorted(list(set(pkgs)))
    return pkgs


def get_pid(pkg):
    return adb(f"pidof {pkg}", timeout=6)


def get_cpu(pid):
    if not pid:
        return 0.0
    top = adb(f"top -n 1 -p {pid} | grep {pid}", timeout=6)
    if not top:
        return 0.0
    try:
        for p in top.split():
            if "%" in p:
                return float(p.replace("%", "").replace(",", "."))
    except:
        pass
    return 0.0


def get_uid(pkg):
    out = adb(f"dumpsys package {pkg} | grep userId=", timeout=10)
    m = re.search(r"userId=(\d+)", out)
    return m.group(1) if m else None


def get_network_bytes(uid):
    if not uid:
        return 0
    try:
        out = adb("cat /proc/net/xt_qtaguid/stats", timeout=12)
        total = 0
        needle = f" {uid} "
        for line in out.splitlines():
            if needle in line:
                parts = line.split()
                # rx_bytes col 5 / tx_bytes col 7 na maioria
                if len(parts) > 7:
                    rx = int(parts[5])
                    tx = int(parts[7])
                    total += rx + tx
        return total
    except:
        return 0


# =============================
# APP CONTROL
# =============================
def stop_app(pkg):
    adb(f"am force-stop {pkg}", timeout=10)


def close_browsers():
    if not CONFIG.get("close_browser_on_restart", True):
        return
    for b in CONFIG.get("browser_packages", []):
        if b:
            adb(f"am force-stop {b}", timeout=6)


def bring_to_focus(pkg):
    """
    Melhor método no VSPhone/DeltaClone:
    resolve-activity -> am start -n activity
    """
    resolved = adb(f"cmd package resolve-activity --brief {pkg}", timeout=10)
    lines = [l.strip() for l in resolved.splitlines() if l.strip()]
    activity = lines[-1] if lines else ""

    if "/" in activity:
        adb(f"am start -n {activity}", timeout=12)
    else:
        adb(f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1", timeout=12)

    time.sleep(FOCUS_DELAY)


def start_app_with_vip(pkg, vip_link):
    """
    Abre o VIP (roblox:// ou https://).
    Tenta ActivityProtocolLaunch primeiro, depois fallback.
    """
    out = adb(
        f"am start -n {pkg}/com.roblox.client.ActivityProtocolLaunch "
        f"-a android.intent.action.VIEW -d '{vip_link}'",
        timeout=15
    )
    if "Error" in out or "Exception" in out:
        adb(f"am start -a android.intent.action.VIEW -d '{vip_link}'", timeout=15)
    time.sleep(2)


# =============================
# UI DETECTION
# =============================
def get_ui_xml():
    adb("uiautomator dump /sdcard/re_phone_ui.xml >/dev/null 2>&1", timeout=12)
    time.sleep(0.2)
    return adb("cat /sdcard/re_phone_ui.xml", timeout=8)


def detect_disconnected(xml):
    xl = xml.lower()
    keys = [
        "disconnected",
        "connection lost",
        "lost connection",
        "reconnect",
        "reconnecting",
        "reconectar",
        "reconectando",
        "retry",
        "tentar novamente",
    ]
    return any(k in xl for k in keys)


def detect_home_screen(xml):
    xl = xml.lower()

    home_indicators = [
        "home",
        "avatar",
        "charts",
        "friends",
        "discover",
        "search",
        "pesquisar",
        "recommended",
        "recomendados",
        "continue playing",
        "check your age",
        "criar conta",
    ]

    game_indicators = [
        "backpack",
        "leaderboard",
        "reset character",
        "leave",
        "chat",
    ]

    home_count = sum(1 for k in home_indicators if k in xl)
    game_count = sum(1 for k in game_indicators if k in xl)

    return home_count >= 2 and game_count == 0


def detect_key_screen(xml):
    xl = xml.lower()
    keys = [
        "welcome back",
        "enter key",
        "receive key",
        "key_example",
        "key system",
        "atlas",
    ]
    return any(k in xl for k in keys)


# =============================
# INSTANCE
# =============================
class Instance:
    def __init__(self, pkg):
        self.pkg = pkg
        self.name = pkg.split(".")[-1].upper()

        self.pid = ""
        self.uid = get_uid(pkg)

        self.cpu = 0.0
        self.status = "INIT"

        self.last_bytes = 0
        self.current_bytes = 0
        self.net_delta = 0

        self.suspect_count = 0
        self.needs_check = False
        self.cooldown_until = time.time() + 3

        self.last_event = "Iniciando..."
        self.lock = threading.Lock()

    def update_metrics(self):
        with self.lock:
            self.pid = get_pid(self.pkg)
            self.cpu = get_cpu(self.pid) if self.pid else 0.0

            self.last_bytes = self.current_bytes
            self.current_bytes = get_network_bytes(self.uid)
            self.net_delta = max(0, self.current_bytes - self.last_bytes)

            now = time.time()
            if now < self.cooldown_until:
                self.status = "SYNC"
                self.suspect_count = 0
                self.needs_check = False
                return

            if not self.pid:
                self.status = "DEAD"
                self.needs_check = True
                return

            alive_by_cpu = self.cpu >= CPU_THRESHOLD_ACTIVE
            alive_by_net = self.net_delta >= NET_MIN_BYTES_ALIVE

            if alive_by_cpu or alive_by_net:
                self.status = "OK"
                self.suspect_count = 0
                self.needs_check = False
                return

            # suspeitar só se CPU morta e rede morta
            if self.cpu < CPU_THRESHOLD_SUSPECT and self.net_delta == 0:
                self.suspect_count += 1
                if self.suspect_count >= SUSPECT_COUNT_LIMIT:
                    self.status = "SUSPECT"
                    self.needs_check = True
                else:
                    self.status = "LOW"
            else:
                self.status = "LOW"

    def mark_checked(self):
        with self.lock:
            self.needs_check = False

    def restart(self, reason):
        vip = CONFIG.get("vip_link", "")
        wh = CONFIG.get("webhook_url", "")

        with self.lock:
            self.last_event = reason
            self.suspect_count = 0
            self.needs_check = False
            self.cooldown_until = time.time() + COOLDOWN_AFTER_RESTART

        send_webhook(wh, f"🔄 `{self.name}` -> {reason}", screenshot=False)

        stop_app(self.pkg)
        time.sleep(1)

        close_browsers()
        time.sleep(0.5)

        start_app_with_vip(self.pkg, vip)


# =============================
# MONITOR
# =============================
class Monitor:
    def __init__(self):
        self.instances = {}
        self.running = False
        self.logs = []
        self.focus_lock = threading.Lock()
        self.checking = ""

    def log(self, msg):
        self.logs.append(f"[{now_ts()}] {msg}")
        if len(self.logs) > 12:
            self.logs.pop(0)

    def passive_worker(self, inst: Instance):
        while self.running:
            inst.update_metrics()
            time.sleep(CHECK_INTERVAL)

    def focus_check_worker(self):
        while self.running:
            queue = []
            for inst in self.instances.values():
                with inst.lock:
                    if inst.needs_check and time.time() >= inst.cooldown_until:
                        queue.append(inst)

            for inst in queue:
                if not self.running:
                    break
                with self.focus_lock:
                    self.check_one(inst)
                time.sleep(FOCUS_DELAY)

            time.sleep(CHECK_INTERVAL)

    def check_one(self, inst: Instance):
        self.checking = inst.name
        self.log(f"🔍 Verificando {inst.name}...")

        with inst.lock:
            dead = (not inst.pid)

        if dead:
            self.log(f"💀 {inst.name}: Processo morto -> REABRIR VIP")
            inst.restart("Processo morto")
            inst.mark_checked()
            self.checking = ""
            time.sleep(3)
            return

        # Focar e estabilizar
        bring_to_focus(inst.pkg)
        stabilize_focus()

        xml = get_ui_xml()
        if not xml:
            self.log(f"⚠️ {inst.name}: UI dump vazio")
            inst.mark_checked()
            self.checking = ""
            return

        wh = CONFIG.get("webhook_url", "")

        if detect_disconnected(xml):
            self.log(f"📡 {inst.name}: Disconnected/Reconnect -> REABRIR VIP")
            send_webhook(wh, f"📡 **{inst.name}**: Disconnected/Reconnect!", screenshot=True)
            inst.restart("Disconnected/Reconnect")

        elif detect_home_screen(xml):
            self.log(f"🏠 {inst.name}: Tela HOME -> REABRIR VIP")
            send_webhook(wh, f"🏠 **{inst.name}**: Tela HOME detectada!", screenshot=True)
            inst.restart("Tela HOME")

        elif detect_key_screen(xml):
            self.log(f"🔑 {inst.name}: KEY detectada (alerta)")
            send_webhook(wh, f"🔑 **{inst.name}**: KEY detectada!", screenshot=True)
            # se você quiser auto-key depois, a gente adiciona aqui

        else:
            self.log(f"✓ {inst.name}: OK (falso positivo)")

        inst.mark_checked()
        self.checking = ""

    def render(self):
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=4),
            Layout(name="main", size=13),
            Layout(name="logs", size=10),
        )

        vip_ok = "OK" if CONFIG.get("vip_link") else "NO"
        head = f"[bold red]RE_PHONE v9.1 VSPhone FINAL[/bold red] | VIP: [{'green' if vip_ok=='OK' else 'red'}]{vip_ok}[/{'green' if vip_ok=='OK' else 'red'}]"
        layout["header"].update(Panel(Align.center(head), border_style="red", box=DOUBLE))

        t = Table(border_style="bright_red", expand=True, header_style="bold white on red", box=ROUNDED)
        t.add_column("INSTÂNCIA", width=14)
        t.add_column("CPU", justify="center", width=8)
        t.add_column("REDE Δ", justify="center", width=10)
        t.add_column("STATUS", justify="center", width=12)
        t.add_column("SUSP", justify="center", width=6)

        for inst in self.instances.values():
            with inst.lock:
                name = inst.name
                cpu = inst.cpu
                netd = inst.net_delta
                st = inst.status
                sc = inst.suspect_count

            if name == self.checking:
                name = f"[bold cyan]→ {name}[/bold cyan]"

            cpu_txt = (
                f"[green]{cpu:.1f}%[/green]" if cpu >= CPU_THRESHOLD_ACTIVE else
                f"[yellow]{cpu:.1f}%[/yellow]" if cpu >= CPU_THRESHOLD_SUSPECT else
                f"[red]{cpu:.1f}%[/red]"
            )
            net_txt = (
                f"[green]{netd}[/green]" if netd >= NET_MIN_BYTES_ALIVE else
                f"[yellow]{netd}[/yellow]" if netd > 0 else
                f"[red]0[/red]"
            )

            status_map = {
                "OK": "[bold green]ONLINE[/bold green]",
                "SYNC": "[bold blue]SYNC[/bold blue]",
                "LOW": "[bold yellow]LOW[/bold yellow]",
                "SUSPECT": "[bold red]SUSPECT[/bold red]",
                "DEAD": "[bold red]DEAD[/bold red]",
                "INIT": "[dim]INIT[/dim]",
            }
            st_txt = status_map.get(st, st)

            t.add_row(name, cpu_txt, net_txt, st_txt, f"[yellow]{sc}[/yellow]")

        layout["main"].update(Panel(t, title="[bold white on red] MONITOR [/bold white on red]", border_style="red", box=DOUBLE))

        logs = "\n".join(self.logs) if self.logs else "[dim]Aguardando eventos...[/dim]"
        layout["logs"].update(Panel(logs, title="[bold white on red] LOGS [/bold white on red]", border_style="red", box=ROUNDED))
        return layout

    def start(self):
        if not ensure_adb_ok():
            console.print("[bold red]ADB não está OK (offline/unauthorized).[/bold red]")
            time.sleep(2)
            return

        if not CONFIG.get("vip_link"):
            console.print("[bold red]Configure o VIP Link primeiro![/bold red]")
            time.sleep(2)
            return

        force_portrait()

        pkgs = get_packages()
        if not pkgs:
            console.print("[bold red]Nenhum pacote roblox encontrado.[/bold red]")
            time.sleep(2)
            return

        self.instances = {}
        for pkg in pkgs:
            inst = Instance(pkg)
            self.instances[pkg] = inst
            self.log(f"✓ {inst.name} monitorando")

        self.running = True

        for inst in self.instances.values():
            threading.Thread(target=self.passive_worker, args=(inst,), daemon=True).start()

        threading.Thread(target=self.focus_check_worker, daemon=True).start()
        self.log("🔒 Focus Lock ON")

        with Live(self.render(), refresh_per_second=2, screen=True) as live:
            try:
                while self.running:
                    live.update(self.render())
                    time.sleep(0.5)
            except KeyboardInterrupt:
                self.running = False


monitor = Monitor()


def config_menu():
    global CONFIG
    console.clear()
    console.print(Panel("[bold]CONFIGURAÇÕES[/bold]", border_style="red"))

    console.print(f"[1] VIP Link: [dim]{(CONFIG.get('vip_link') or 'N/A')[:90]}[/dim]")
    console.print(f"[2] Webhook: [dim]{(CONFIG.get('webhook_url') or 'N/A')[:90]}[/dim]")
    console.print(f"[3] Fechar navegador no restart: [bold]{'SIM' if CONFIG.get('close_browser_on_restart', True) else 'NÃO'}[/bold]")
    console.print("[0] Voltar")

    opt = Prompt.ask("Opção", choices=["1", "2", "3", "0"])
    if opt == "1":
        CONFIG["vip_link"] = Prompt.ask("Cole VIP Link (roblox:// ou https://)")
        save_config(CONFIG)
    elif opt == "2":
        CONFIG["webhook_url"] = Prompt.ask("Cole Webhook (opcional)", default=CONFIG.get("webhook_url", ""))
        save_config(CONFIG)
    elif opt == "3":
        CONFIG["close_browser_on_restart"] = not CONFIG.get("close_browser_on_restart", True)
        save_config(CONFIG)
        console.print("[green]Alterado![/green]")
        time.sleep(1)


def tools_menu():
    console.clear()
    console.print(Panel("[bold]FERRAMENTAS[/bold]", border_style="red"))

    console.print("[1] Listar pacotes Roblox")
    console.print("[2] Stop ALL Roblox")
    console.print("[3] Start ALL Roblox (VIP)")
    console.print("[4] Testar UI dump (janela atual)")
    console.print("[0] Voltar")

    opt = Prompt.ask("Opção", choices=["1", "2", "3", "4", "0"])
    if opt == "1":
        pkgs = get_packages()
        console.print(f"[yellow]Encontrados {len(pkgs)} pacotes:[/yellow]")
        for p in pkgs:
            console.print(f"  - [green]{p}[/green] (PID: {get_pid(p) or 'N/A'})")
        Prompt.ask("Enter")
    elif opt == "2":
        for p in get_packages():
            stop_app(p)
        console.print("[red]Todos parados.[/red]")
        time.sleep(1)
    elif opt == "3":
        vip = CONFIG.get("vip_link", "")
        if not vip:
            console.print("[red]Configure VIP link primeiro.[/red]")
            time.sleep(1)
            return
        for p in get_packages():
            start_app_with_vip(p, vip)
            time.sleep(1)
        console.print("[green]Todos iniciados.[/green]")
        time.sleep(1)
    elif opt == "4":
        xml = get_ui_xml()
        console.print(xml[:1500] if xml else "[red]UI dump vazio[/red]")
        Prompt.ask("Enter")


def main_menu():
    global CONFIG
    while True:
        console.clear()

        vip_ok = "✓" if CONFIG.get("vip_link") else "✗"
        wh_ok = "✓" if CONFIG.get("webhook_url") else "✗"

        banner = f"""
[bold red]RE_PHONE v9.1 VSPhone FINAL[/bold red]
[white]Auto Rejoin Roblox Clones (ADB/Termux)[/white]

VIP: [{'green' if vip_ok=='✓' else 'red'}]{vip_ok}[/{'green' if vip_ok=='✓' else 'red'}]
WEBHOOK: [{'green' if wh_ok=='✓' else 'red'}]{wh_ok}[/{'green' if wh_ok=='✓' else 'red'}]
"""
        console.print(Panel(banner, border_style="red", box=DOUBLE))

        console.print("[1] 🚀 Iniciar monitor")
        console.print("[2] ⚙️ Configurações")
        console.print("[3] 🛠️ Ferramentas")
        console.print("[0] ❌ Sair")

        c = Prompt.ask("Selecione", choices=["1", "2", "3", "0"])
        if c == "1":
            monitor.start()
        elif c == "2":
            config_menu()
            CONFIG = load_config()
        elif c == "3":
            tools_menu()
            CONFIG = load_config()
        elif c == "0":
            break


if __name__ == "__main__":
    main_menu()
