#!/usr/bin/env python3
import os, subprocess, time, requests, datetime, json, threading
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.align import Align
from rich import print as rprint

console = Console()
CONFIG_FILE = "config.json"

CHECK_INTERVAL = 3
COOLDOWN_TIME = 300          # 5 minutos
CPU_IDLE_LIMIT = 1.0        # CPU mínima aceitável
MAX_IDLE_CYCLES = 30        # 30 x 3s = 90s reais travado

# ================= CONFIG =================
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"vip_link": "", "webhook_url": ""}

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=4)

cfg = load_config()
VIP_LINK = cfg.get("vip_link", "")
WEBHOOK_URL = cfg.get("webhook_url", "")

# ================= ROBLOX INSTANCE =================
class RobloxInstance:
    def __init__(self, package, manager):
        self.package = package
        self.manager = manager
        self.pid = ""
        self.cpu = 0.0
        self.status = "INIT"
        self.last_action = "-"
        self.cooldown_until = 0
        self.idle_counter = 0
        self.running = True

    def adb(self, cmd):
        try:
            return subprocess.check_output(
                f"adb shell {cmd}",
                shell=True,
                stderr=subprocess.DEVNULL,
                timeout=4
            ).decode().strip()
        except:
            return ""

    def update_status(self):
        self.pid = self.adb(f"pidof {self.package}")

        if not self.pid:
            self.status = "BACKGROUND"
            self.cpu = 0.0
            return

        top = self.adb(f"top -n 1 -p {self.pid}")
        cpu = 0.0
        for line in top.splitlines():
            if self.pid in line:
                for part in line.split():
                    if "%" in part:
                        cpu = float(part.replace("%", "").replace(",", "."))
                        break
        self.cpu = cpu

        if time.time() < self.cooldown_until:
            self.status = "STABILIZING"
            return

        if self.cpu > CPU_IDLE_LIMIT:
            self.status = "RUNNING"
            self.idle_counter = 0
        else:
            self.status = "IDLE"
            self.idle_counter += 1

    def relaunch(self, reason):
        self.last_action = reason
        self.manager.log(f"{self.package} → RELAUNCH ({reason})")

        if WEBHOOK_URL:
            try:
                requests.post(WEBHOOK_URL, json={"content": f"🔄 **ROBLOX** `{self.package}` → {reason}"}, timeout=3)
            except:
                pass

        # ❌ SEM FORCE-STOP
        self.adb(f"am start -a android.intent.action.VIEW -d '{VIP_LINK}' {self.package}")
        self.cooldown_until = time.time() + COOLDOWN_TIME
        self.idle_counter = 0

    def loop(self):
        while self.running and self.manager.running:
            self.update_status()

            if self.status == "IDLE" and self.idle_counter >= MAX_IDLE_CYCLES:
                self.relaunch("Travado > 90s")

            time.sleep(CHECK_INTERVAL)

# ================= MANAGER =================
class RE_PHONE:
    def __init__(self):
        self.instances = {}
        self.running = False
        self.logs = []

    def log(self, msg):
        t = datetime.datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{t}] {msg}")
        if len(self.logs) > 8:
            self.logs.pop(0)

    def force_portrait(self):
        subprocess.run("adb shell settings put system accelerometer_rotation 0", shell=True)
        subprocess.run("adb shell settings put system user_rotation 0", shell=True)

    def start(self):
        if not VIP_LINK:
            rprint("[red]Configure o VIP LINK primeiro[/red]")
            time.sleep(2)
            return

        self.force_portrait()
        self.running = True

        try:
            out = subprocess.check_output("adb shell pm list packages | grep roblox", shell=True).decode()
            pkgs = [l.replace("package:", "").strip() for l in out.splitlines()]
        except:
            pkgs = []

        if not pkgs:
            rprint("[red]Nenhum Roblox encontrado[/red]")
            time.sleep(2)
            return

        for p in pkgs:
            inst = RobloxInstance(p, self)
            self.instances[p] = inst
            threading.Thread(target=inst.loop, daemon=True).start()

        with Live(self.render(), refresh_per_second=4, screen=True) as live:
            try:
                while self.running:
                    live.update(self.render())
                    time.sleep(0.25)
            except KeyboardInterrupt:
                self.running = False

    def render(self):
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body", size=12),
            Layout(name="footer", size=8)
        )

        layout["header"].update(
            Panel(Align.center(Text("RE_PHONE v7 SAFE – VS PHONE", style="bold red")), border_style="red")
        )

        table = Table(expand=True, border_style="red", header_style="bold red")
        table.add_column("PACOTE")
        table.add_column("CPU", justify="center")
        table.add_column("STATUS", justify="center")
        table.add_column("AÇÃO", justify="center")

        for inst in self.instances.values():
            color = "green" if inst.status == "RUNNING" else "yellow" if inst.status == "IDLE" else "cyan"
            table.add_row(
                inst.package.split(".")[-1],
                f"{inst.cpu:.1f}%",
                f"[{color}]{inst.status}[/{color}]",
                inst.last_action
            )

        layout["body"].update(Panel(table, title="MONITOR", border_style="red"))
        layout["footer"].update(Panel("\n".join(self.logs), title="LOGS", border_style="red"))
        return layout

# ================= MENU =================
manager = RE_PHONE()

def main():
    global VIP_LINK, WEBHOOK_URL

    while True:
        console.clear()
        rprint(Align.center("[bold red]RE_PHONE SAFE – VS PHONE[/bold red]\n"))

        rprint(Panel(f"VIP: {VIP_LINK[:40]}...\nWebhook: {'OK' if WEBHOOK_URL else 'OFF'}", border_style="red"))

        opt = Prompt.ask("1 Iniciar | 2 Config | 0 Sair", choices=["1", "2", "0"])

        if opt == "1":
            manager.start()

        elif opt == "2":
            VIP_LINK = Prompt.ask("VIP LINK", default=VIP_LINK)
            WEBHOOK_URL = Prompt.ask("Webhook", default=WEBHOOK_URL)
            save_config({"vip_link": VIP_LINK, "webhook_url": WEBHOOK_URL})

        elif opt == "0":
            break

if __name__ == "__main__":
    main()
