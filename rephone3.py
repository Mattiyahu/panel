#!/usr/bin/env python3
"""
RE_PHONE v9.0 PRO (FIXED) by MSA
Auto Rejoin / Monitor Roblox Clones (Android + Termux + ADB)

✅ Detecta automaticamente todos os pacotes que contenham "roblox"
✅ Monitor passivo (PID + CPU + Rede por UID)
✅ Focus Lock (só 1 clone vai pra frente por vez)
✅ UI check só quando SUSPECT / DEAD
✅ Detecta: disconnected / reconnect / home screen / atlas key screen
✅ Reinicia com VIP link (roblox:// OU https://)
✅ Webhook opcional (Discord)
✅ Fecha navegador junto (configurável)
✅ HUD com Rich

Requisitos Termux:
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
from rich.text import Text
from rich.align import Align
from rich.box import DOUBLE, ROUNDED

# =========================
# CONFIG
# =========================
console = Console()
CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "vip_link": "",
    "webhook_url": "",
    "auto_key": True,
    "close_browser_on_restart": True,
    "browser_packages": [
        "com.android.chrome",
        "com.brave.browser",
        "com.microsoft.emmx",
        "org.mozilla.firefox",
    ],
}

# Monitoramento
CHECK_INTERVAL = 3
FOCUS_DELAY = 0.8
COOLDOWN_AFTER_RESTART = 120

CPU_THRESHOLD_ACTIVE = 15.0
CPU_THRESHOLD_SUSPECT = 5.0
SUSPECT_COUNT_LIMIT = 5

# Rede: quantos bytes em CHECK_INTERVAL já contam como "tem vida"
NET_MIN_BYTES_ALIVE = 200


# =========================
# HELPERS
# =========================
def now_ts():
    return datetime.datetime.now().strftime("%H:%M:%S")


def safe_print(msg):
    try:
        console.print(msg)
    except:
        print(msg)


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # merge com defaults
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


def adb(cmd, timeout=8):
    """
    Executa ADB shell com timeout.
    Retorna stdout (string).
    """
    try:
        out = subprocess.check_output(
            f"adb shell {cmd}",
            shell=True,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
        return out.decode(errors="ignore").strip()
    except:
        return ""


def adb_host(cmd, timeout=12):
    """
    Executa comando no host (não é adb shell).
    """
    try:
        out = subprocess.check_output(
            cmd,
            shell=True,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
        return out.decode(errors="ignore").strip()
    except:
        return ""


def ensure_adb_ok():
    out = adb_host("adb devices", timeout=8)
    return ("device" in out) and ("unauthorized" not in out) and ("offline" not in out)


def force_portrait():
    # trava rotação pra reduzir bagunça no multi-window
    adb("settings put system accelerometer_rotation 0")
    adb("settings put system user_rotation 0")


def send_webhook(url, msg, screenshot=False):
    if not url:
        return
    try:
        if screenshot:
            adb("screencap -p /sdcard/re_phone_screen.png")
            adb_host("adb pull /sdcard/re_phone_screen.png ./re_phone_screen.png", timeout=15)
            if os.path.exists("./re_phone_screen.png"):
                with open("./re_phone_screen.png", "rb") as f:
                    requests.post(
                        url,
                        data={"content": msg},
                        files={"file": ("screen.png", f)},
                        timeout=12,
                    )
                return
        requests.post(url, json={"content": msg}, timeout=8)
    except:
        pass


# =========================
# PACKAGES / PROCESS / CPU / NET
# =========================
def get_packages():
    """
    Detecta pacotes Roblox automaticamente.
    """
    # mais compatível que "pm list packages roblox" em alguns androids
    out = adb("pm list packages | grep -i roblox")
    pkgs = []
    for l in out.splitlines():
        l = l.strip()
        if l.startswith("package:"):
            pkg = l.replace("package:", "").strip()
            pkgs.append(pkg)
    pkgs = sorted(list(set(pkgs)))
    return pkgs


def get_pid(pkg):
    return adb(f"pidof {pkg}")


def get_cpu(pid):
    if not pid:
        return 0.0
    # tenta pegar linha do PID
    top = adb(f"top -n 1 -p {pid} | grep {pid}", timeout=6)
    if not top:
        return 0.0
    try:
        parts = top.split()
        # procurar parte com %
        for p in parts:
            if "%" in p:
                return float(p.replace("%", "").replace(",", "."))
    except:
        pass
    return 0.0


def get_uid(pkg):
    out = adb(f"dumpsys package {pkg} | grep userId=", timeout=8)
    m = re.search(r"userId=(\d+)", out)
    return m.group(1) if m else None


def get_network_bytes(uid):
    """
    Le /proc/net/xt_qtaguid/stats por UID.
    Muito mais compatível que /proc/uid_stat
    """
    if not uid:
        return 0
    try:
        out = adb(f"cat /proc/net/xt_qtaguid/stats | grep ' {uid} '", timeout=10)
        total = 0
        for line in out.splitlines():
            parts = line.split()
            # colunas comuns:
            # idx 5 = rx_bytes, idx 7 = tx_bytes (em muitos builds)
            if len(parts) > 7:
                rx_bytes = int(parts[5])
                tx_bytes = int(parts[7])
                total += rx_bytes + tx_bytes
        return total
    except:
        return 0


# =========================
# APP CONTROL
# =========================
def stop_app(pkg):
    adb(f"am force-stop {pkg}", timeout=8)


def close_browsers():
    if not CONFIG.get("close_browser_on_restart", True):
        return
    for b in CONFIG.get("browser_packages", []):
        if b:
            adb(f"am force-stop {b}", timeout=6)


def bring_to_focus(pkg):
    """
    Mais compatível e estável pra focar clones:
    monkey com launcher category.
    (Sim: monkey é imprevisível quando usado direto, mas com focus_lock + 1 de cada vez ele funciona bem.)
    """
    adb(f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1", timeout=10)
    time.sleep(FOCUS_DELAY)


def start_app_with_vip(pkg, vip_link):
    """
    Inicia com VIP. Tenta 2 métodos:
    1) ActivityProtocolLaunch (se existir no clone)
    2) VIEW normal (Android escolhe handler)
    """
    # tenta forçar activity correta
    out = adb(
        f"am start -n {pkg}/com.roblox.client.ActivityProtocolLaunch "
        f"-a android.intent.action.VIEW -d '{vip_link}'",
        timeout=12
    )
    # fallback se falhar
    if ("Error" in out) or ("Exception" in out):
        adb(f"am start -a android.intent.action.VIEW -d '{vip_link}'", timeout=12)
    time.sleep(2)


# =========================
# UI CHECK
# =========================
def get_ui_xml():
    adb("uiautomator dump /sdcard/re_phone_ui.xml >/dev/null 2>&1", timeout=12)
    time.sleep(0.3)
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
    ]
    return any(k in xl for k in keys)


# =========================
# Instance
# =========================
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

            # rede
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

            # online detect: CPU alta ou rede mexendo
            alive_by_net = self.net_delta >= NET_MIN_BYTES_ALIVE
            alive_by_cpu = self.cpu >= CPU_THRESHOLD_ACTIVE

            if alive_by_cpu or alive_by_net:
                self.status = "OK"
                self.suspect_count = 0
                self.needs_check = False
                return

            # suspeita só se CPU baixa e rede baixa
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


# =========================
# Monitor
# =========================
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
            # pega fila de checks
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
        self.log(f"🔍 Checando {inst.name}...")

        # se processo morreu mesmo -> restart sem focar
        with inst.lock:
            dead = (not inst.pid)

        if dead:
            self.log(f"💀 {inst.name}: PID morreu -> restart")
            inst.restart("Processo morto")
            inst.mark_checked()
            self.checking = ""
            time.sleep(3)
            return

        # focar
        bring_to_focus(inst.pkg)
        time.sleep(0.4)

        # dump UI
        xml = get_ui_xml()
        if not xml:
            self.log(f"⚠️ {inst.name}: UI vazia (dump falhou)")
            inst.mark_checked()
            self.checking = ""
            return

        if detect_disconnected(xml):
            self.log(f"📡 {inst.name}: disconnected/reconnect -> restart")
            send_webhook(CONFIG.get("webhook_url", ""), f"📡 **{inst.name}**: Disconnected/Reconnect!", screenshot=True)
            inst.restart("Disconnected/Reconnect")
        elif detect_home_screen(xml):
            self.log(f"🏠 {inst.name}: HOME -> restart")
            send_webhook(CONFIG.get("webhook_url", ""), f"🏠 **{inst.name}**: Tela HOME!", screenshot=True)
            inst.restart("Tela HOME")
        elif detect_key_screen(xml):
            self.log(f"🔑 {inst.name}: KEY detectada")
            send_webhook(CONFIG.get("webhook_url", ""), f"🔑 **{inst.name}**: Key detectada!", screenshot=True)
            # Aqui você pode adicionar auto-key depois. Por enquanto só alerta.
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

        # header
        vip_ok = "OK" if CONFIG.get("vip_link") else "NO"
        wh_ok = "OK" if CONFIG.get("webhook_url") else "NO"
        head = f"[bold red]RE_PHONE v9 FIX[/bold red] | VIP: [{ 'green' if vip_ok=='OK' else 'red'}]{vip_ok}[/{ 'green' if vip_ok=='OK' else 'red'}] | WEBHOOK: [{ 'green' if wh_ok=='OK' else 'red'}]{wh_ok}[/{ 'green' if wh_ok=='OK' else 'red'}]"
        layout["header"].update(Panel(Align.center(head), border_style="red", box=DOUBLE))

        # table
        t = Table(border_style="bright_red", expand=True, header_style="bold white on red", box=ROUNDED)
        t.add_column("INSTÂNCIA", width=14)
        t.add_column("PID", justify="center", width=8)
        t.add_column("CPU", justify="center", width=8)
        t.add_column("REDE Δ", justify="center", width=10)
        t.add_column("STATUS", justify="center", width=12)
        t.add_column("SUSP", justify="center", width=6)

        for inst in self.instances.values():
            with inst.lock:
                name = inst.name
                pid = inst.pid or "-"
                cpu = inst.cpu
                netd = inst.net_delta
                st = inst.status
                sc = inst.suspect_count

            if name == self.checking:
                name = f"[bold cyan]→ {name}[/bold cyan]"

            cpu_txt = f"[green]{cpu:.1f}%[/green]" if cpu >= CPU_THRESHOLD_ACTIVE else f"[yellow]{cpu:.1f}%[/yellow]" if cpu >= CPU_THRESHOLD_SUSPECT else f"[red]{cpu:.1f}%[/red]"
            net_txt = f"[green]{netd}[/green]" if netd >= NET_MIN_BYTES_ALIVE else f"[yellow]{netd}[/yellow]" if netd > 0 else f"[red]0[/red]"

            status_map = {
                "OK": "[bold green]ONLINE[/bold green]",
                "SYNC": "[bold blue]SYNC[/bold blue]",
                "LOW": "[bold yellow]LOW[/bold yellow]",
                "SUSPECT": "[bold red]SUSPECT[/bold red]",
                "DEAD": "[bold red]DEAD[/bold red]",
                "INIT": "[dim]INIT[/dim]",
            }
            st_txt = status_map.get(st, st)

            t.add_row(name, pid[:7], cpu_txt, net_txt, st_txt, f"[yellow]{sc}[/yellow]")

        layout["main"].update(Panel(t, title="[bold white on red] MONITOR [/bold white on red]", border_style="red", box=DOUBLE))

        logs = "\n".join(self.logs) if self.logs else "[dim]Aguardando eventos...[/dim]"
        layout["logs"].update(Panel(logs, title="[bold white on red] LOGS [/bold white on red]", border_style="red", box=ROUNDED))
        return layout

    def start(self):
        if not ensure_adb_ok():
            safe_print("[bold red]ADB não está OK (offline/unauthorized).[/bold red]")
            safe_print("Rode: [yellow]adb devices[/yellow] e confirme a permissão.")
            time.sleep(3)
            return

        vip = CONFIG.get("vip_link", "")
        if not vip:
            safe_print("[bold red]Configure o VIP Link primeiro![/bold red]")
            time.sleep(2)
            return

        force_portrait()

        pkgs = get_packages()
        if not pkgs:
            safe_print("[bold red]Nenhum pacote Roblox encontrado via ADB.[/bold red]")
            time.sleep(2)
            return

        self.instances = {}
        for pkg in pkgs:
            inst = Instance(pkg)
            self.instances[pkg] = inst
            self.log(f"✓ {inst.name} monitorando ({pkg})")

        self.running = True

        # workers
        for inst in self.instances.values():
            threading.Thread(target=self.passive_worker, args=(inst,), daemon=True).start()

        threading.Thread(target=self.focus_check_worker, daemon=True).start()

        with Live(self.render(), refresh_per_second=2, screen=True) as live:
            try:
                while self.running:
                    live.update(self.render())
                    time.sleep(0.5)
            except KeyboardInterrupt:
                self.running = False


monitor = Monitor()


# =========================
# MENUS
# =========================
def config_menu():
    global CONFIG
    console.clear()
    safe_print(Panel("[bold]CONFIGURAÇÕES[/bold]", border_style="red"))

    safe_print(f"[1] VIP Link: [dim]{(CONFIG.get('vip_link') or 'Não configurado')[:80]}[/dim]")
    safe_print(f"[2] Webhook: [dim]{(CONFIG.get('webhook_url') or 'Não configurado')[:80]}[/dim]")
    safe_print(f"[3] Fechar navegador no restart: [bold]{'SIM' if CONFIG.get('close_browser_on_restart', True) else 'NÃO'}[/bold]")
    safe_print("[0] Voltar")

    opt = Prompt.ask("Opção", choices=["1", "2", "3", "0"])
    if opt == "1":
        CONFIG["vip_link"] = Prompt.ask("Cole seu VIP Link (roblox:// ou https://)")
        save_config(CONFIG)
    elif opt == "2":
        CONFIG["webhook_url"] = Prompt.ask("Cole seu Webhook (opcional)", default=CONFIG.get("webhook_url", ""))
        save_config(CONFIG)
    elif opt == "3":
        CONFIG["close_browser_on_restart"] = not CONFIG.get("close_browser_on_restart", True)
        save_config(CONFIG)
        safe_print("[green]Alterado![/green]")
        time.sleep(1)


def tools_menu():
    console.clear()
    safe_print(Panel("[bold]FERRAMENTAS[/bold]", border_style="red"))

    safe_print("[1] Listar pacotes Roblox")
    safe_print("[2] Stop ALL Roblox")
    safe_print("[3] Start ALL Roblox (VIP)")
    safe_print("[4] Testar UI dump (foco atual)")
    safe_print("[0] Voltar")

    opt = Prompt.ask("Opção", choices=["1", "2", "3", "4", "0"])
    if opt == "1":
        pkgs = get_packages()
        safe_print(f"[yellow]Encontrados {len(pkgs)} pacotes:[/yellow]")
        for p in pkgs:
            safe_print(f"  - [green]{p}[/green] (PID: {get_pid(p) or 'N/A'})")
        Prompt.ask("Enter")
    elif opt == "2":
        pkgs = get_packages()
        for p in pkgs:
            stop_app(p)
        safe_print("[red]Todos parados.[/red]")
        time.sleep(1)
    elif opt == "3":
        vip = CONFIG.get("vip_link", "")
        if not vip:
            safe_print("[red]Configure VIP Link primeiro.[/red]")
            time.sleep(1)
            return
        pkgs = get_packages()
        for p in pkgs:
            start_app_with_vip(p, vip)
            time.sleep(1)
        safe_print("[green]Todos iniciados.[/green]")
        time.sleep(1)
    elif opt == "4":
        xml = get_ui_xml()
        safe_print(xml[:2000] if xml else "[red]UI dump vazio[/red]")
        Prompt.ask("Enter")


def main_menu():
    global CONFIG
    while True:
        console.clear()

        vip_ok = "✓" if CONFIG.get("vip_link") else "✗"
        wh_ok = "✓" if CONFIG.get("webhook_url") else "✗"

        banner = f"""
[bold red]RE_PHONE v9 FIX[/bold red]
[white]Auto Rejoin Roblox Clones (ADB/Termux)[/white]

VIP: [{'green' if vip_ok=='✓' else 'red'}]{vip_ok}[/{'green' if vip_ok=='✓' else 'red'}]   WEBHOOK: [{'green' if wh_ok=='✓' else 'red'}]{wh_ok}[/{'green' if wh_ok=='✓' else 'red'}]
"""
        safe_print(Panel(banner, border_style="red", box=DOUBLE))

        safe_print("[1] 🚀 Iniciar monitor")
        safe_print("[2] ⚙️ Configurações")
        safe_print("[3] 🛠️ Ferramentas")
        safe_print("[0] ❌ Sair")

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
