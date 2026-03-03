#!/usr/bin/env python3
"""
🖥️ TITANIYAHU - Roblox AutoRejoin (Termux/ADB) 🖥️
v5.2 - FIX: Roblox não abrindo + ping falso + logs de erro do am start

FULL (com ADB):
- PID / CPU / RSS / force-stop / rejoin
LITE (sem ADB):
- ping/mem local + tenta reconectar ADB + abre VIP sem force-stop

⚠️ Para CPU/RSS/force-stop funcionar, precisa ADB conectado.
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


APP_NAME = "TITANIYAHU"
VERSION = "5.2"
CONFIG_FILE = "titaniyahu_config.json"

DEFAULT_CONFIG = {
    "vip_links": [
        "https://www.roblox.com/games/1537690962/Bee-Swarm-Simulator?privateServerLinkCode=05888256464342538313491710978310"
    ],
    "webhook_url": "",

    "check_interval": 10,
    "cooldown_time": 12,
    "warmup_time": 20,

    "launch_wait_sec": 12,          # ⬅️ espera PID depois de abrir
    "link_apply_wait_sec": 6,       # ⬅️ espera depois de aplicar link
    "monkey_first": True,           # ⬅️ abre Roblox primeiro (recomendado)

    "low_cpu_threshold": 8.0,
    "max_lowcpu_time": 30,

    "min_rss_mb": 60,
    "max_lowrss_time": 30,

    "device_low_mem_mb": 350,
    "device_low_mem_time": 30,

    "internet_fail_time": 25,
    "ping_host": "1.1.1.1",

    "adb": {
        "serial": "",
        "auto_connect": True,
        "connect_target": "",
        "pair_target": "",
    },

    "packages": [],

    "lite_open_vip_on_internet_return": False,
    "lite_open_vip_every_min": 0,
}

# =========================
# 🎨 THEME/UI
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

    SYMBOLS = {"terminal": "⌘", "pointer": "➤", "radar": "📡"}


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


def local_shell(cmd: str, timeout: int = 18) -> Tuple[int, str, str]:
    try:
        p = subprocess.run(["sh", "-lc", cmd], capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as e:
        return 1, "", str(e)


def load_config() -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user = json.load(f)
            if isinstance(user, dict):
                cfg.update({k: v for k, v in user.items() if k != "adb"})
                if isinstance(user.get("adb"), dict):
                    cfg["adb"].update(user["adb"])
        except Exception as e:
            UI.log("CONFIG", f"Falha ao carregar config: {e}", "ERROR")

    if isinstance(cfg.get("vip_links"), str):
        cfg["vip_links"] = [cfg["vip_links"]]
    if not cfg.get("vip_links"):
        cfg["vip_links"] = DEFAULT_CONFIG["vip_links"]
    return cfg


def save_config(cfg: dict) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


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

    def shell_rc(self, cmd: str, timeout: int = 12) -> Tuple[int, str, str]:
        # importante: retorna stdout+stderr (pra gente ver erro do am start)
        return self.run(["shell", "sh", "-c", cmd], timeout=timeout)

    def shell(self, cmd: str, timeout: int = 12) -> str:
        rc, out, err = self.shell_rc(cmd, timeout=timeout)
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


def detect_roblox_packages(adb: ADB) -> List[str]:
    out = ""
    if adb.ensure():
        out = adb.shell("pm list packages -3", timeout=18)
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


@dataclass
class ProcSample:
    last_proc_jiffies: int = 0
    last_total_jiffies: int = 0
    last_seen_pid: str = ""
    lowcpu_seconds: int = 0
    lowrss_seconds: int = 0
    last_launch_ts: float = 0.0
    cooldown_until: float = 0.0


class TitaniyahuMonitor:
    def __init__(self, cfg: dict, adb: ADB):
        self.cfg = cfg
        self.adb = adb
        self.running = True
        self.samples: Dict[str, ProcSample] = {}

        self.internet_fail_seconds = 0
        self.low_mem_seconds = 0
        self.last_lite_open_ts = 0.0

        self._ping_supported: Optional[bool] = None

        signal.signal(signal.SIGINT, self._sig)
        signal.signal(signal.SIGTERM, self._sig)

    def _sig(self, *_):
        UI.log("SYSTEM", "Interrupção detectada • encerrando...", "WARN")
        self.running = False

    # ------------------ NET ------------------
    def _check_ping_supported(self) -> bool:
        if self._ping_supported is not None:
            return self._ping_supported
        # testa se existe "ping" no ambiente (ADB ou local)
        if self.adb.ensure():
            rc, out, err = self.adb.shell_rc("command -v ping >/dev/null 2>&1; echo $?", timeout=6)
            ok = ("0" in (out.strip() or ""))
            self._ping_supported = ok
            if not ok:
                UI.log("NET", "ping não disponível no shell via ADB (vou ignorar checagem de ping)", "WARN")
            return ok
        rc, out, _ = local_shell("command -v ping >/dev/null 2>&1; echo $?", timeout=6)
        ok = ("0" in (out.strip() or ""))
        self._ping_supported = ok
        if not ok:
            UI.log("NET", "ping não disponível (vou ignorar checagem de ping)", "WARN")
        return ok

    def internet_ok(self) -> Optional[bool]:
        # retorna True/False ou None = "não sei" (não penaliza)
        if not self._check_ping_supported():
            return None

        host = str(self.cfg.get("ping_host", "1.1.1.1")).strip() or "1.1.1.1"
        cmds = (f"ping -c 1 -W 2 {host}", f"ping -c 1 -w 2 {host}", f"ping -c 1 {host}")

        if self.adb.ensure():
            for c in cmds:
                rc, out, err = self.adb.shell_rc(c, timeout=6)
                txt = (out + "\n" + err).lower()
                if ("bytes from" in txt and "time=" in txt) or ("1 received" in txt) or ("1 packets received" in txt):
                    return True
            return False

        for c in cmds:
            rc, out, err = local_shell(c, timeout=6)
            txt = (out + "\n" + err).lower()
            if ("bytes from" in txt and "time=" in txt) or ("1 received" in txt) or ("1 packets received" in txt):
                return True
        return False

    # ------------------ MEM ------------------
    def device_mem(self) -> Tuple[Optional[int], Optional[int]]:
        if self.adb.ensure():
            mem = self.adb.shell("cat /proc/meminfo", timeout=6)
            return parse_meminfo(mem)
        _, mem, _ = local_shell("cat /proc/meminfo", timeout=6)
        return parse_meminfo(mem)

    # ------------------ FULL metrics ------------------
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
        parts = txt.splitlines()[0].split()
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
            return int(parts[13]) + int(parts[14])
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
        return (kb / 1024.0) if kb else 0.0

    # ------------------ ACTIONS ------------------
    def choose_vip_link(self) -> str:
        links = self.cfg.get("vip_links") or []
        if isinstance(links, str):
            links = [links]
        links = [l.strip() for l in links if isinstance(l, str) and l.strip()]
        if not links:
            links = DEFAULT_CONFIG["vip_links"]
        return links[int(time.time()) % len(links)]

    def wait_pid(self, package: str, sec: int) -> Optional[str]:
        end = time.time() + sec
        while time.time() < end:
            pid = self.get_pid(package)
            if pid:
                return pid
            time.sleep(0.4)
        return None

    def open_app_monkey(self, package: str) -> Tuple[bool, str]:
        # abre o app pela intent LAUNCHER (bem mais confiável)
        rc, out, err = self.adb.shell_rc(
            f"monkey -p {package} -c android.intent.category.LAUNCHER 1",
            timeout=12
        )
        txt = (out + "\n" + err).strip()
        ok = rc == 0
        return ok, txt

    def apply_link(self, package: str, link: str) -> Tuple[bool, str]:
        # 1) tenta VIEW sem -p (deixa sistema resolver, universal link)
        rc1, out1, err1 = self.adb.shell_rc(
            f"am start -a android.intent.action.VIEW -c android.intent.category.BROWSABLE -d '{link}'",
            timeout=14
        )
        txt1 = (out1 + "\n" + err1).strip()

        # 2) tenta VIEW com -p (se tiver intent filter)
        rc2, out2, err2 = self.adb.shell_rc(
            f"am start -a android.intent.action.VIEW -c android.intent.category.BROWSABLE -d '{link}' -p {package}",
            timeout=14
        )
        txt2 = (out2 + "\n" + err2).strip()

        ok = (rc1 == 0) or (rc2 == 0)
        combined = ("[VIEW no -p]\n" + (txt1 or "(vazio)") + "\n\n[VIEW com -p]\n" + (txt2 or "(vazio)"))
        return ok, combined

    def open_vip(self, package: str) -> bool:
        link = self.choose_vip_link()

        if not self.adb.ensure():
            # LITE local: tenta abrir
            rc, out, err = local_shell(
                f"am start -a android.intent.action.VIEW -c android.intent.category.BROWSABLE -d '{link}' -p {package}",
                timeout=14
            )
            return rc == 0 and ("error" not in (out + err).lower())

        # FULL:
        if self.cfg.get("monkey_first", True):
            ok, txt = self.open_app_monkey(package)
            if not ok:
                UI.log(package, f"monkey falhou:\n{txt}", "ERROR")
            else:
                UI.log(package, "App aberto (monkey)", "SUCCESS")

            pid = self.wait_pid(package, int(self.cfg.get("launch_wait_sec", 12)))
            if not pid:
                UI.log(package, "Não consegui PID após abrir app (monkey).", "ERROR")
                # mesmo assim tenta aplicar link
            else:
                UI.log(package, f"PID detectado: {pid}", "INFO")

        ok_link, debug_txt = self.apply_link(package, link)
        if not ok_link:
            UI.log(package, "am start do link falhou (vou mostrar debug abaixo)", "ERROR")
            UI.box("AM START DEBUG", debug_txt)

        time.sleep(int(self.cfg.get("link_apply_wait_sec", 6)))
        pid2 = self.wait_pid(package, int(self.cfg.get("launch_wait_sec", 12)))
        return pid2 is not None

    def force_stop(self, package: str) -> bool:
        if not self.adb.ensure():
            return False
        self.adb.shell_rc(f"am force-stop {package}", timeout=10)
        time.sleep(0.3)
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
            time.sleep(1.0)
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
            UI.log(package, "Rejoin pode ter falhado (sem PID)", "ERROR")
            send_webhook(self.cfg.get("webhook_url", ""), f"❌ {package} rejoin falhou • motivo: {reason}")
        return ok

    # ------------------ RULES ------------------
    def should_ignore_rules(self, package: str) -> bool:
        warm = int(self.cfg.get("warmup_time", 20))
        sample = self.samples.setdefault(package, ProcSample())
        return sample.last_launch_ts > 0 and (time.time() - sample.last_launch_ts) < warm

    def tick_package_full(self, package: str, interval: int,
                          inet: Optional[bool], avail_mem_mb: Optional[int]) -> None:
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
            self.soft_restart(package, f"CPU baixa {sample.lowcpu_seconds}s ({cpu:.1f}%)")
            return

        if sample.lowrss_seconds >= int(self.cfg.get("max_lowrss_time", 30)):
            self.soft_restart(package, f"RSS baixo {sample.lowrss_seconds}s ({rss:.0f}MB)")
            return

        # só penaliza internet se a checagem for confiável (inet != None)
        if inet is False and self.internet_fail_seconds >= int(self.cfg.get("internet_fail_time", 25)):
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
        UI.log(package, "LITE • sem métricas do processo (conecte ADB p/ FULL)", "WARN")

    # ------------------ LOOP ------------------
    def monitor_loop(self) -> None:
        UI.banner()
        pkgs = self.cfg.get("packages") or []
        interval = int(self.cfg.get("check_interval", 10))

        if not pkgs:
            UI.log("SYSTEM", "Nenhum pacote configurado. Use Detectar Pacotes.", "ERROR")
            return

        UI.box("CONFIG", "\n".join([
            f"Intervalo: {interval}s | Cooldown: {self.cfg.get('cooldown_time')}s | Warmup: {self.cfg.get('warmup_time')}s",
            f"monkey_first: {self.cfg.get('monkey_first', True)} | launch_wait: {self.cfg.get('launch_wait_sec')}s | link_wait: {self.cfg.get('link_apply_wait_sec')}s",
            f"Ping host: {self.cfg.get('ping_host')} (ping_supported será detectado)",
            f"ADB auto_connect: {self.cfg.get('adb', {}).get('auto_connect', True)}",
            f"ADB connect_target: {self.cfg.get('adb', {}).get('connect_target', '') or '(vazio)'}",
            f"Pacotes: {len(pkgs)}",
        ]))

        UI.spinner("Inicializando (rejoin) pacotes...", 1.0)
        for p in pkgs:
            self.soft_restart(p, "startup")
            time.sleep(0.6)

        cycle = 0
        while self.running:
            cycle += 1
            adb_ok = self.adb.ensure()
            mode = "FULL" if adb_ok else "LITE"

            print(f"\n{Theme.GREEN_DARK}{'─'*64}{Theme.RESET}")
            print(f"{Theme.CYAN}{Theme.SYMBOLS['radar']} CICLO {cycle:04d} • {datetime.now().strftime('%H:%M:%S')} • MODE={mode}{Theme.RESET}")
            print(f"{Theme.GREEN_DARK}{'─'*64}{Theme.RESET}\n")

            total_mb, avail_mb = self.device_mem()
            inet = self.internet_ok()

            # NET status
            if inet is None:
                UI.log("NET", "Checagem de ping indisponível • ignorando regra de internet", "WARN")
                self.internet_fail_seconds = 0
            elif inet is False:
                self.internet_fail_seconds += interval
                UI.log("NET", f"Sem ping ({self.internet_fail_seconds}s)", "WARN")
            else:
                if self.internet_fail_seconds >= interval:
                    UI.log("NET", "Ping OK (internet voltou)", "SUCCESS")
                self.internet_fail_seconds = 0

            # MEM status
            if avail_mb is not None and avail_mb <= int(self.cfg.get("device_low_mem_mb", 350)):
                self.low_mem_seconds += interval
                UI.log("MEM", f"Memória baixa: {avail_mb}MB livres ({self.low_mem_seconds}s)", "WARN")
            else:
                self.low_mem_seconds = 0
                if avail_mb is not None and total_mb is not None:
                    UI.log("MEM", f"Memória OK: {avail_mb}MB livres de {total_mb}MB", "INFO")

            if not adb_ok:
                UI.log("ADB", "OFFLINE • tentando reconectar automaticamente...", "WARN")

            for p in pkgs:
                if adb_ok:
                    self.tick_package_full(p, interval=interval, inet=inet, avail_mem_mb=avail_mb)
                else:
                    self.tick_package_lite(p)

            for s in range(interval, 0, -1):
                warn = s <= 3
                t = f"{Theme.BLINK}{Theme.RED}{s:02d}s{Theme.RESET}" if warn else f"{s:02d}s"
                print(f"\r{Theme.GREEN_DARK}[{Theme.CYAN}AGUARDANDO{Theme.GREEN_DARK}] "
                      f"{Theme.GREEN_LIGHT}próximo scan em {t}{Theme.RESET}", end="", flush=True)
                time.sleep(1)
            print()


def setup_wizard(cfg: dict) -> dict:
    UI.banner()
    UI.log("WIZARD", "Configuração rápida", "INFO")

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

    if adb_cfg.get("pair_target") and input(f"\n{Theme.GREEN_LIGHT}Parear agora? (s/n): {Theme.RESET}").lower().startswith("s"):
        code = input(f"{Theme.GREEN_LIGHT}Código de pareamento: {Theme.RESET}").strip()
        UI.spinner("Pareando...", 1.0)
        ok = adb.pair(adb_cfg["pair_target"], code)
        UI.log("ADB", "Pareamento OK" if ok else "Pareamento falhou", "SUCCESS" if ok else "ERROR")

    if adb_cfg.get("connect_target") and input(f"\n{Theme.GREEN_LIGHT}Conectar agora? (s/n): {Theme.RESET}").lower().startswith("s"):
        UI.spinner("Conectando...", 1.0)
        ok = adb.connect(adb_cfg["connect_target"])
        UI.log("ADB", "Conectado" if ok else "Falhou conectar", "SUCCESS" if ok else "ERROR")
        UI.box("ADB DEVICES", adb.devices())

    # VIP links
    print(f"\n{Theme.INFO}Links VIP/Private Server (1 por linha). Vazio = manter.{Theme.RESET}")
    print(f"{Theme.DIM}Finalize com 'FIM'.{Theme.RESET}")
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

    # opts do launch
    mf = input(f"{Theme.GREEN_LIGHT}Abrir Roblox via monkey antes do link? (s/n) [{ 's' if cfg.get('monkey_first', True) else 'n' }]: {Theme.RESET}").strip().lower()
    if mf in ("s", "n"):
        cfg["monkey_first"] = (mf == "s")

    lw = input(f"{Theme.GREEN_LIGHT}Esperar PID (launch_wait_sec) [{cfg.get('launch_wait_sec')}]: {Theme.RESET}").strip()
    if lw:
        try: cfg["launch_wait_sec"] = int(lw)
        except: pass

    aw = input(f"{Theme.GREEN_LIGHT}Esperar após aplicar link (link_apply_wait_sec) [{cfg.get('link_apply_wait_sec')}]: {Theme.RESET}").strip()
    if aw:
        try: cfg["link_apply_wait_sec"] = int(aw)
        except: pass

    ph = input(f"{Theme.GREEN_LIGHT}Host p/ ping [{cfg.get('ping_host')}]: {Theme.RESET}").strip()
    if ph:
        cfg["ping_host"] = ph

    if input(f"\n{Theme.GREEN_LIGHT}Detectar pacotes Roblox agora? (s/n): {Theme.RESET}").lower().startswith("s"):
        UI.spinner("Detectando pacotes...", 0.8)
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
        UI.box("STATUS", "\n".join([
            f"ADB: {'OK' if adb.is_connected() else 'OFF'} | auto_connect: {cfg.get('adb',{}).get('auto_connect',True)}",
            f"connect_target: {cfg.get('adb',{}).get('connect_target') or '(vazio)'}",
            f"Pacotes: {len(pkgs)}",
            f"Ping host: {cfg.get('ping_host')}",
        ]))

        print(f"{Theme.GREEN_DARK}┌─[{Theme.CYAN}MENU{Theme.GREEN_DARK}]─{'─'*54}┐{Theme.RESET}")
        print(f"{Theme.GREEN_DARK}│ {Theme.CYAN}1{Theme.GREEN_DARK} {Theme.SYMBOLS['pointer']} {Theme.GREEN_LIGHT}Iniciar monitoramento{Theme.RESET}")
        print(f"{Theme.GREEN_DARK}│ {Theme.CYAN}2{Theme.GREEN_DARK} {Theme.SYMBOLS['pointer']} {Theme.GREEN_LIGHT}Configurar (wizard){Theme.RESET}")
        print(f"{Theme.GREEN_DARK}│ {Theme.CYAN}3{Theme.GREEN_DARK} {Theme.SYMBOLS['pointer']} {Theme.GREEN_LIGHT}Detectar pacotes Roblox (SEM ADB também){Theme.RESET}")
        print(f"{Theme.GREEN_DARK}│ {Theme.CYAN}4{Theme.GREEN_DARK} {Theme.SYMBOLS['pointer']} {Theme.GREEN_LIGHT}ADB devices{Theme.RESET}")
        print(f"{Theme.GREEN_DARK}│ {Theme.CYAN}5{Theme.GREEN_DARK} {Theme.SYMBOLS['pointer']} {Theme.GREEN_LIGHT}Executar tudo (auto){Theme.RESET}")
        print(f"{Theme.GREEN_DARK}│ {Theme.CYAN}6{Theme.GREEN_DARK} {Theme.SYMBOLS['pointer']} {Theme.RED}Sair{Theme.RESET}")
        print(f"{Theme.GREEN_DARK}└{'─'*60}┘{Theme.RESET}")

        ch = input(f"\n{Theme.CYAN}{Theme.SYMBOLS['terminal']} {Theme.BOLD}Escolha (1-6): {Theme.RESET}").strip()

        if ch == "1":
            if not pkgs:
                UI.log("SYSTEM", "Nenhum pacote configurado. Use Detectar Pacotes.", "ERROR")
                input(f"{Theme.GREEN_LIGHT}Enter...{Theme.RESET}")
                continue
            TitaniyahuMonitor(cfg, adb).monitor_loop()
            input(f"{Theme.GREEN_LIGHT}Enter...{Theme.RESET}")

        elif ch == "2":
            cfg = setup_wizard(cfg)
            input(f"{Theme.GREEN_LIGHT}Enter...{Theme.RESET}")

        elif ch == "3":
            UI.spinner("Detectando pacotes...", 0.8)
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
            UI.box("ADB DEVICES", adb.devices())
            input(f"{Theme.GREEN_LIGHT}Enter...{Theme.RESET}")

        elif ch == "5":
            UI.spinner("Detectando pacotes...", 0.8)
            pkgs = detect_roblox_packages(adb)
            if pkgs:
                cfg["packages"] = pkgs
                save_config(cfg)
                UI.log("AUTO", f"{len(pkgs)} pacotes detectados e salvos", "SUCCESS")
                TitaniyahuMonitor(cfg, ADB(cfg.get("adb", {}))).monitor_loop()
            else:
                UI.log("AUTO", "Nenhum pacote Roblox detectado", "ERROR")
            input(f"{Theme.GREEN_LIGHT}Enter...{Theme.RESET}")

        elif ch == "6":
            UI.log("SYSTEM", "Encerrando. Até mais!", "SUCCESS")
            sys.exit(0)

        else:
            UI.log("INPUT", "Opção inválida", "ERROR")
            time.sleep(1)


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
        TitaniyahuMonitor(cfg, ADB(cfg.get("adb", {}))).monitor_loop()
        return
    if args.monitor:
        if not cfg.get("packages"):
            UI.log("SYSTEM", "Config sem pacotes. Rode --detect ou --auto.", "ERROR")
            return
        TitaniyahuMonitor(cfg, ADB(cfg.get("adb", {}))).monitor_loop()
        return

    interactive_menu(cfg)


if __name__ == "__main__":
    main()
