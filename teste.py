#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import json
import shutil
import signal
import subprocess
import threading
import queue
import re
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, Any, List, Optional, Tuple

CONFIG_FILE = "monitor_config.json"
LOG_FILE = "monitor.log"

SPINNER = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
SPARK_CHARS = "▁▂▃▄▅▆▇█"
HELP_TEXT = "Teclas: [D]ebug  [P]ause  [R]estart all  [1..9] restart pkg  [Q]uit"

DEFAULT_CONFIG = {
    # Roblox / Launch
    "web_link": "https://www.roblox.com/games/1537690962/Bee-Swarm-Simulator",
    "proto_activity": "com.roblox.client.ActivityProtocolLaunch",
    "launch_mode": "vip",  # vip|monkey

    # Monitor
    "packages": [],
    "check_interval": 2.0,   # coleta adb (ps/top)
    "ui_refresh": 0.20,      # fps do dashboard
    "low_cpu_threshold": 5.0,
    "freeze_cpu_threshold": 0.5,
    "lowcpu_strikes": 3,
    "freeze_strikes": 4,
    "restart_cooldown": 10.0,

    # ADB
    "adb_serial": "",
    "adb_timeout": 6.0,

    # Debug/Logs
    "debug": True,
    "log_max_memory": 250,

    # Popup Play Games
    "dismiss_play_games": True,

    # Webhook (notificações)
    "webhook_url": "",           # Discord webhook ou endpoint seu
    "webhook_mode": "auto",      # auto|discord|json
    "webhook_notify_events": True,

    # Controle remoto (poll)
    "control_url": "",           # GET -> JSON de comandos
    "control_poll_interval": 4.0,
    "control_token": "",
    "control_token_header": "X-Control-Token",
    "control_ack_url": "",       # POST ack (se vazio usa webhook_url)

    # Servidor local opcional (POST /cmd)
    "local_control_server": False,
    "local_control_host": "127.0.0.1",
    "local_control_port": 8765,
}

# =========================
# UTIL / CONFIG
# =========================

def now_ts() -> str:
    return datetime.now().strftime("%H:%M:%S")

def load_config() -> Dict[str, Any]:
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG.copy())
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        merged = DEFAULT_CONFIG.copy()
        merged.update(cfg)
        return merged
    except Exception:
        save_config(DEFAULT_CONFIG.copy())
        return DEFAULT_CONFIG.copy()

def save_config(cfg: Dict[str, Any]) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def fit(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text + " " * (width - len(text))
    if width <= 1:
        return text[:width]
    return text[:width-1] + "…"

def sparkline(values: List[float], vmax: float, width: int) -> str:
    if width <= 0:
        return ""
    if not values:
        return " " * width
    tail = values[-width:]
    out = []
    for v in tail:
        v = max(0.0, v)
        frac = 0.0 if vmax <= 0 else min(1.0, v / vmax)
        idx = int(frac * (len(SPARK_CHARS) - 1))
        out.append(SPARK_CHARS[idx])
    return "".join(out)

def bar(percent: float, width: int) -> str:
    if width <= 0:
        return ""
    p = max(0.0, min(100.0, percent))
    filled = int(round((p / 100.0) * width))
    return "█" * filled + "░" * (width - filled)

# =========================
# DEBUG + LOGGER
# =========================

class Debug:
    enabled: bool = True

    @staticmethod
    def toggle() -> bool:
        Debug.enabled = not Debug.enabled
        return Debug.enabled

class Logger:
    def __init__(self, filepath: str, max_mem: int):
        self.filepath = filepath
        self.max_mem = max_mem
        self._mem: List[str] = []
        self._lock = threading.Lock()

    def log(self, level: str, msg: str, pkg: str = "") -> None:
        line = f"{now_ts()} [{level:<5}]"
        if pkg:
            line += f" [{pkg}]"
        line += f" {msg}"

        with self._lock:
            self._mem.append(line)
            if len(self._mem) > self.max_mem:
                self._mem = self._mem[-self.max_mem:]

        try:
            with open(self.filepath, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def tail(self, n: int) -> List[str]:
        with self._lock:
            return self._mem[-n:]

# =========================
# TERMINAL (tela fixa)
# =========================

class Terminal:
    def __init__(self):
        self.is_tty = sys.stdin.isatty() and sys.stdout.isatty()
        self._orig_term = None

    def enter(self):
        if not self.is_tty:
            return
        sys.stdout.write("\033[?1049h\033[?25l")  # alt screen + hide cursor
        sys.stdout.flush()
        try:
            import termios, tty
            self._orig_term = termios.tcgetattr(sys.stdin.fileno())
            tty.setcbreak(sys.stdin.fileno())
        except Exception:
            self._orig_term = None

    def exit(self):
        if not self.is_tty:
            return
        try:
            if self._orig_term is not None:
                import termios
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._orig_term)
        except Exception:
            pass
        sys.stdout.write("\033[?25h\033[?1049l")  # show cursor + leave alt
        sys.stdout.flush()

    @staticmethod
    def clear_home():
        sys.stdout.write("\033[2J\033[H")

    @staticmethod
    def size() -> Tuple[int, int]:
        sz = shutil.get_terminal_size(fallback=(110, 30))
        return sz.columns, sz.lines

# =========================
# HTTP (webhook/control)
# =========================

def http_get_json(url: str, headers: Dict[str, str], timeout: float) -> Tuple[bool, Any, str]:
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            return True, json.loads(raw), raw
    except Exception as e:
        return False, None, str(e)

def http_post_json(url: str, payload: Dict[str, Any], headers: Dict[str, str], timeout: float) -> Tuple[bool, str]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **headers},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return False, str(e)

