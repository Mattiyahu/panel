#!/usr/bin/env python3
"""
🖥️ TITANIYAHU - Roblox AutoRejoin (Termux/ADB) 🖥️
Tema cyberpunk/hacker + monitoramento avançado

Recursos:
- Detecta pacotes Roblox (clones) via ADB
- Detecta "caiu/travou" por: PID, CPU%, RSS (RAM do processo), internet (ping), RAM do dispositivo
- Auto-restart (force-stop + abrir link VIP) com cooldown + warmup
- Webhook opcional (Discord)
- Interface com animações (spinner/frames)

⚠️ Use apenas no seu próprio dispositivo e respeite as regras do Roblox/servidor.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# =========================
# ⚙️ CONFIG
# =========================
APP_NAME = "TITANIYAHU"
VERSION = "5.0"
CONFIG_FILE = "titaniyahu_config.json"

DEFAULT_CONFIG = {
    # Pode ser string ou lista (rotações). Ex: ["link1","link2"]
    "vip_links": [
        "https://www.roblox.com/games/1537690962/Bee-Swarm-Simulator?privateServerLinkCode=05888256464342538313491710978310"
    ],
    "webhook_url": "",
    "check_interval": 10,
    "cooldown_time": 12,
    "warmup_time": 20,                 # tempo após relançar antes de aplicar regras "baixa CPU/RAM"
    "low_cpu_threshold": 8.0,
    "max_lowcpu_time": 30,             # segundos com CPU baixa antes de reiniciar
    "min_rss_mb": 60,                  # RAM do processo (RSS) mínima aceitável (após warmup)
    "max_lowrss_time": 30,             # segundos com RSS baixo antes de reiniciar
    "device_low_mem_mb": 350,          # se MemAvailable ficar abaixo disso, reinicia apps para aliviar
    "device_low_mem_time": 30,         # segundos em baixa memória antes de ação
    "internet_fail_time": 25,          # segundos sem internet antes de tentar reabrir
    "ping_host": "1.1.1.1",
    "adb_serial": "",                  # opcional: serial do device (adb -s)
    "packages": []
}

# =========================
# 🎨 TEMA
# =========================
class Theme:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    BLINK = "\033[5m"

    MATRIX = "\033[38;5;46m"
    CYAN = "\033[38;5;51m"
    PINK = "\033[38;5;201m"
    PURPLE = "\033[38;5;93m"
    BLUE = "\033[38;5;39m"
    ORANGE = "\033[38;5;208m"
    RED = "\033[38;5;196m"
    YELLOW = "\033[38;5;226m"

    GREEN_DARK = "\033[38;5;22m"
    GREEN_MED = "\033[38;5;28m"
    GREEN_LIGHT = "\033[38;5;34m"
    GREEN_NEON = "\033[38;5;82m"

    BG_BLACK = "\033[48;5;232m"

    SUCCESS = f"{BOLD}{CYAN}"
    ERROR = f"{BOLD}{RED}"
    WARNING = f"{BOLD}{YELLOW}"
    INFO = f"{BOLD}{BLUE}"
    NEUTRAL = f"{GREEN_LIGHT}"

    SYMBOLS = {
        "terminal": "⌘",
        "pointer": "➤",
        "dot": "▪",
        "check": "✓",
        "cross": "✗",
        "warning": "⚠",
        "loading": "⌛",
        "radar": "📡",
    }

# =========================
# 🖥️ UI
# =========================
class UI:
    @staticmethod
    def clear():
        os.system("cls" if os.name == "nt" else "clear")

    @staticmethod
    def banner():
        UI.clear()
        w = 70
        print(f"\n{Theme.BG_BLACK}{Theme.MATRIX}{'▁'*w}{Theme.RESET}")
        print(f"{Theme.BG_BLACK}{Theme.MATRIX}╔{'═'*(w-2)}╗{Theme.RESET}")
        title = f"║ {Theme.BOLD}{Theme.CYAN}{APP_NAME}{Theme.RESET}{Theme.BG_BLACK}{Theme.MATRIX} • v{VERSION}"
        print(f"{Theme.BG_BLACK}{Theme.MATRIX}{title:<{w-1}}║{Theme.RESET}")
        sub = f"║ {Theme.GREEN_LIGHT}Roblox AutoRejoin • Termux/ADB Monitor{Theme.MATRIX}"
        print(f"{Theme.BG_BLACK}{Theme.MATRIX}{sub:<{w-1}}║{Theme.RESET}")
        print(f"{Theme.BG_BLACK}{Theme.MATRIX}╚{'═'*(w-2)}╝{Theme.RESET}")
        print(f"{Theme.BG_BLACK}{Theme.MATRIX}{'▔'*w}{Theme.RESET}\n")

    @staticmethod
    def log(pkg: str, msg: str, level: str = "INFO"):
        levels = {
            "INFO": Theme.INFO,
            "WARN": Theme.WARNING,
            "ERROR": Theme.ERROR,
            "SUCCESS": Theme.SUCCESS,
            "DEBUG": Theme.PURPLE,
        }
        color = levels.get(level, Theme.NEUTRAL)
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"{Theme.GREEN_DARK}[{Theme.CYAN}{ts}{Theme.GREEN_DARK}] "
              f"[{color}{level:<7}{Theme.GREEN_DARK}] "
              f"[{Theme.YELLOW}{pkg:<18}{Theme.GREEN_DARK}] "
              f"{Theme.GREEN_LIGHT}{msg}{Theme.RESET}")

    @staticmethod
    def box(title: str, content: str):
        lines = content.splitlines() or [""]
        max_len = max(len(l) for l in lines)
        cap = f"{Theme.CYAN}{title}{Theme.RESET}"
        print(f"{Theme.GREEN_DARK}┌─[{cap}{Theme.GREEN_DARK}]─{'─'*(max(0, max_len - len(title) + 6))}┐{Theme.RESET}")
        for l in lines:
            pad = " " * (max_len - len(l))
            print(f"{Theme.GREEN_DARK}│ {Theme.GREEN_LIGHT}{l}{pad} {Theme.GREEN_DARK}│{Theme.RESET}")
        print(f"{Theme.GREEN_DARK}└{'─'*(max_len + 4)}┘{Theme.RESET}")

    @staticmethod
    def spinner(text: str, seconds: float):
        frames = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
        end = time.time() + seconds
        i = 0
        while time.time() < end:
            print(f"\r{Theme.CYAN}{frames[i%len(frames)]}{Theme.RESET} {Theme.GREEN_LIGHT}{text}{Theme.RESET}", end="", flush=True)
            time.sleep(0.1)
            i += 1
        print()

# =========================
# 🔧 CONFIG IO
# =========================
def load_config() -> dict:
    cfg = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user = json.load(f)
            if isinstance(user, dict):
                cfg.update(user)
        except Exception as e:
            UI.log("CONFIG", f"Falha ao carregar config: {e}", "ERROR")
    # normaliza vip_links
    if isinstance(cfg.get("vip_links"), str):
        cfg["vip_links"] = [cfg["vip_links"]]
    if not cfg.get("vip_links"):
        cfg["vip_links"] = DEFAULT_CONFIG["vip_links"]
    return cfg

def save_config(cfg: dict) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

# =========================
# 📡 Webhook (Discord)
# =========================
def send_webhook(url: str, content: str) -> None:
    if not url:
        return
    payload = {"content": content}
    try:
        # tenta requests se existir
        try:
            import requests  # type: ignore
            requests.post(url, json=payload, timeout=6)
            return
        except Exception:
            pass

        import urllib.request
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=6).read()
    except Exception:
        return

# =========================
# 📱 ADB Wrapper
# =========================
class ADB:
    def __init__(self, serial: str = ""):
        self.serial = serial.strip()

    def _base(self) -> List[str]:
        cmd = ["adb"]
        if self.serial:
            cmd += ["-s", self.serial]
        return cmd

    def run(self, args: List[str], timeout: int = 10) -> Tuple[int, str, str]:
        try:
            p = subprocess.run(self._base() + args, capture_output=True, text=True, timeout=timeout)
            return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
        except FileNotFoundError:
            return 127, "", "adb not found"
        except subprocess.TimeoutExpired:
            return 124, "", "timeout"
        except Exception as e:
            return 1, "", str(e)

    def shell(self, cmd: str, timeout: int = 10) -> str:
        """
        Executa via: adb shell sh -c "<cmd>"
        (suporta pipes/quotes/& etc)
        """
        rc, out, _ = self.run(["shell", "sh", "-c", cmd], timeout=timeout)
        if rc != 0:
            return ""
        return out

    def ensure(self) -> bool:
        rc, out, _ = self.run(["devices"], timeout=8)
        if rc != 0:
            return False
        for line in out.splitlines():
            if "\tdevice" in line:
                return True
        return False

# =========================
# 📊 Helpers
# =========================
def parse_meminfo(meminfo: str) -> Tuple[Optional[int], Optional[int]]:
    """retorna (MemTotal_MB, MemAvailable_MB)"""
    total_kb = None
    avail_kb = None
    for line in meminfo.splitlines():
        if line.startswith("MemTotal:"):
            total_kb = int(re.findall(r"\d+", line)[0])
        elif line.startswith("MemAvailable:"):
            avail_kb = int(re.findall(r"\d+", line)[0])
    if total_kb is None:
        return None, None
    total_mb = total_kb // 1024
    avail_mb = (avail_kb // 1024) if avail_kb is not None else None
    return total_mb, avail_mb

def parse_vmrss_kb(status_txt: str) -> Optional[int]:
    for line in status_txt.splitlines():
        if line.startswith("VmRSS:"):
            nums = re.findall(r"\d+", line)
            if nums:
                return int(nums[0])
    return None

def safe_float(s: str, default: float = 0.0) -> float:
    try:
        return float(s)
    except Exception:
        return default

# =========================
# 🧠 Estado por pacote
# =========================
@dataclass
class ProcSample:
    last_proc_jiffies: int = 0
    last_total_jiffies: int = 0
    last_seen_pid: str = ""
    lowcpu_seconds: int = 0
    lowrss_seconds: int = 0
    last_launch_ts: float = 0.0
    cooldown_until: float = 0.0

# =========================
# 🎮 Monitor
# =========================
class TitaniyahuMonitor:
    def __init__(self, cfg: dict, adb: ADB):
        self.cfg = cfg
        self.adb = adb
        self.running = True
        self.samples: Dict[str, ProcSample] = {}

        self.proto_activity = "com.roblox.client.ActivityProtocolLaunch"
        self.internet_fail_seconds = 0
        self.low_mem_seconds = 0

        signal.signal(signal.SIGINT, self._sig)
        signal.signal(signal.SIGTERM, self._sig)

    def _sig(self, *_):
        UI.log("SYSTEM", "Interrupção detectada • encerrando...", "WARN")
        self.running = False

    # ---------- device checks ----------
    def device_mem(self) -> Tuple[Optional[int], Optional[int]]:
        mem = self.adb.shell("cat /proc/meminfo", timeout=6)
        return parse_meminfo(mem)

    def internet_ok(self) -> bool:
        host = str(self.cfg.get("ping_host", "1.1.1.1")).strip() or "1.1.1.1"

        # tenta variações de ping (Android varia)
        for cmd in (f"ping -c 1 -W 2 {host}", f"ping -c 1 -w 2 {host}", f"ping -c 1 {host}"):
            out = self.adb.shell(cmd, timeout=6)
            if not out:
                continue
            low = out.lower()
            if ("bytes from" in low and "time=" in low) or ("1 received" in low) or ("1 packets received" in low):
                return True
        return False

    # ---------- process checks ----------
    def get_pid(self, package: str) -> Optional[str]:
        pid = self.adb.shell(f"pidof {package}", timeout=6).strip()
        if not pid:
            return None
        return pid.split()[0]

    def read_total_jiffies(self) -> int:
        txt = self.adb.shell("cat /proc/stat", timeout=6)
        if not txt:
            return 0
        line = txt.splitlines()[0]
        parts = line.split()
        if len(parts) < 2:
            return 0
        nums = []
        for x in parts[1:]:
            try:
                nums.append(int(x))
            except Exception:
                pass
        return sum(nums) if nums else 0

    def read_proc_jiffies(self, pid: str) -> int:
        stat = self.adb.shell(f"cat /proc/{pid}/stat", timeout=6)
        parts = stat.split()
        if len(parts) < 16:
            return 0
        try:
            utime = int(parts[13])
            stime = int(parts[14])
            return utime + stime
        except Exception:
            return 0

    def cpu_percent(self, package: str, pid: str) -> float:
        sample = self.samples.setdefault(package, ProcSample())
        total = self.read_total_jiffies()
        proc = self.read_proc_jiffies(pid)
        if total <= 0 or proc <= 0:
            return 0.0

        if sample.last_total_jiffies <= 0 or sample.last_proc_jiffies <= 0 or sample.last_seen_pid != pid:
            sample.last_total_jiffies = total
            sample.last_proc_jiffies = proc
            sample.last_seen_pid = pid
            return 0.0

        dt = total - sample.last_total_jiffies
        dp = proc - sample.last_proc_jiffies
        sample.last_total_jiffies = total
        sample.last_proc_jiffies = proc
        sample.last_seen_pid = pid

        if dt <= 0 or dp < 0:
            return 0.0
        return max(0.0, min(100.0, (dp / dt) * 100.0))

    def rss_mb(self, pid: str) -> float:
        status_txt = self.adb.shell(f"cat /proc/{pid}/status", timeout=6)
        kb = parse_vmrss_kb(status_txt)
        if kb is None:
            return 0.0
        return kb / 1024.0

    # ---------- actions ----------
    def choose_vip_link(self) -> str:
        links = self.cfg.get("vip_links") or []
        if isinstance(links, str):
            links = [links]
        links = [l.strip() for l in links if isinstance(l, str) and l.strip()]
        if not links:
            links = DEFAULT_CONFIG["vip_links"]
        return links[int(time.time()) % len(links)]

    def open_vip(self, package: str) -> bool:
        link = self.choose_vip_link()

        # 1) VIEW com package-alvo (mais compatível)
        cmd_view_pkg = f"am start -a android.intent.action.VIEW -d '{link}' -p {package}"
        self.adb.shell(cmd_view_pkg, timeout=12)
        time.sleep(2.0)
        if self.get_pid(package):
            return True

        # 2) ActivityProtocolLaunch (se existir)
        cmd_proto = f"am start -n {package}/{self.proto_activity} -a android.intent.action.VIEW -d '{link}'"
        self.adb.shell(cmd_proto, timeout=12)
        time.sleep(2.5)
        if self.get_pid(package):
            return True

        # 3) fallback: VIEW sem -p
        cmd_view = f"am start -a android.intent.action.VIEW -d '{link}'"
        self.adb.shell(cmd_view, timeout=12)
        time.sleep(2.5)
        return self.get_pid(package) is not None

    def force_stop(self, package: str) -> None:
        self.adb.shell(f"am force-stop {package}", timeout=10)

    def soft_restart(self, package: str, reason: str = "") -> bool:
        now = time.time()
        sample = self.samples.setdefault(package, ProcSample())

        if now < sample.cooldown_until:
            UI.log(package, f"Cooldown ativo ({int(sample.cooldown_until-now)}s)", "WARN")
            return False

        UI.log(package, f"Reiniciando • motivo: {reason or 'n/a'}", "WARN")
        try:
            self.force_stop(package)
            time.sleep(1.6)

            ok = self.open_vip(package)

            sample.cooldown_until = time.time() + int(self.cfg.get("cooldown_time", 12))
            sample.last_launch_ts = time.time()
            sample.lowcpu_seconds = 0
            sample.lowrss_seconds = 0
            sample.last_proc_jiffies = 0
            sample.last_total_jiffies = 0
            sample.last_seen_pid = ""

            if ok:
                UI.log(package, "Rejoin OK (processo ativo)", "SUCCESS")
                send_webhook(self.cfg.get("webhook_url", ""), f"✅ {package} rejoin OK • motivo: {reason}")
            else:
                UI.log(package, "Rejoin pode ter falhado (sem PID)", "ERROR")
                send_webhook(self.cfg.get("webhook_url", ""), f"❌ {package} reinício falhou (sem PID) • motivo: {reason}")
            return ok
        except Exception as e:
            UI.log(package, f"Erro no reinício: {e}", "ERROR")
            return False

    # ---------- logic ----------
    def should_ignore_rules(self, package: str) -> bool:
        warm = int(self.cfg.get("warmup_time", 20))
        sample = self.samples.setdefault(package, ProcSample())
        if sample.last_launch_ts <= 0:
            return False
        return (time.time() - sample.last_launch_ts) < warm

    def tick_package(self, package: str, interval: int, internet_ok: bool, avail_mem_mb: Optional[int]) -> None:
        sample = self.samples.setdefault(package, ProcSample())
        pid = self.get_pid(package)

        if not pid:
            sample.lowcpu_seconds = 0
            sample.lowrss_seconds = 0
            UI.log(package, "PROCESSO OFFLINE", "ERROR")
            self.soft_restart(package, "processo offline")
            return

        cpu = self.cpu_percent(package, pid)
        rss = self.rss_mb(pid)

        if self.should_ignore_rules(package):
            UI.log(package, f"WARMUP • CPU {cpu:.1f}% • RSS {rss:.0f}MB", "INFO")
            return

        low_cpu = cpu <= float(self.cfg.get("low_cpu_threshold", 8.0))
        low_rss = rss <= float(self.cfg.get("min_rss_mb", 60))

        sample.lowcpu_seconds = sample.lowcpu_seconds + interval if low_cpu else 0
        sample.lowrss_seconds = sample.lowrss_seconds + interval if low_rss else 0

        if sample.lowcpu_seconds >= int(self.cfg.get("max_lowcpu_time", 30)):
            self.soft_restart(package, f"CPU baixa por {sample.lowcpu_seconds}s ({cpu:.1f}%)")
            return

        if sample.lowrss_seconds >= int(self.cfg.get("max_lowrss_time", 30)):
            self.soft_restart(package, f"RSS baixo por {sample.lowrss_seconds}s ({rss:.0f}MB)")
            return

        if not internet_ok and self.internet_fail_seconds >= int(self.cfg.get("internet_fail_time", 25)):
            self.soft_restart(package, "internet sem ping (rejoin)")
            return

        if avail_mem_mb is not None and avail_mem_mb <= int(self.cfg.get("device_low_mem_mb", 350)) \
           and self.low_mem_seconds >= int(self.cfg.get("device_low_mem_time", 30)):
            self.soft_restart(package, f"memória do dispositivo baixa ({avail_mem_mb}MB livre)")
            return

        cpu_color = Theme.GREEN_NEON if cpu > 20 else (Theme.CYAN if cpu > 8 else Theme.YELLOW)
        rss_color = Theme.CYAN if rss >= float(self.cfg.get("min_rss_mb", 60)) else Theme.YELLOW
        UI.log(package, f"OK • CPU {cpu_color}{cpu:.1f}%{Theme.RESET}{Theme.GREEN_LIGHT} • RSS {rss_color}{rss:.0f}MB{Theme.RESET}", "SUCCESS")

    def monitor_loop(self) -> None:
        if not self.adb.ensure():
            UI.log("ADB", "Nenhum device conectado. Rode: adb devices", "ERROR")
            return

        UI.banner()
        interval = int(self.cfg.get("check_interval", 10))
        pkgs = self.cfg.get("packages") or []

        UI.box("CONFIG", "\n".join([
            f"Intervalo: {interval}s",
            f"Cooldown: {self.cfg.get('cooldown_time')}s | Warmup: {self.cfg.get('warmup_time')}s",
            f"CPU baixa: <= {self.cfg.get('low_cpu_threshold')}% por {self.cfg.get('max_lowcpu_time')}s",
            f"RSS baixo: <= {self.cfg.get('min_rss_mb')}MB por {self.cfg.get('max_lowrss_time')}s",
            f"MemDevice baixa: <= {self.cfg.get('device_low_mem_mb')}MB por {self.cfg.get('device_low_mem_time')}s",
            f"Ping: {self.cfg.get('ping_host')}",
            f"Pacotes: {len(pkgs)}",
        ]))

        UI.spinner("Inicializando (rejoin) pacotes...", 1.2)
        for p in pkgs:
            self.soft_restart(p, "startup")
            time.sleep(0.8)

        cycle = 0
        while self.running:
            cycle += 1
            print(f"\n{Theme.GREEN_DARK}{'─'*62}{Theme.RESET}")
            print(f"{Theme.CYAN}{Theme.SYMBOLS['radar']} CICLO {cycle:04d} • {datetime.now().strftime('%H:%M:%S')} • SCAN{Theme.RESET}")
            print(f"{Theme.GREEN_DARK}{'─'*62}{Theme.RESET}\n")

            total_mb, avail_mb = self.device_mem()
            inet = self.internet_ok()

            if not inet:
                self.internet_fail_seconds += interval
                UI.log("NET", f"Sem ping ({self.internet_fail_seconds}s)", "WARN")
            else:
                if self.internet_fail_seconds >= interval:
                    UI.log("NET", "Ping OK (internet voltou)", "SUCCESS")
                self.internet_fail_seconds = 0

            if avail_mb is not None and avail_mb <= int(self.cfg.get("device_low_mem_mb", 350)):
                self.low_mem_seconds += interval
                UI.log("MEM", f"Memória baixa: {avail_mb}MB livres ({self.low_mem_seconds}s)", "WARN")
            else:
                self.low_mem_seconds = 0
                if avail_mb is not None and total_mb is not None:
                    UI.log("MEM", f"Memória OK: {avail_mb}MB livres de {total_mb}MB", "INFO")

            for p in pkgs:
                self.tick_package(p, interval=interval, internet_ok=inet, avail_mem_mb=avail_mb)

            for s in range(interval, 0, -1):
                warn = s <= 3
                t = f"{Theme.BLINK}{Theme.RED}{s:02d}s{Theme.RESET}" if warn else f"{s:02d}s"
                print(f"\r{Theme.GREEN_DARK}[{Theme.CYAN}AGUARDANDO{Theme.GREEN_DARK}] "
                      f"{Theme.GREEN_LIGHT}próximo scan em {t}{Theme.RESET}", end="", flush=True)
                time.sleep(1)
            print()

# =========================
# 🧭 Wizard / Menu
# =========================
def detect_roblox_packages(adb: ADB) -> List[str]:
    out = adb.shell("pm list packages", timeout=18)
    pkgs: List[str] = []
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("package:"):
            continue
        pkg = line.replace("package:", "").strip()
        if "roblox" in pkg.lower():
            pkgs.append(pkg)
    return sorted(set(pkgs))

def setup_wizard(cfg: dict, adb: ADB) -> dict:
    UI.banner()
    UI.log("WIZARD", "Configuração rápida", "INFO")

    current_serial = cfg.get("adb_serial", "")
    if current_serial:
        UI.log("ADB", f"Serial atual: {current_serial}", "INFO")
    s = input(f"{Theme.GREEN_LIGHT}Serial ADB (Enter p/ manter): {Theme.RESET}").strip()
    if s:
        cfg["adb_serial"] = s

    print(f"\n{Theme.INFO}Links VIP/Private Server (1 por linha). Vazio = manter.{Theme.RESET}")
    print(f"{Theme.DIM}Cole vários links e finalize com 'FIM'.{Theme.RESET}")
    new_links: List[str] = []
    while True:
        line = input(f"{Theme.GREEN_LIGHT}link> {Theme.RESET}").strip()
        if not line:
            if not new_links:
                break
            continue
        if line.upper() == "FIM":
            break
        new_links.append(line)
    if new_links:
        cfg["vip_links"] = new_links

    def ask_float(key: str, label: str):
        cur = cfg.get(key)
        val = input(f"{Theme.GREEN_LIGHT}{label} [{cur}]: {Theme.RESET}").strip()
        if val:
            cfg[key] = safe_float(val, float(cur))

    def ask_int(key: str, label: str):
        cur = cfg.get(key)
        val = input(f"{Theme.GREEN_LIGHT}{label} [{cur}]: {Theme.RESET}").strip()
        if val:
            try:
                cfg[key] = int(val)
            except Exception:
                pass

    print(f"\n{Theme.INFO}Configurações técnicas (Enter = manter){Theme.RESET}")
    ask_int("check_interval", "Intervalo de scan (s)")
    ask_int("cooldown_time", "Cooldown (s)")
    ask_int("warmup_time", "Warmup após relançar (s)")
    ask_float("low_cpu_threshold", "CPU baixa (<= %)")

    ask_int("max_lowcpu_time", "Tempo CPU baixa (s) p/ restart")
    ask_int("min_rss_mb", "RSS mínimo (MB)")
    ask_int("max_lowrss_time", "Tempo RSS baixo (s) p/ restart")

    ask_int("device_low_mem_mb", "MemAvailable mínima do device (MB)")
    ask_int("device_low_mem_time", "Tempo em memória baixa (s) p/ ação")

    ask_int("internet_fail_time", "Tempo sem ping (s) p/ rejoin")
    ping = input(f"{Theme.GREEN_LIGHT}Host p/ ping [{cfg.get('ping_host')}]: {Theme.RESET}").strip()
    if ping:
        cfg["ping_host"] = ping

    webhook = input(f"{Theme.GREEN_LIGHT}Webhook Discord (Enter p/ manter): {Theme.RESET}").strip()
    if webhook:
        cfg["webhook_url"] = webhook

    # aplica serial novo no adb local do wizard
    adb = ADB(cfg.get("adb_serial", ""))

    if adb.ensure():
        if input(f"\n{Theme.GREEN_LIGHT}Detectar pacotes Roblox agora? (s/n): {Theme.RESET}").lower().startswith("s"):
            UI.spinner("Detectando pacotes...", 1.0)
            pkgs = detect_roblox_packages(adb)
            if pkgs:
                cfg["packages"] = pkgs
                UI.box("PACOTES", "\n".join(pkgs))
                UI.log("WIZARD", f"{len(pkgs)} pacotes salvos", "SUCCESS")
            else:
                UI.log("WIZARD", "Nenhum pacote Roblox encontrado", "ERROR")
    else:
        UI.log("ADB", "Sem device conectado; pulei detecção.", "WARN")

    save_config(cfg)
    UI.log("CONFIG", "Configuração salva", "SUCCESS")
    return cfg

def interactive_menu(cfg: dict) -> None:
    adb = ADB(cfg.get("adb_serial", ""))
    while True:
        UI.banner()
        pkgs = cfg.get("packages") or []
        UI.box("STATUS", "\n".join([
            f"Device conectado: {'SIM' if adb.ensure() else 'NÃO'}",
            f"Pacotes: {len(pkgs)}",
            f"Intervalo: {cfg.get('check_interval')}s | Cooldown: {cfg.get('cooldown_time')}s",
            f"CPU baixa: <= {cfg.get('low_cpu_threshold')}% ({cfg.get('max_lowcpu_time')}s)",
            f"RSS mínimo: {cfg.get('min_rss_mb')}MB ({cfg.get('max_lowrss_time')}s)",
            f"Ping host: {cfg.get('ping_host')}",
        ]))

        print(f"{Theme.GREEN_DARK}┌─[{Theme.CYAN}MENU{Theme.GREEN_DARK}]─{'─'*52}┐{Theme.RESET}")
        print(f"{Theme.GREEN_DARK}│ {Theme.CYAN}1{Theme.GREEN_DARK} {Theme.SYMBOLS['pointer']} {Theme.GREEN_LIGHT}Iniciar monitoramento{Theme.RESET}")
        print(f"{Theme.GREEN_DARK}│ {Theme.CYAN}2{Theme.GREEN_DARK} {Theme.SYMBOLS['pointer']} {Theme.GREEN_LIGHT}Configurar (wizard){Theme.RESET}")
        print(f"{Theme.GREEN_DARK}│ {Theme.CYAN}3{Theme.GREEN_DARK} {Theme.SYMBOLS['pointer']} {Theme.GREEN_LIGHT}Detectar pacotes Roblox{Theme.RESET}")
        print(f"{Theme.GREEN_DARK}│ {Theme.CYAN}4{Theme.GREEN_DARK} {Theme.SYMBOLS['pointer']} {Theme.GREEN_LIGHT}Testar ADB / devices{Theme.RESET}")
        print(f"{Theme.GREEN_DARK}│ {Theme.CYAN}5{Theme.GREEN_DARK} {Theme.SYMBOLS['pointer']} {Theme.GREEN_LIGHT}Executar tudo (auto){Theme.RESET}")
        print(f"{Theme.GREEN_DARK}│ {Theme.CYAN}6{Theme.GREEN_DARK} {Theme.SYMBOLS['pointer']} {Theme.RED}Sair{Theme.RESET}")
        print(f"{Theme.GREEN_DARK}└{'─'*60}┘{Theme.RESET}")

        ch = input(f"\n{Theme.CYAN}{Theme.SYMBOLS['terminal']} {Theme.BOLD}Escolha (1-6): {Theme.RESET}").strip()
        if ch == "1":
            if not pkgs:
                UI.log("SYSTEM", "Nenhum pacote configurado. Use 'Detectar pacotes' ou wizard.", "ERROR")
                input(f"{Theme.GREEN_LIGHT}Enter...{Theme.RESET}")
                continue
            mon = TitaniyahuMonitor(cfg, adb)
            mon.monitor_loop()
            input(f"{Theme.GREEN_LIGHT}Enter para voltar ao menu...{Theme.RESET}")

        elif ch == "2":
            cfg = setup_wizard(cfg, adb)
            adb = ADB(cfg.get("adb_serial", ""))
            input(f"{Theme.GREEN_LIGHT}Enter...{Theme.RESET}")

        elif ch == "3":
            if not adb.ensure():
                UI.log("ADB", "Sem device conectado.", "ERROR")
            else:
                UI.spinner("Detectando pacotes...", 0.9)
                pkgs = detect_roblox_packages(adb)
                if pkgs:
                    cfg["packages"] = pkgs
                    save_config(cfg)
                    UI.box("PACOTES", "\n".join(pkgs))
                    UI.log("SYSTEM", f"{len(pkgs)} pacotes salvos", "SUCCESS")
                else:
                    UI.log("SYSTEM", "Nenhum pacote Roblox encontrado", "ERROR")
            input(f"{Theme.GREEN_LIGHT}Enter...{Theme.RESET}")

        elif ch == "4":
            UI.spinner("Testando ADB...", 0.9)
            rc, out, err = adb.run(["devices"], timeout=10)
            UI.box("ADB DEVICES", out or err or "(vazio)")
            input(f"{Theme.GREEN_LIGHT}Enter...{Theme.RESET}")

        elif ch == "5":
            if adb.ensure():
                pkgs = detect_roblox_packages(adb)
                if pkgs:
                    cfg["packages"] = pkgs
                    save_config(cfg)
                    UI.log("AUTO", f"{len(pkgs)} pacotes detectados e salvos", "SUCCESS")
                    mon = TitaniyahuMonitor(cfg, adb)
                    mon.monitor_loop()
                else:
                    UI.log("AUTO", "Nenhum pacote Roblox detectado", "ERROR")
            else:
                UI.log("AUTO", "Sem device conectado", "ERROR")
            input(f"{Theme.GREEN_LIGHT}Enter...{Theme.RESET}")

        elif ch == "6":
            UI.log("SYSTEM", "Encerrando. Até mais!", "SUCCESS")
            sys.exit(0)

        else:
            UI.log("INPUT", "Opção inválida", "ERROR")
            time.sleep(1)

# =========================
# 🚀 CLI
# =========================
def parse_args():
    p = argparse.ArgumentParser(prog="titaniyahu", add_help=True)
    p.add_argument("--auto", action="store_true", help="Detecta pacotes e inicia monitoramento (sem menu).")
    p.add_argument("--monitor", action="store_true", help="Inicia monitoramento com pacotes do config (sem menu).")
    p.add_argument("--detect", action="store_true", help="Detecta pacotes Roblox e salva no config.")
    p.add_argument("--config", action="store_true", help="Abre wizard de configuração.")
    p.add_argument("--serial", type=str, default="", help="Serial ADB (equivalente a adb -s).")
    return p.parse_args()

def main():
    cfg = load_config()
    args = parse_args()

    if args.serial.strip():
        cfg["adb_serial"] = args.serial.strip()
        save_config(cfg)

    adb = ADB(cfg.get("adb_serial", ""))

    if args.config:
        setup_wizard(cfg, adb)
        return

    if args.detect:
        if not adb.ensure():
            UI.log("ADB", "Sem device conectado (adb devices).", "ERROR")
            return
        pkgs = detect_roblox_packages(adb)
        if pkgs:
            cfg["packages"] = pkgs
            save_config(cfg)
            UI.box("PACOTES", "\n".join(pkgs))
            UI.log("SYSTEM", f"{len(pkgs)} pacotes salvos em {CONFIG_FILE}", "SUCCESS")
        else:
            UI.log("SYSTEM", "Nenhum pacote Roblox encontrado", "ERROR")
        return

    if args.auto:
        if not adb.ensure():
            UI.log("ADB", "Sem device conectado (adb devices).", "ERROR")
            return
        pkgs = detect_roblox_packages(adb)
        if not pkgs:
            UI.log("AUTO", "Nenhum pacote Roblox detectado", "ERROR")
            return
        cfg["packages"] = pkgs
        save_config(cfg)
        mon = TitaniyahuMonitor(cfg, adb)
        mon.monitor_loop()
        return

    if args.monitor:
        if not cfg.get("packages"):
            UI.log("SYSTEM", "Config sem pacotes. Rode --detect ou --auto.", "ERROR")
            return
        mon = TitaniyahuMonitor(cfg, adb)
        mon.monitor_loop()
        return

    interactive_menu(cfg)

if __name__ == "__main__":
    main()
