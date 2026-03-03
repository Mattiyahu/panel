#!/usr/bin/env python3
"""
🖥️ TITANIYAHU - Roblox AutoRejoin (Termux/ADB) 🖥️
v5.1 - Auto ADB + Detecção sem ADB + Monitor FULL/LITE

FULL (com ADB conectado):
- Detecta PID
- Calcula CPU% por /proc
- RSS (RAM do processo)
- force-stop + abrir link VIP

LITE (sem ADB):
- Detecta pacotes via pm local
- Ping + MemAvailable do device local
- Tenta reconectar ADB automaticamente
- Pode abrir VIP link local (sem force-stop)

⚠️ Observação:
- Para CPU/RSS/force-stop funcionar, precisa ADB conectado (Wireless Debugging ou USB).
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
VERSION = "5.1"
CONFIG_FILE = "titaniyahu_config.json"

DEFAULT_CONFIG = {
    "vip_links": [
        "https://www.roblox.com/games/1537690962/Bee-Swarm-Simulator?privateServerLinkCode=05888256464342538313491710978310"
    ],
    "webhook_url": "",

    "check_interval": 10,
    "cooldown_time": 12,
    "warmup_time": 20,

    "low_cpu_threshold": 8.0,
    "max_lowcpu_time": 30,

    "min_rss_mb": 60,
    "max_lowrss_time": 30,

    "device_low_mem_mb": 350,
    "device_low_mem_time": 30,

    "internet_fail_time": 25,
    "ping_host": "1.1.1.1",

    # ADB auto
    "adb": {
        "serial": "",                # opcional: adb -s <serial>
        "auto_connect": True,        # tenta reconectar sozinho
        "connect_target": "",        # ex: "127.0.0.1:5555" ou "192.168.0.10:5555"
        "pair_target": "",           # ex: "127.0.0.1:37123"
    },

    "packages": [],

    # LITE behavior (sem ADB)
    "lite_open_vip_on_internet_return": False,  # se internet voltar, tenta abrir VIP link local
    "lite_open_vip_every_min": 0,               # 0 = nunca; ex: 10 = tenta abrir vip a cada 10 min (sem force-stop)
}

# =========================
# 🎨 TEMA
# =========================
class Theme:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    BLINK = "\033[5m"

    MATRIX = "\033[38;5;46m"
    CYAN = "\033[38;5;51m"
    PURPLE = "\033[38;5;93m"
    BLUE = "\033[38;5;39m"
    RED = "\033[38;5;196m"
    YELLOW = "\033[38;5;226m"

    GREEN_DARK = "\033[38;5;22m"
    GREEN_LIGHT = "\033[38;5;34m"
    GREEN_NEON = "\033[38;5;82m"

    BG_BLACK = "\033[48;5;232m"

    SUCCESS = f"{BOLD}{CYAN}"
    ERROR = f"{BOLD}{RED}"
    WARNING = f"{BOLD}{YELLOW}"
    INFO = f"{BOLD}{BLUE}"

    SYMBOLS = {
        "terminal": "⌘",
        "pointer": "➤",
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
        w = 72
        print(f"\n{Theme.BG_BLACK}{Theme.MATRIX}{'▁'*w}{Theme.RESET}")
        print(f"{Theme.BG_BLACK}{Theme.MATRIX}╔{'═'*(w-2)}╗{Theme.RESET}")
        title = f"║ {Theme.BOLD}{Theme.CYAN}{APP_NAME}{Theme.RESET}{Theme.BG_BLACK}{Theme.MATRIX} • v{VERSION}"
        print(f"{Theme.BG_BLACK}{Theme.MATRIX}{title:<{w-1}}║{Theme.RESET}")
        sub = f"║ {Theme.GREEN_LIGHT}Roblox AutoRejoin • Termux/ADB • FULL/LITE Monitor{Theme.MATRIX}"
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
        color = levels.get(level, Theme.GREEN_LIGHT)
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
# 🔧 Local shell (Termux)
# =========================
def local_shell(cmd: str, timeout: int = 18) -> Tuple[int, str, str]:
    try:
        p = subprocess.run(["sh", "-lc", cmd], capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as e:
        return 1, "", str(e)

# =========================
# 🔧 CONFIG IO
# =========================
def load_config() -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # deep-ish copy
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user = json.load(f)
            if isinstance(user, dict):
                # merge simples
                cfg.update({k: v for k, v in user.items() if k != "adb"})
                if isinstance(user.get("adb"), dict):
                    cfg["adb"].update(user["adb"])
        except Exception as e:
            UI.log("CONFIG", f"Falha ao carregar config: {e}", "ERROR")

    # normalize vip_links
    if isinstance(cfg.get("vip_links"), str):
        cfg["vip_links"] = [cfg["vip_links"]]
    if not cfg.get("vip_links"):
        cfg["vip_links"] = DEFAULT_CONFIG["vip_links"]
    return cfg

def save_config(cfg: dict) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

# =========================
# 📡 Webhook (opcional)
# =========================
def send_webhook(url: str, content: str) -> None:
    if not url:
        return
    payload = {"content": content}
    try:
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
# 📱 ADB Wrapper + Auto Connect
# =========================
class ADB:
    def __init__(self, adb_cfg: dict):
        self.cfg = adb_cfg or {}

    def _base(self) -> List[str]:
        cmd = ["adb"]
        serial = (self.cfg.get("serial") or "").strip()
        if serial:
            cmd += ["-s", serial]
        return cmd

    def run(self, args: List[str], timeout: int = 12) -> Tuple[int, str, str]:
        try:
            p = subprocess.run(self._base() + args, capture_output=True, text=True, timeout=timeout)
            return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
        except FileNotFoundError:
            return 127, "", "adb not found"
        except subprocess.TimeoutExpired:
            return 124, "", "timeout"
        except Exception as e:
            return 1, "", str(e)

    def shell(self, cmd: str, timeout: int = 12) -> str:
        rc, out, _ = self.run(["shell", "sh", "-c", cmd], timeout=timeout)
        if rc != 0:
            return ""
        return out

    def devices(self) -> str:
        rc, out, err = self.run(["devices"], timeout=10)
        return out or err or ""

    def start_server(self) -> bool:
        rc, _, _ = self.run(["start-server"], timeout=10)
        return rc == 0

    def connect(self, target: str) -> bool:
        target = (target or "").strip()
        if not target:
            return False
        rc, out, err = self.run(["connect", target], timeout=12)
        txt = (out + "\n" + err).lower()
        return rc == 0 and ("connected" in txt or "already connected" in txt)

    def pair(self, target: str, code: str) -> bool:
        target = (target or "").strip()
        code = (code or "").strip()
        if not target or not code:
            return False
        # adb pair host:port code  (não-interativo)
        rc, out, err = self.run(["pair", target, code], timeout=18)
        txt = (out + "\n" + err).lower()
        return rc == 0 and ("success" in txt or "paired" in txt)

    def is_connected(self) -> bool:
        out = self.devices()
        for line in out.splitlines():
            if "\tdevice" in line:
                return True
        return False

    def ensure(self) -> bool:
        """Garante conexão. Se auto_connect ligado e connect_target setado, tenta conectar."""
        if self.is_connected():
            return True

        if not self.cfg.get("auto_connect", True):
            return False

        self.start_server()

        target = (self.cfg.get("connect_target") or "").strip()
        if target:
            self.connect(target)
            time.sleep(0.2)

        return self.is_connected()

# =========================
# 📊 Helpers
# =========================
def parse_meminfo(meminfo: str) -> Tuple[Optional[int], Optional[int]]:
    total_kb = None
    avail_kb = None
    for line in meminfo.splitlines():
        if line.startswith("MemTotal:"):
            m = re.findall(r"\d+", line)
            if m:
                total_kb = int(m[0])
        if line.startswith("MemAvailable:"):
            m = re.findall(r"\d+", line)
            if m:
                avail_kb = int(m[0])
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
# 📦 Detect packages (ADB or Termux)
# =========================
def detect_roblox_packages(adb: ADB) -> List[str]:
    out = ""
    # tenta ADB primeiro
    if adb.ensure():
        out = adb.shell("pm list packages -3", timeout=18)

    # fallback local Termux
    if not out:
        _, out, _ = local_shell("pm list packages -3", timeout=18)

    pkgs: List[str] = []
    patterns = re.compile(r"(roblox|rblx|blox|rbx)", re.IGNORECASE)

    for line in (out or "").splitlines():
        line = line.strip()
        if not line.startswith("package:"):
            continue
        pkg = line.replace("package:", "").strip()
        if patterns.search(pkg):
            pkgs.append(pkg)

    return sorted(set(pkgs))

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

        self.internet_fail_seconds = 0
        self.low_mem_seconds = 0
        self.last_lite_open_ts = 0.0

        signal.signal(signal.SIGINT, self._sig)
        signal.signal(signal.SIGTERM, self._sig)

    def _sig(self, *_):
        UI.log("SYSTEM", "Interrupção detectada • encerrando...", "WARN")
        self.running = False

    # ---------- device checks ----------
    def device_mem(self) -> Tuple[Optional[int], Optional[int]]:
        if self.adb.ensure():
            mem = self.adb.shell("cat /proc/meminfo", timeout=6)
            return parse_meminfo(mem)
        # local
        _, mem, _ = local_shell("cat /proc/meminfo", timeout=6)
        return parse_meminfo(mem)

    def internet_ok(self) -> bool:
        host = str(self.cfg.get("ping_host", "1.1.1.1")).strip() or "1.1.1.1"

        cmds = (f"ping -c 1 -W 2 {host}", f"ping -c 1 -w 2 {host}", f"ping -c 1 {host}")
        if self.adb.ensure():
            for c in cmds:
                out = self.adb.shell(c, timeout=6)
                if self._ping_ok(out):
                    return True
            return False

        for c in cmds:
            _, out, _ = local_shell(c, timeout=6)
            if self._ping_ok(out):
                return True
        return False

    @staticmethod
    def _ping_ok(out: str) -> bool:
        if not out:
            return False
        low = out.lower()
        return ("bytes from" in low and "time=" in low) or ("1 received" in low) or ("1 packets received" in low)

    # ---------- process checks (FULL only) ----------
    def get_pid(self, package: str) -> Optional[str]:
        if not self.adb.ensure():
            return None
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

        if self.adb.ensure():
            # via ADB
            self.adb.shell(f"am start -a android.intent.action.VIEW -d '{link}' -p {package}", timeout=14)
            time.sleep(2.0)
            return self.get_pid(package) is not None

        # LITE local: tenta abrir (não garante)
        rc, out, err = local_shell(f"am start -a android.intent.action.VIEW -d '{link}' -p {package}", timeout=14)
        return rc == 0 and ("error" not in (out + err).lower())

    def force_stop(self, package: str) -> bool:
        if not self.adb.ensure():
            return False
        self.adb.shell(f"am force-stop {package}", timeout=10)
        time.sleep(0.2)
        return True

    def soft_restart(self, package: str, reason: str = "") -> bool:
        now = time.time()
        sample = self.samples.setdefault(package, ProcSample())

        if now < sample.cooldown_until:
            UI.log(package, f"Cooldown ativo ({int(sample.cooldown_until-now)}s)", "WARN")
            return False

        if self.adb.ensure():
            UI.log(package, f"Reiniciando FULL • motivo: {reason or 'n/a'}", "WARN")
            self.force_stop(package)
            time.sleep(1.3)
            ok = self.open_vip(package)
        else:
            UI.log(package, f"Reiniciando LITE (sem force-stop) • motivo: {reason or 'n/a'}", "WARN")
            ok = self.open_vip(package)

        sample.cooldown_until = time.time() + int(self.cfg.get("cooldown_time", 12))
        sample.last_launch_ts = time.time()
        sample.lowcpu_seconds = 0
        sample.lowrss_seconds = 0
        sample.last_proc_jiffies = 0
        sample.last_total_jiffies = 0
        sample.last_seen_pid = ""

        if ok:
            UI.log(package, "Rejoin OK", "SUCCESS")
            send_webhook(self.cfg.get("webhook_url", ""), f"✅ {package} rejoin OK • motivo: {reason}")
        else:
            UI.log(package, "Rejoin pode ter falhado", "ERROR")
            send_webhook(self.cfg.get("webhook_url", ""), f"❌ {package} rejoin falhou • motivo: {reason}")
        return ok

    # ---------- rules ----------
    def should_ignore_rules(self, package: str) -> bool:
        warm = int(self.cfg.get("warmup_time", 20))
        sample = self.samples.setdefault(package, ProcSample())
        return sample.last_launch_ts > 0 and (time.time() - sample.last_launch_ts) < warm

    def tick_package_full(self, package: str, interval: int, internet_ok: bool,
                          avail_mem_mb: Optional[int]) -> None:
        sample = self.samples.setdefault(package, ProcSample())
        pid = self.get_pid(package)

        if not pid:
            sample.lowcpu_seconds = 0
            sample.lowrss_seconds = 0
            UI.log(package, "PROCESSO OFFLINE (FULL)", "ERROR")
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
            self.soft_restart(package, f"memória baixa do device ({avail_mem_mb}MB livre)")
            return

        cpu_color = Theme.GREEN_NEON if cpu > 20 else (Theme.CYAN if cpu > 8 else Theme.YELLOW)
        rss_color = Theme.CYAN if rss >= float(self.cfg.get("min_rss_mb", 60)) else Theme.YELLOW
        UI.log(package, f"OK • CPU {cpu_color}{cpu:.1f}%{Theme.RESET}{Theme.GREEN_LIGHT} • RSS {rss_color}{rss:.0f}MB{Theme.RESET}", "SUCCESS")

    def tick_package_lite(self, package: str) -> None:
        # sem ADB, não dá para PID/CPU/RSS com segurança.
        UI.log(package, "LITE • sem métricas do processo (conecte ADB p/ FULL)", "WARN")

    def monitor_loop(self) -> None:
        UI.banner()

        pkgs = self.cfg.get("packages") or []
        interval = int(self.cfg.get("check_interval", 10))

        if not pkgs:
            UI.log("SYSTEM", "Nenhum pacote configurado. Use Detectar Pacotes.", "ERROR")
            return

        UI.box("CONFIG", "\n".join([
            f"Intervalo: {interval}s | Cooldown: {self.cfg.get('cooldown_time')}s | Warmup: {self.cfg.get('warmup_time')}s",
            f"CPU baixa: <= {self.cfg.get('low_cpu_threshold')}% por {self.cfg.get('max_lowcpu_time')}s (FULL)",
            f"RSS baixo: <= {self.cfg.get('min_rss_mb')}MB por {self.cfg.get('max_lowrss_time')}s (FULL)",
            f"MemDevice baixa: <= {self.cfg.get('device_low_mem_mb')}MB por {self.cfg.get('device_low_mem_time')}s",
            f"Ping: {self.cfg.get('ping_host')}",
            f"ADB auto_connect: {self.cfg.get('adb', {}).get('auto_connect', True)}",
            f"ADB connect_target: {self.cfg.get('adb', {}).get('connect_target', '') or '(vazio)'}",
            f"Pacotes: {len(pkgs)}",
        ]))

        UI.spinner("Inicializando (rejoin) pacotes...", 1.2)
        for p in pkgs:
            self.soft_restart(p, "startup")
            time.sleep(0.6)

        cycle = 0
        while self.running:
            cycle += 1
            adb_ok = self.adb.ensure()

            print(f"\n{Theme.GREEN_DARK}{'─'*64}{Theme.RESET}")
            mode = "FULL" if adb_ok else "LITE"
            print(f"{Theme.CYAN}{Theme.SYMBOLS['radar']} CICLO {cycle:04d} • {datetime.now().strftime('%H:%M:%S')} • MODE={mode}{Theme.RESET}")
            print(f"{Theme.GREEN_DARK}{'─'*64}{Theme.RESET}\n")

            total_mb, avail_mb = self.device_mem()
            inet = self.internet_ok()

            # Internet
            if not inet:
                self.internet_fail_seconds += interval
                UI.log("NET", f"Sem ping ({self.internet_fail_seconds}s)", "WARN")
            else:
                if self.internet_fail_seconds >= interval:
                    UI.log("NET", "Ping OK (internet voltou)", "SUCCESS")
                    if (not adb_ok) and self.cfg.get("lite_open_vip_on_internet_return", False):
                        for p in pkgs:
                            self.open_vip(p)
                            time.sleep(0.3)
                self.internet_fail_seconds = 0

            # Memória do device
            if avail_mb is not None and avail_mb <= int(self.cfg.get("device_low_mem_mb", 350)):
                self.low_mem_seconds += interval
                UI.log("MEM", f"Memória baixa: {avail_mb}MB livres ({self.low_mem_seconds}s)", "WARN")
            else:
                self.low_mem_seconds = 0
                if avail_mb is not None and total_mb is not None:
                    UI.log("MEM", f"Memória OK: {avail_mb}MB livres de {total_mb}MB", "INFO")

            # ADB status hint
            if not adb_ok:
                UI.log("ADB", "OFFLINE • tentando reconectar automaticamente...", "WARN")
                UI.log("ADB", "Dica: configure 'adb.connect_target' no wizard (Wireless Debugging).", "INFO")

            # LITE periodic open
            lite_every = int(self.cfg.get("lite_open_vip_every_min", 0) or 0)
            if (not adb_ok) and lite_every > 0:
                if time.time() - self.last_lite_open_ts > lite_every * 60:
                    UI.log("LITE", f"Tentando abrir VIP (a cada {lite_every} min)", "WARN")
                    for p in pkgs:
                        self.open_vip(p)
                        time.sleep(0.3)
                    self.last_lite_open_ts = time.time()

            # Tick packages
            for p in pkgs:
                if adb_ok:
                    self.tick_package_full(p, interval=interval, internet_ok=inet, avail_mem_mb=avail_mb)
                else:
                    self.tick_package_lite(p)

            # Countdown
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
def setup_wizard(cfg: dict) -> dict:
    UI.banner()
    UI.log("WIZARD", "Configuração rápida", "INFO")

    # ADB section
    adb_cfg = cfg.get("adb", {})
    UI.box("ADB", "\n".join([
        f"serial: {adb_cfg.get('serial') or '(vazio)'}",
        f"auto_connect: {adb_cfg.get('auto_connect', True)}",
        f"connect_target: {adb_cfg.get('connect_target') or '(vazio)'}",
        f"pair_target: {adb_cfg.get('pair_target') or '(vazio)'}",
    ]))

    s = input(f"{Theme.GREEN_LIGHT}ADB serial (Enter p/ manter): {Theme.RESET}").strip()
    if s:
        adb_cfg["serial"] = s

    ac = input(f"{Theme.GREEN_LIGHT}Auto conectar ADB? (s/n) [{ 's' if adb_cfg.get('auto_connect', True) else 'n' }]: {Theme.RESET}").strip().lower()
    if ac in ("s", "n"):
        adb_cfg["auto_connect"] = (ac == "s")

    ct = input(f"{Theme.GREEN_LIGHT}ADB connect_target (ex 127.0.0.1:5555) (Enter p/ manter): {Theme.RESET}").strip()
    if ct:
        adb_cfg["connect_target"] = ct

    pt = input(f"{Theme.GREEN_LIGHT}ADB pair_target (ex 127.0.0.1:37123) (Enter p/ manter): {Theme.RESET}").strip()
    if pt:
        adb_cfg["pair_target"] = pt

    cfg["adb"] = adb_cfg
    adb = ADB(cfg["adb"])

    # Pair now?
    if adb_cfg.get("pair_target") and input(f"\n{Theme.GREEN_LIGHT}Quer PAREAR agora? (s/n): {Theme.RESET}").lower().startswith("s"):
        code = input(f"{Theme.GREEN_LIGHT}Digite o código de pareamento: {Theme.RESET}").strip()
        UI.spinner("Pareando...", 1.2)
        ok = adb.pair(adb_cfg["pair_target"], code)
        UI.log("ADB", "Pareamento OK" if ok else "Pareamento falhou", "SUCCESS" if ok else "ERROR")

    # Connect now?
    if adb_cfg.get("connect_target") and input(f"\n{Theme.GREEN_LIGHT}Quer CONECTAR agora? (s/n): {Theme.RESET}").lower().startswith("s"):
        UI.spinner("Conectando...", 1.2)
        ok = adb.connect(adb_cfg["connect_target"])
        UI.log("ADB", "Conectado" if ok else "Falhou conectar", "SUCCESS" if ok else "ERROR")
        UI.box("ADB DEVICES", adb.devices())

    # VIP links
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

    # Technical settings
    def ask_int(key: str, label: str):
        cur = cfg.get(key)
        val = input(f"{Theme.GREEN_LIGHT}{label} [{cur}]: {Theme.RESET}").strip()
        if val:
            try:
                cfg[key] = int(val)
            except Exception:
                pass

    def ask_float(key: str, label: str):
        cur = cfg.get(key)
        val = input(f"{Theme.GREEN_LIGHT}{label} [{cur}]: {Theme.RESET}").strip()
        if val:
            cfg[key] = safe_float(val, float(cur))

    print(f"\n{Theme.INFO}Configurações técnicas (Enter = manter){Theme.RESET}")
    ask_int("check_interval", "Intervalo de scan (s)")
    ask_int("cooldown_time", "Cooldown (s)")
    ask_int("warmup_time", "Warmup após relançar (s)")
    ask_float("low_cpu_threshold", "CPU baixa (<= %) [FULL]")
    ask_int("max_lowcpu_time", "Tempo CPU baixa (s) p/ restart [FULL]")
    ask_int("min_rss_mb", "RSS mínimo (MB) [FULL]")
    ask_int("max_lowrss_time", "Tempo RSS baixo (s) p/ restart [FULL]")
    ask_int("device_low_mem_mb", "MemAvailable mínima do device (MB)")
    ask_int("device_low_mem_time", "Tempo em memória baixa (s) p/ ação")
    ask_int("internet_fail_time", "Tempo sem ping (s) p/ rejoin")
    ph = input(f"{Theme.GREEN_LIGHT}Host p/ ping [{cfg.get('ping_host')}]: {Theme.RESET}").strip()
    if ph:
        cfg["ping_host"] = ph

    wh = input(f"{Theme.GREEN_LIGHT}Webhook Discord (Enter p/ manter): {Theme.RESET}").strip()
    if wh:
        cfg["webhook_url"] = wh

    # LITE options
    lo = input(f"{Theme.GREEN_LIGHT}LITE: abrir VIP quando internet voltar? (s/n) [{ 's' if cfg.get('lite_open_vip_on_internet_return') else 'n' }]: {Theme.RESET}").strip().lower()
    if lo in ("s", "n"):
        cfg["lite_open_vip_on_internet_return"] = (lo == "s")

    lem = input(f"{Theme.GREEN_LIGHT}LITE: abrir VIP a cada X minutos (0=desligado) [{cfg.get('lite_open_vip_every_min',0)}]: {Theme.RESET}").strip()
    if lem:
        try:
            cfg["lite_open_vip_every_min"] = int(lem)
        except Exception:
            pass

    # Detect packages now (no ADB required)
    if input(f"\n{Theme.GREEN_LIGHT}Detectar pacotes Roblox agora? (s/n): {Theme.RESET}").lower().startswith("s"):
        UI.spinner("Detectando pacotes...", 1.0)
        adb = ADB(cfg["adb"])
        pkgs = detect_roblox_packages(adb)
        if pkgs:
            cfg["packages"] = pkgs
            UI.box("PACOTES", "\n".join(pkgs))
            UI.log("WIZARD", f"{len(pkgs)} pacotes salvos", "SUCCESS")
        else:
            UI.log("WIZARD", "Nenhum pacote Roblox encontrado", "ERROR")

    save_config(cfg)
    UI.log("CONFIG", "Configuração salva", "SUCCESS")
    return cfg

def interactive_menu(cfg: dict) -> None:
    while True:
        adb = ADB(cfg.get("adb", {}))
        UI.banner()

        pkgs = cfg.get("packages") or []
        adb_ok = adb.is_connected()

        UI.box("STATUS", "\n".join([
            f"ADB: {'OK' if adb_ok else 'OFF'} | auto_connect: {cfg.get('adb',{}).get('auto_connect',True)}",
            f"connect_target: {cfg.get('adb',{}).get('connect_target') or '(vazio)'}",
            f"pair_target: {cfg.get('adb',{}).get('pair_target') or '(vazio)'}",
            f"Pacotes: {len(pkgs)}",
            f"Ping host: {cfg.get('ping_host')}",
        ]))

        print(f"{Theme.GREEN_DARK}┌─[{Theme.CYAN}MENU{Theme.GREEN_DARK}]─{'─'*54}┐{Theme.RESET}")
        print(f"{Theme.GREEN_DARK}│ {Theme.CYAN}1{Theme.GREEN_DARK} {Theme.SYMBOLS['pointer']} {Theme.GREEN_LIGHT}Iniciar monitoramento{Theme.RESET}")
        print(f"{Theme.GREEN_DARK}│ {Theme.CYAN}2{Theme.GREEN_DARK} {Theme.SYMBOLS['pointer']} {Theme.GREEN_LIGHT}Configurar (wizard){Theme.RESET}")
        print(f"{Theme.GREEN_DARK}│ {Theme.CYAN}3{Theme.GREEN_DARK} {Theme.SYMBOLS['pointer']} {Theme.GREEN_LIGHT}Detectar pacotes Roblox (SEM ADB também){Theme.RESET}")
        print(f"{Theme.GREEN_DARK}│ {Theme.CYAN}4{Theme.GREEN_DARK} {Theme.SYMBOLS['pointer']} {Theme.GREEN_LIGHT}ADB: parear / conectar / devices{Theme.RESET}")
        print(f"{Theme.GREEN_DARK}│ {Theme.CYAN}5{Theme.GREEN_DARK} {Theme.SYMBOLS['pointer']} {Theme.GREEN_LIGHT}Executar tudo (auto){Theme.RESET}")
        print(f"{Theme.GREEN_DARK}│ {Theme.CYAN}6{Theme.GREEN_DARK} {Theme.SYMBOLS['pointer']} {Theme.RED}Sair{Theme.RESET}")
        print(f"{Theme.GREEN_DARK}└{'─'*60}┘{Theme.RESET}")

        ch = input(f"\n{Theme.CYAN}{Theme.SYMBOLS['terminal']} {Theme.BOLD}Escolha (1-6): {Theme.RESET}").strip()

        if ch == "1":
            if not pkgs:
                UI.log("SYSTEM", "Nenhum pacote configurado. Use Detectar Pacotes.", "ERROR")
                input(f"{Theme.GREEN_LIGHT}Enter...{Theme.RESET}")
                continue
            mon = TitaniyahuMonitor(cfg, adb)
            mon.monitor_loop()
            input(f"{Theme.GREEN_LIGHT}Enter...{Theme.RESET}")

        elif ch == "2":
            cfg = setup_wizard(cfg)
            input(f"{Theme.GREEN_LIGHT}Enter...{Theme.RESET}")

        elif ch == "3":
            UI.spinner("Detectando pacotes...", 0.9)
            pkgs = detect_roblox_packages(adb)
            if pkgs:
                cfg["packages"] = pkgs
                save_config(cfg)
                UI.box("PACOTES", "\n".join(pkgs))
                UI.log("SYSTEM", f"{len(pkgs)} pacotes salvos", "SUCCESS")
                if not adb.is_connected():
                    UI.log("ADB", "Detectei via Termux (pm). Para FULL (CPU/RSS/force-stop), conecte ADB.", "WARN")
            else:
                UI.log("SYSTEM", "Nenhum pacote Roblox encontrado", "ERROR")
            input(f"{Theme.GREEN_LIGHT}Enter...{Theme.RESET}")

        elif ch == "4":
            UI.banner()
            adb_cfg = cfg.get("adb", {})
            adb = ADB(adb_cfg)

            UI.box("ADB DEVICES", adb.devices())
            print(f"\n{Theme.GREEN_LIGHT}1) Parear (Wireless Debugging)\n2) Conectar (adb connect)\n3) Voltar{Theme.RESET}")
            sub = input(f"{Theme.CYAN}{Theme.SYMBOLS['terminal']} Escolha (1-3): {Theme.RESET}").strip()

            if sub == "1":
                pair_target = (adb_cfg.get("pair_target") or "").strip()
                if not pair_target:
                    pair_target = input(f"{Theme.GREEN_LIGHT}pair_target (ex 127.0.0.1:37123): {Theme.RESET}").strip()
                    adb_cfg["pair_target"] = pair_target
                code = input(f"{Theme.GREEN_LIGHT}Código de pareamento: {Theme.RESET}").strip()
                cfg["adb"] = adb_cfg
                save_config(cfg)
                adb = ADB(cfg["adb"])
                UI.spinner("Pareando...", 1.2)
                ok = adb.pair(pair_target, code)
                UI.log("ADB", "Pareamento OK" if ok else "Pareamento falhou", "SUCCESS" if ok else "ERROR")
                UI.box("ADB DEVICES", adb.devices())
                input(f"{Theme.GREEN_LIGHT}Enter...{Theme.RESET}")

            elif sub == "2":
                connect_target = (adb_cfg.get("connect_target") or "").strip()
                if not connect_target:
                    connect_target = input(f"{Theme.GREEN_LIGHT}connect_target (ex 127.0.0.1:5555): {Theme.RESET}").strip()
                    adb_cfg["connect_target"] = connect_target
                cfg["adb"] = adb_cfg
                save_config(cfg)
                adb = ADB(cfg["adb"])
                UI.spinner("Conectando...", 1.2)
                ok = adb.connect(connect_target)
                UI.log("ADB", "Conectado" if ok else "Falhou conectar", "SUCCESS" if ok else "ERROR")
                UI.box("ADB DEVICES", adb.devices())
                input(f"{Theme.GREEN_LIGHT}Enter...{Theme.RESET}")

        elif ch == "5":
            # auto: detectar pacotes (sem ADB) e iniciar monitor
            UI.spinner("Detectando pacotes...", 0.9)
            pkgs = detect_roblox_packages(adb)
            if pkgs:
                cfg["packages"] = pkgs
                save_config(cfg)
                UI.log("AUTO", f"{len(pkgs)} pacotes detectados e salvos", "SUCCESS")
                mon = TitaniyahuMonitor(cfg, ADB(cfg.get("adb", {})))
                mon.monitor_loop()
            else:
                UI.log("AUTO", "Nenhum pacote Roblox detectado", "ERROR")
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
    p.add_argument("--auto", action="store_true", help="Detecta pacotes e inicia monitoramento.")
    p.add_argument("--monitor", action="store_true", help="Inicia monitoramento com pacotes do config.")
    p.add_argument("--detect", action="store_true", help="Detecta pacotes Roblox e salva no config.")
    p.add_argument("--config", action="store_true", help="Abre wizard.")
    return p.parse_args()

def main():
    cfg = load_config()
    args = parse_args()
    adb = ADB(cfg.get("adb", {}))

    if args.config:
        setup_wizard(cfg)
        return

    if args.detect:
        pkgs = detect_roblox_packages(adb)
        if pkgs:
            cfg["packages"] = pkgs
            save_config(cfg)
            UI.banner()
            UI.box("PACOTES", "\n".join(pkgs))
            UI.log("SYSTEM", f"{len(pkgs)} pacotes salvos em {CONFIG_FILE}", "SUCCESS")
            if not adb.is_connected():
                UI.log("ADB", "Aviso: sem ADB, FULL (CPU/RSS/force-stop) não funciona.", "WARN")
        else:
            UI.log("SYSTEM", "Nenhum pacote Roblox encontrado", "ERROR")
        return

    if args.auto:
        pkgs = detect_roblox_packages(adb)
        if not pkgs:
            UI.log("AUTO", "Nenhum pacote Roblox detectado", "ERROR")
            return
        cfg["packages"] = pkgs
        save_config(cfg)
        mon = TitaniyahuMonitor(cfg, ADB(cfg.get("adb", {})))
        mon.monitor_loop()
        return

    if args.monitor:
        if not cfg.get("packages"):
            UI.log("SYSTEM", "Config sem pacotes. Rode --detect ou --auto.", "ERROR")
            return
        mon = TitaniyahuMonitor(cfg, ADB(cfg.get("adb", {})))
        mon.monitor_loop()
        return

    interactive_menu(cfg)

if __name__ == "__main__":
    main()