class Webhook:
    def __init__(self, cfg: Dict[str, Any], logger: Logger):
        self.cfg = cfg
        self.logger = logger

    def _mode(self) -> str:
        mode = (self.cfg.get("webhook_mode") or "auto").lower()
        if mode == "auto":
            url = (self.cfg.get("webhook_url") or "").lower()
            if "discord.com/api/webhooks" in url or "discordapp.com/api/webhooks" in url:
                return "discord"
            return "json"
        return mode

    def notify(self, event: str, data: Dict[str, Any]) -> None:
        url = (self.cfg.get("webhook_url") or "").strip()
        if not url or not self.cfg.get("webhook_notify_events", True):
            return

        mode = self._mode()
        if mode == "discord":
            content = f"**{event}**\n```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```"
            payload = {"content": content}
        else:
            payload = {"event": event, "data": data, "ts": datetime.now().isoformat()}

        ok, err = http_post_json(url, payload, headers={}, timeout=6.0)
        if not ok:
            self.logger.log("ERR", f"Webhook notify falhou: {err}")

class ControlPoller(threading.Thread):
    def __init__(self, cfg: Dict[str, Any], qcmd: queue.Queue, logger: Logger):
        super().__init__(daemon=True)
        self.cfg = cfg
        self.qcmd = qcmd
        self.logger = logger
        self.stop_evt = threading.Event()
        self.last_id = 0

    def stop(self):
        self.stop_evt.set()

    def run(self):
        while not self.stop_evt.is_set():
            url = (self.cfg.get("control_url") or "").strip()
            if not url:
                time.sleep(1.0)
                continue

            token = (self.cfg.get("control_token") or "").strip()
            header_name = (self.cfg.get("control_token_header") or "X-Control-Token").strip()
            headers = {}
            if token:
                headers[header_name] = token

            ok, obj, err = http_get_json(url, headers=headers, timeout=6.0)
            if ok and obj is not None:
                cmds = []
                if isinstance(obj, list):
                    cmds = obj
                elif isinstance(obj, dict):
                    if isinstance(obj.get("commands"), list):
                        cmds = obj["commands"]
                    elif "cmd" in obj:
                        cmds = [obj]

                for c in cmds:
                    if not isinstance(c, dict):
                        continue
                    cid = c.get("id", 0)
                    try:
                        cid = int(cid)
                    except Exception:
                        cid = 0
                    if cid <= self.last_id:
                        continue
                    self.last_id = max(self.last_id, cid)
                    self.qcmd.put(c)
                    self.logger.log("INF", f"Cmd remoto: {c.get('cmd')} (id={cid})")

            elif not ok:
                self.logger.log("ERR", f"Control poll falhou: {err}")

            time.sleep(max(1.0, float(self.cfg.get("control_poll_interval", 4.0))))

class LocalControlServer(threading.Thread):
    def __init__(self, host: str, port: int, qcmd: queue.Queue, logger: Logger):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.qcmd = qcmd
        self.logger = logger
        self.httpd: Optional[HTTPServer] = None

    def run(self):
        qcmd = self.qcmd
        logger = self.logger

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path != "/cmd":
                    self.send_response(404); self.end_headers()
                    return
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8", errors="ignore")
                try:
                    obj = json.loads(raw) if raw else {}
                    if isinstance(obj, dict) and "cmd" in obj:
                        qcmd.put(obj)
                        logger.log("INF", f"Cmd local: {obj.get('cmd')}")
                        self.send_response(200); self.end_headers()
                        self.wfile.write(b'{"ok":true}')
                    else:
                        self.send_response(400); self.end_headers()
                        self.wfile.write(b'{"ok":false,"err":"invalid"}')
                except Exception as e:
                    self.send_response(400); self.end_headers()
                    self.wfile.write(json.dumps({"ok": False, "err": str(e)}).encode("utf-8"))

            def log_message(self, *_):
                return

        try:
            self.httpd = HTTPServer((self.host, int(self.port)), Handler)
            self.logger.log("INF", f"Local control ON: http://{self.host}:{self.port}/cmd")
            self.httpd.serve_forever()
        except Exception as e:
            self.logger.log("ERR", f"Local control falhou: {e}")

    def stop(self):
        if self.httpd:
            try:
                self.httpd.shutdown()
            except Exception:
                pass

# =========================
# ADB (otimizado)
# =========================

class ADB:
    def __init__(self, serial: str, timeout: float, logger: Logger):
        self.serial = (serial or "").strip()
        self.timeout = float(timeout)
        self.logger = logger

    def _base(self) -> List[str]:
        cmd = ["adb"]
        if self.serial:
            cmd += ["-s", self.serial]
        return cmd

    def run(self, args: List[str], timeout: Optional[float] = None) -> Tuple[int, str, str]:
        t = self.timeout if timeout is None else float(timeout)
        try:
            p = subprocess.run(self._base() + args, capture_output=True, text=True, timeout=t)
            return p.returncode, p.stdout.strip(), p.stderr.strip()
        except Exception as e:
            return 1, "", str(e)

    def shell(self, cmd: str, timeout: Optional[float] = None) -> str:
        rc, out, err = self.run(["shell", "sh", "-c", cmd], timeout=timeout)
        if rc != 0 and Debug.enabled:
            self.logger.log("DBG", f"adb shell fail: {cmd} | {err}")
        return out

    def is_connected(self) -> bool:
        rc, out, _ = self.run(["get-state"], timeout=3.0)
        return rc == 0 and "device" in out

    def devices(self) -> List[str]:
        rc, out, _ = self.run(["devices"], timeout=4.0)
        if rc != 0:
            return []
        devs = []
        for line in out.splitlines():
            if "\tdevice" in line:
                devs.append(line.split("\t")[0].strip())
        return devs

    # ---- FAST PATH: 1x ps p/ todos + 1x top p/ todos ----

    def ps_map(self) -> Dict[str, str]:
        """
        Retorna {process_name: pid} usando 1 chamada.
        Em Android, NAME geralmente é o pacote.
        """
        out = self.shell("ps -A", timeout=6.0)
        mp: Dict[str, str] = {}
        for ln in out.splitlines():
            s = ln.strip()
            if not s or s.lower().startswith("user"):
                continue
            parts = s.split()
            if len(parts) < 2:
                continue
            # PID normalmente é o 2º token
            pid = parts[1] if parts[1].isdigit() else None
            if pid is None:
                # fallback: procura primeiro token numérico
                for tok in parts:
                    if tok.isdigit():
                        pid = tok
                        break
            if not pid:
                continue
            name = parts[-1]
            mp[name] = pid
        return mp

    def top_cpu_map(self) -> Dict[str, float]:
        """
        Retorna {pid: cpu%} usando 1 chamada.
        """
        out = self.shell("top -n 1 -b", timeout=6.0)
        cpu_by_pid: Dict[str, float] = {}
        for ln in out.splitlines():
            s = ln.strip()
            if not s:
                continue
            parts = s.replace(",", ".").split()
            # linha de processo: deve ter algum pid numérico
            pid = None
            # muitos tops: PID está no 1º token
            if parts and parts[0].isdigit():
                pid = parts[0]
            else:
                # procura token numérico "bem provável"
                for tok in parts[:4]:
                    if tok.isdigit():
                        pid = tok
                        break
            if not pid:
                continue
            # acha token com %
            cpu = None
            for tok in parts:
                if tok.endswith("%"):
                    try:
                        cpu = float(tok[:-1])
                        break
                    except Exception:
                        pass
            if cpu is None:
                # fallback: pega algum float 0..100
                for tok in parts:
                    try:
                        v = float(tok)
                        if 0.0 <= v <= 100.0:
                            cpu = v
                            break
                    except Exception:
                        continue
            if cpu is None:
                continue
            cpu_by_pid[pid] = cpu
        return cpu_by_pid

    def force_stop(self, package: str) -> None:
        self.shell(f"am force-stop {package}", timeout=5.0)

    def launch_monkey(self, package: str) -> None:
        self.shell(f"monkey -p {package} -c android.intent.category.LAUNCHER 1", timeout=6.0)

    def launch_vip(self, package: str, activity: str, url: str) -> None:
        # sh -c já está ativo, então podemos usar aspas com segurança:
        cmd = f'am start -n "{package}/{activity}" -a android.intent.action.VIEW -d "{url}"'
        self.shell(cmd, timeout=8.0)

    def input_key(self, keycode: int) -> None:
        self.shell(f"input keyevent {keycode}", timeout=3.0)

    def input_tap(self, x: int, y: int) -> None:
        self.shell(f"input tap {x} {y}", timeout=3.0)

    def ui_dump(self) -> str:
        # dump para /sdcard e lê
        self.shell("uiautomator dump /sdcard/uidump.xml >/dev/null 2>&1 || true", timeout=6.0)
        return self.shell("cat /sdcard/uidump.xml 2>/dev/null || true", timeout=6.0)

# =========================
# DASHBOARD RENDER
# =========================

class Dashboard:
    def __init__(self):
        self.frame = 0

    def render(self, title: str, subtitle: str, devline: str, rows: List[str], logs: List[str], footer: str) -> None:
        w, h = Terminal.size()
        Terminal.clear_home()

        def line(text: str) -> str:
            return "│" + fit(text, w - 2) + "│"

        top = "┌" + "─" * (w - 2) + "┐"
        sep = "├" + "─" * (w - 2) + "┤"
        bot = "└" + "─" * (w - 2) + "┘"
        blank = "│" + " " * (w - 2) + "│"

        print(top)
        print(line(f"{title}  {SPINNER[self.frame % len(SPINNER)]}"))
        print(line(subtitle))
        print(line(devline))
        print(sep)

        # rows
        max_rows = max(3, h - 3 - 1 - 10)  # heurística
        for r in rows[:max_rows]:
            print(line(r))

        print(sep)

        # logs cabem no resto
        log_space = max(3, h - (4 + 1 + min(len(rows), max_rows) + 1 + 3))
        tail = logs[-log_space:]
        for lg in tail:
            print(line(lg))
        for _ in range(max(0, log_space - len(tail))):
            print(blank)

        print(sep)
        print(line(footer))
        print(bot)

        sys.stdout.flush()
        self.frame += 1

# =========================
# PLAY GAMES POPUP DISMISS
# =========================

def dismiss_play_games_popup(adb: ADB, logger: Logger) -> bool:
    """
    Fecha o popup do Google Play Games (Create a profile) automaticamente.
    Estratégia:
      1) BACK 2x
      2) uiautomator dump e clicar em "Not now" / "Agora não" etc.
    """
    # BACK 2x (muitas vezes resolve)
    adb.input_key(4)
    time.sleep(0.35)
    adb.input_key(4)
    time.sleep(0.35)

    xml = adb.ui_dump()
    if not xml:
        return False

    # textos comuns
    targets = [
        "Not now", "Agora não", "AGORA NÃO", "NOT NOW",
        "Skip", "Pular", "Ignorar", "Cancel", "Cancelar"
    ]

    for txt in targets:
        m = re.search(rf'text="{re.escape(txt)}".*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml, re.S)
        if m:
            x1, y1, x2, y2 = map(int, m.groups())
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            adb.input_tap(cx, cy)
            logger.log("INF", f"Popup Play Games fechado clicando: {txt}")
            time.sleep(0.4)
            return True

    # fallback: tenta achar por "Create a profile" e mandar BACK
    if "Create a profile" in xml or "Criar um perfil" in xml:
        adb.input_key(4)
        time.sleep(0.3)
        return True

    return False

# =========================
# MONITOR CORE (otimizado)
# =========================

class Monitor:
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg
        Debug.enabled = bool(cfg.get("debug", True))

        self.logger = Logger(LOG_FILE, max_mem=int(cfg.get("log_max_memory", 250)))
        self.webhook = Webhook(cfg, self.logger)

        self.adb = ADB(
            serial=str(cfg.get("adb_serial", "")).strip(),
            timeout=float(cfg.get("adb_timeout", 6.0)),
            logger=self.logger
        )

        self.ui = Dashboard()
        self.term = Terminal()

        self.qcmd: queue.Queue = queue.Queue()
        self.poller: Optional[ControlPoller] = None
        self.local_server: Optional[LocalControlServer] = None

        self.running = True
        self.paused = False

        self.hist: Dict[str, List[float]] = {}
        self.low_strikes: Dict[str, int] = {}
        self.freeze_strikes: Dict[str, int] = {}
        self.cooldown_until: Dict[str, float] = {}
        self.last_action: Dict[str, str] = {}
        self.last_snapshot: Dict[str, Dict[str, Any]] = {}

    def start_bg(self):
        if (self.cfg.get("control_url") or "").strip():
            self.poller = ControlPoller(self.cfg, self.qcmd, self.logger)
            self.poller.start()

        if bool(self.cfg.get("local_control_server", False)):
            host = str(self.cfg.get("local_control_host", "127.0.0.1"))
            port = int(self.cfg.get("local_control_port", 8765))
            self.local_server = LocalControlServer(host, port, self.qcmd, self.logger)
            self.local_server.start()

    def stop_bg(self):
        if self.poller:
            self.poller.stop()
        if self.local_server:
            self.local_server.stop()

    def log(self, level: str, msg: str, pkg: str = ""):
        self.logger.log(level, msg, pkg=pkg)
        if self.cfg.get("webhook_notify_events", True) and level in ("INF", "WRN", "ERR"):
            self.webhook.notify(level, {"pkg": pkg, "msg": msg})

    def send_ack(self, ack: Dict[str, Any]):
        url = (self.cfg.get("control_ack_url") or "").strip() or (self.cfg.get("webhook_url") or "").strip()
        if not url:
            return
        # se for discord webhook, manda como content
        mode = (self.cfg.get("webhook_mode") or "auto").lower()
        if mode == "auto":
            if "discord.com/api/webhooks" in url or "discordapp.com/api/webhooks" in url:
                mode = "discord"
            else:
                mode = "json"
        if mode == "discord":
            payload = {"content": f"**CONTROL_ACK**\n```json\n{json.dumps(ack, ensure_ascii=False, indent=2)}\n```"}
        else:
            payload = {"event": "CONTROL_ACK", "data": ack}
        http_post_json(url, payload, headers={}, timeout=6.0)

    def restart_pkg(self, pkg: str, reason: str):
        now = time.time()
        cd = float(self.cfg.get("restart_cooldown", 10.0))
        if self.cooldown_until.get(pkg, 0) > now:
            self.last_action[pkg] = f"cooldown {int(self.cooldown_until[pkg]-now)}s"
            return

        self.last_action[pkg] = f"restarting ({reason})"
        self.log("WRN", f"Restart: {reason}", pkg=pkg)

        try:
            self.adb.force_stop(pkg)
            time.sleep(1.0)

            if (self.cfg.get("launch_mode") or "vip").lower() == "vip":
                self.adb.launch_vip(pkg, str(self.cfg.get("proto_activity")), str(self.cfg.get("web_link")))
            else:
                self.adb.launch_monkey(pkg)

            # tenta fechar popup após launch
            if bool(self.cfg.get("dismiss_play_games", True)):
                time.sleep(1.2)
                dismiss_play_games_popup(self.adb, self.logger)

        except Exception as e:
            self.log("ERR", f"Falha restart: {e}", pkg=pkg)

        self.cooldown_until[pkg] = time.time() + cd
        self.low_strikes[pkg] = 0
        self.freeze_strikes[pkg] = 0

    def handle_commands(self):
        while True:
            try:
                cmd = self.qcmd.get_nowait()
            except queue.Empty:
                return
            if not isinstance(cmd, dict):
                continue

            c = (cmd.get("cmd") or "").lower().strip()
            cid = cmd.get("id", "")
            ack = {"id": cid, "cmd": c, "ok": True, "result": ""}

            try:
                if c == "toggle_debug":
                    state = Debug.toggle()
                    self.cfg["debug"] = state
                    save_config(self.cfg)
                    ack["result"] = f"debug={'ON' if state else 'OFF'}"
                    self.log("INF", ack["result"])

                elif c == "pause":
                    self.paused = True
                    ack["result"] = "paused"
                    self.log("INF", "Monitor pausado")

                elif c == "resume":
                    self.paused = False
                    ack["result"] = "resumed"
                    self.log("INF", "Monitor retomado")

                elif c == "restart_all":
                    for p in self.cfg.get("packages", []):
                        self.restart_pkg(p, "remote restart_all")
                    ack["result"] = "restart_all triggered"

                elif c == "restart":
                    pkg = (cmd.get("package") or "").strip()
                    idx = cmd.get("index", None)
                    pkgs = self.cfg.get("packages", [])
                    if pkg and pkg in pkgs:
                        self.restart_pkg(pkg, "remote restart")
                        ack["result"] = f"restart {pkg}"
                    elif idx is not None:
                        i = int(idx)
                        if 0 <= i < len(pkgs):
                            self.restart_pkg(pkgs[i], "remote restart index")
                            ack["result"] = f"restart index={i} pkg={pkgs[i]}"
                        else:
                            ack["ok"] = False
                            ack["result"] = "index out of range"
                    else:
                        ack["ok"] = False
                        ack["result"] = "missing package/index"

                elif c == "set_threshold":
                    v = float(cmd.get("value"))
                    self.cfg["low_cpu_threshold"] = v
                    save_config(self.cfg)
                    ack["result"] = f"low_cpu_threshold={v}"

                elif c == "set_interval":
                    v = float(cmd.get("value"))
                    self.cfg["check_interval"] = max(0.5, v)
                    save_config(self.cfg)
                    ack["result"] = f"check_interval={self.cfg['check_interval']}"

                elif c == "shutdown":
                    ack["result"] = "shutting down"
                    self.running = False

                elif c == "ping":
                    ack["result"] = "pong"

                else:
                    ack["ok"] = False
                    ack["result"] = f"unknown cmd: {c}"

            except Exception as e:
                ack["ok"] = False
                ack["result"] = str(e)
                self.log("ERR", f"Erro cmd: {e}")

            try:
                self.send_ack(ack)
            except Exception:
                pass

    def read_key(self) -> Optional[str]:
        if not self.term.is_tty:
            return None
        try:
            import select
            r, _, _ = select.select([sys.stdin], [], [], 0)
            if r:
                return sys.stdin.read(1)
        except Exception:
            return None
        return None

    def ui_rows(self) -> List[str]:
        pkgs = self.cfg.get("packages", [])
        rows = []
        rows.append("IDX  PACKAGE                     PID        CPU%   BAR            GRAPH                ST  ACTION")
        for i, p in enumerate(pkgs):
            snap = self.last_snapshot.get(p, {"pid": "-", "cpu": 0.0, "status": "?", "package": p})
            pid = str(snap.get("pid", "-"))
            cpu = float(snap.get("cpu", 0.0))
            status = str(snap.get("status", "?"))

            self.hist.setdefault(p, [])
            g = sparkline(self.hist[p], vmax=100.0, width=20)
            b = bar(cpu, 12)

            low = self.low_strikes.get(p, 0)
            frz = self.freeze_strikes.get(p, 0)
            st = f"{status}:{low}/{frz}"

            act = self.last_action.get(p, "")
            pkgshort = p if len(p) <= 26 else (p[:25] + "…")

            rows.append(f"{i:>3}  {pkgshort:<26} {pid:<9} {cpu:>6.1f}  {b}  {g}  {st:<9} {act}")
        return rows

    def run(self):
        def on_sig(*_):
            self.running = False
        signal.signal(signal.SIGINT, on_sig)
        signal.signal(signal.SIGTERM, on_sig)

        self.start_bg()
        self.term.enter()
        self.log("INF", "Monitor iniciado")

        next_check = time.time()
        next_ui = time.time()
        last_adb_ok = None

        try:
            while self.running:
                # comandos remotos/locais
                self.handle_commands()

                # hotkeys
                key = self.read_key()
                if key:
                    k = key.lower()
                    if k == "q":
                        self.running = False
                    elif k == "d":
                        state = Debug.toggle()
                        self.cfg["debug"] = state
                        save_config(self.cfg)
                        self.log("INF", f"DEBUG {'ON' if state else 'OFF'}")
                    elif k == "p":
                        self.paused = not self.paused
                        self.log("INF", f"{'PAUSADO' if self.paused else 'RETOMADO'}")
                    elif k == "r":
                        for p in self.cfg.get("packages", []):
                            self.restart_pkg(p, "hotkey restart_all")
                    elif k.isdigit():
                        idx = int(k) - 1
                        pkgs = self.cfg.get("packages", [])
                        if 0 <= idx < len(pkgs):
                            self.restart_pkg(pkgs[idx], f"hotkey restart idx={idx}")

                now = time.time()

                adb_ok = self.adb.is_connected()
                if adb_ok != last_adb_ok:
                    last_adb_ok = adb_ok
                    self.log("INF" if adb_ok else "WRN", f"ADB {'CONNECTED' if adb_ok else 'DISCONNECTED'}")

                # coleta
                if now >= next_check:
                    next_check = now + float(self.cfg.get("check_interval", 2.0))

                    if not self.paused and adb_ok:
                        # 1x ps + 1x top
                        ps = self.adb.ps_map()
                        cpu_map = self.adb.top_cpu_map()

                        low_thr = float(self.cfg.get("low_cpu_threshold", 5.0))
                        frz_thr = float(self.cfg.get("freeze_cpu_threshold", 0.5))
                        low_need = int(self.cfg.get("lowcpu_strikes", 3))
                        frz_need = int(self.cfg.get("freeze_strikes", 4))

                        for pkg in self.cfg.get("packages", []):
                            pid = ps.get(pkg)
                            if not pid:
                                self.last_snapshot[pkg] = {"pid": "-", "cpu": 0.0, "status": "OFFLINE", "package": pkg}
                                self.restart_pkg(pkg, "offline")
                                continue

                            cpu = float(cpu_map.get(pid, 0.0))
                            self.hist.setdefault(pkg, []).append(cpu)
                            if len(self.hist[pkg]) > 120:
                                self.hist[pkg] = self.hist[pkg][-120:]

                            # strikes
                            if cpu <= low_thr:
                                self.low_strikes[pkg] = self.low_strikes.get(pkg, 0) + 1
                            else:
                                self.low_strikes[pkg] = 0

                            if cpu <= frz_thr:
                                self.freeze_strikes[pkg] = self.freeze_strikes.get(pkg, 0) + 1
                            else:
                                self.freeze_strikes[pkg] = 0

                            status = "OK"
                            if self.freeze_strikes.get(pkg, 0) >= frz_need:
                                status = "FREEZE"
                                self.restart_pkg(pkg, f"freeze cpu<= {frz_thr}% ({frz_need}x)")
                            elif cpu <= low_thr:
                                status = "LOWCPU"
                                if self.low_strikes.get(pkg, 0) >= low_need:
                                    self.last_action[pkg] = f"lowcpu {self.low_strikes[pkg]}x"
                            else:
                                self.last_action[pkg] = ""

                            self.last_snapshot[pkg] = {"pid": pid, "cpu": cpu, "status": status, "package": pkg}

                # UI
                if now >= next_ui:
                    next_ui = now + float(self.cfg.get("ui_refresh", 0.2))

                    title = "ROBLOX CLUSTER MONITOR PRO"
                    sub = (
                        f"interval={self.cfg.get('check_interval')}s  refresh={self.cfg.get('ui_refresh')}s  "
                        f"debug={'ON' if Debug.enabled else 'OFF'}  paused={'YES' if self.paused else 'NO'}"
                    )
                    dev = self.adb.serial or "auto"
                    devline = (
                        f"ADB={'OK' if adb_ok else 'NO DEVICE'}  device={dev}  pkgs={len(self.cfg.get('packages', []))}  "
                        f"webhook={'ON' if (self.cfg.get('webhook_url') or '').strip() else 'OFF'}  "
                        f"control={'ON' if (self.cfg.get('control_url') or '').strip() else 'OFF'}"
                    )

                    rows = self.ui_rows()
                    logs = self.logger.tail(60)
                    self.ui.render(title, sub, devline, rows, logs, HELP_TEXT)

                time.sleep(0.02)

        finally:
            self.stop_bg()
            self.term.exit()
            self.log("INF", "Monitor encerrado")

# =========================
# MENU / SETUP
# =========================

def adb_detect_packages(adb: ADB) -> List[str]:
    out = adb.shell("pm list packages | grep roblox || true", timeout=6.0)
    pkgs = []
    for ln in out.splitlines():
        ln = ln.strip()
        if ln.startswith("package:"):
            pkgs.append(ln.replace("package:", "").strip())
    return pkgs

def pick_adb_device(adb: ADB) -> str:
    devs = adb.devices()
    if not devs:
        return ""
    if len(devs) == 1:
        return devs[0]
    print("\nDispositivos ADB:")
    for i, d in enumerate(devs, 1):
        print(f"{i}) {d}")
    try:
        c = int(input("Escolha: ").strip())
        if 1 <= c <= len(devs):
            return devs[c-1]
    except Exception:
        pass
    return devs[0]

def print_control_examples():
    print("\n=== EXEMPLOS control_url (GET -> JSON) ===")
    print("Lista:")
    print("""
[
  {"id": 1, "cmd": "toggle_debug"},
  {"id": 2, "cmd": "restart", "package": "com.roblox.client1"},
  {"id": 3, "cmd": "set_threshold", "value": 6.5},
  {"id": 4, "cmd": "pause"},
  {"id": 5, "cmd": "resume"},
  {"id": 6, "cmd": "restart_all"},
  {"id": 7, "cmd": "shutdown"}
]
""".strip())
    print("\nServidor local opcional:")
    print('curl -s -X POST http://127.0.0.1:8765/cmd -H "Content-Type: application/json" -d \'{"cmd":"restart_all"}\'')
    print()

def menu():
    cfg = load_config()
    logger = Logger(LOG_FILE, max_mem=int(cfg.get("log_max_memory", 250)))
    adb = ADB(serial=str(cfg.get("adb_serial","")).strip(), timeout=float(cfg.get("adb_timeout", 6.0)), logger=logger)

    while True:
        os.system("clear" if os.name != "nt" else "cls")
        print("ROBLOX CLUSTER MONITOR PRO\n")
        print(f"Config: {CONFIG_FILE}")
        print(f"ADB serial: {cfg.get('adb_serial') or '(auto)'}")
        print(f"Packages: {len(cfg.get('packages', []))}")
        print(f"interval: {cfg.get('check_interval')}s | low_cpu: {cfg.get('low_cpu_threshold')}% | freeze: {cfg.get('freeze_cpu_threshold')}%")
        print(f"webhook: {'ON' if (cfg.get('webhook_url') or '').strip() else 'OFF'} | control: {'ON' if (cfg.get('control_url') or '').strip() else 'OFF'}")
        print(f"dismiss play games: {'ON' if cfg.get('dismiss_play_games', True) else 'OFF'}")
        print("\n1) Detectar pacotes Roblox (adb)")
        print("2) Escolher device ADB (serial)")
        print("3) Editar web_link / launch_mode / proto_activity")
        print("4) Configurar webhook (notificações)")
        print("5) Configurar controle remoto (control_url/token/ack)")
        print("6) Ativar servidor local de comandos (POST /cmd)")
        print("7) Mostrar exemplos de comandos")
        print("8) Iniciar monitor")
        print("9) Sair")

        choice = input("\n> ").strip()

        if choice == "1":
            if not adb.is_connected():
                print("\nADB não conectado. Rode: adb devices e autorize no celular/emulador.")
                input("\nEnter...")
                continue
            pkgs = adb_detect_packages(adb)
            cfg["packages"] = pkgs
            save_config(cfg)
            print("\nPacotes detectados:")
            for p in pkgs:
                print(" -", p)
            input("\nEnter...")

        elif choice == "2":
            serial = pick_adb_device(adb)
            cfg["adb_serial"] = serial
            save_config(cfg)
            adb.serial = serial
            print("\nSelecionado:", serial or "(auto)")
            input("\nEnter...")

        elif choice == "3":
            print("\nweb_link atual:", cfg.get("web_link"))
            wl = input("Novo web_link (Enter mantém): ").strip()
            if wl:
                cfg["web_link"] = wl

            print("\nlaunch_mode atual:", cfg.get("launch_mode"))
            lm = input("launch_mode (vip/monkey) (Enter mantém): ").strip().lower()
            if lm in ("vip", "monkey"):
                cfg["launch_mode"] = lm

            print("\nproto_activity atual:", cfg.get("proto_activity"))
            pa = input("proto_activity (Enter mantém): ").strip()
            if pa:
                cfg["proto_activity"] = pa

            dp = input("\nFechar popup Play Games automaticamente? (s/n) (Enter mantém): ").strip().lower()
            if dp in ("s", "n"):
                cfg["dismiss_play_games"] = (dp == "s")

            save_config(cfg)
            input("\nEnter...")

        elif choice == "4":
            print("\nwebhook_url atual:", cfg.get("webhook_url") or "(vazio)")
            wh = input("Novo webhook_url (Enter mantém): ").strip()
            if wh:
                cfg["webhook_url"] = wh
            mode = input("webhook_mode (auto/discord/json) (Enter mantém): ").strip().lower()
            if mode in ("auto", "discord", "json"):
                cfg["webhook_mode"] = mode
            en = input("Notificar eventos? (s/n) (Enter mantém): ").strip().lower()
            if en in ("s", "n"):
                cfg["webhook_notify_events"] = (en == "s")
            save_config(cfg)
            input("\nEnter...")

        elif choice == "5":
            print("\ncontrol_url atual:", cfg.get("control_url") or "(vazio)")
            cu = input("Novo control_url (Enter mantém): ").strip()
            if cu:
                cfg["control_url"] = cu

            print("\ncontrol_token atual:", "SET" if (cfg.get("control_token") or "").strip() else "(vazio)")
            tk = input("Novo control_token (Enter mantém): ").strip()
            if tk:
                cfg["control_token"] = tk

            pi = input(f"control_poll_interval (atual {cfg.get('control_poll_interval')}): ").strip()
            try:
                if pi:
                    cfg["control_poll_interval"] = max(1.0, float(pi))
            except Exception:
                pass

            print("\ncontrol_ack_url atual:", cfg.get("control_ack_url") or "(vazio -> usa webhook_url)")
            au = input("Novo control_ack_url (Enter mantém): ").strip()
            if au:
                cfg["control_ack_url"] = au

            save_config(cfg)
            input("\nEnter...")

        elif choice == "6":
            cur = bool(cfg.get("local_control_server", False))
            print("\nServidor local atual:", "ON" if cur else "OFF")
            v = input("Ativar? (s/n): ").strip().lower()
            if v in ("s", "n"):
                cfg["local_control_server"] = (v == "s")
            if cfg["local_control_server"]:
                host = input(f"Host (atual {cfg.get('local_control_host')}): ").strip()
                port = input(f"Port (atual {cfg.get('local_control_port')}): ").strip()
                if host:
                    cfg["local_control_host"] = host
                try:
                    if port:
                        cfg["local_control_port"] = int(port)
                except Exception:
                    pass
            save_config(cfg)
            input("\nEnter...")

        elif choice == "7":
            print_control_examples()
            input("\nEnter...")

        elif choice == "8":
            cfg = load_config()
            m = Monitor(cfg)
            m.run()
            input("\nVoltou ao menu. Enter...")

        elif choice == "9":
            return

# =========================
# MAIN
# =========================

if __name__ == "__main__":
    menu()
