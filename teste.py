#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Roblox Cluster Monitor Pro (Terminal Dashboard)
- Dashboard dinâmico (sem spam) com ANSI + alternate screen
- Sparklines (gráfico CPU tempo real) + barras
- Detecção de offline / freeze / low cpu + restart/rejoin
- Debug toggle runtime (tecla D + remoto)
- Controle remoto via webhook (poll commands + ack) + notificação webhook
- Logs na tela + arquivo

Compatível: Linux / Termux (Python 3.8+). Sem dependências externas.
"""

import os
import sys
import time
import json
import shutil
import signal
import subprocess
import threading
import queue
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional, Dict, Any, List, Tuple

CONFIG_FILE = "monitor_config.json"
LOG_FILE = "monitor.log"

SPINNER = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
SPARK_CHARS = "▁▂▃▄▅▆▇█"

DEFAULT_CONFIG = {
    # --- Roblox / Launch ---
    "web_link": "https://www.roblox.com/games/1537690962/Bee-Swarm-Simulator",
    "proto_activity": "com.roblox.client.ActivityProtocolLaunch",  # pode ajustar se necessário
    "launch_mode": "vip",  # "vip" (am start com link) ou "monkey" (launcher)

    # --- Monitor ---
    "packages": [],              # detecta via menu
    "check_interval": 2.0,       # segundos (coleta adb)
    "ui_refresh": 0.20,          # segundos (fps do dashboard)
    "low_cpu_threshold": 5.0,    # %
    "freeze_cpu_threshold": 0.5, # %
    "freeze_strikes": 4,         # quantas coletas seguidas abaixo do freeze para reiniciar
    "lowcpu_strikes": 3,         # quantas coletas seguidas abaixo do low_cpu para marcar
    "restart_cooldown": 10.0,    # segundos por pacote

    # --- ADB ---
    "adb_serial": "",            # se quiser fixar device: "emulator-5554" etc
    "adb_timeout": 6.0,

    # --- Debug / Logs ---
    "debug": True,
    "log_max_memory": 250,

    # --- Webhooks ---
    # Notificação (Discord/Slack/custom)
    "webhook_url": "",
    "webhook_mode": "auto",      # "auto" | "discord" | "json"
    "webhook_notify_events": True,

    # Controle remoto (polling)
    # Sua URL deve retornar JSON com comandos (exemplos abaixo)
    "control_url": "",
    "control_poll_interval": 4.0,
    "control_token": "",         # opcional (enviado como header)
    "control_token_header": "X-Control-Token",

    # Servidor local opcional (POST /cmd)
    "local_control_server": False,
    "local_control_host": "127.0.0.1",
    "local_control_port": 8765
}

HELP_TEXT = "Teclas: [D]ebug  [P]ause  [R]estart all  [1..9] restart pkg  [Q]uit"


# ==========================================================
# UTIL / CONFIG
# ==========================================================

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


# ==========================================================
# DEBUG + LOGGER
# ==========================================================

class Debug:
    enabled: bool = True

    @staticmethod
    def toggle() -> bool:
        Debug.enabled = not Debug.enabled
        return Debug.enabled

class Logger:
    def __init__(self, filepath: str, max_mem: int = 200):
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

        if Debug.enabled and level in ("DBG", "ERR"):
            # debug imediato em stderr (fora da UI, mas a UI redesenha)
            # mantemos silencioso pra não "poluir"; a UI mostra logs
            pass

    def tail(self, n: int = 10) -> List[str]:
        with self._lock:
            return self._mem[-n:]


# ==========================================================
# TERMINAL (tela fixa, sem spam)
# ==========================================================

class Terminal:
    def __init__(self):
        self.is_tty = sys.stdin.isatty() and sys.stdout.isatty()
        self._orig_term = None

    def enter(self):
        if not self.is_tty:
            return
        # Alternate screen + hide cursor
        sys.stdout.write("\033[?1049h\033[?25l")
        sys.stdout.flush()
        # cbreak (captura tecla sem Enter)
        try:
            import termios, tty
            self._orig_term = termios.tcgetattr(sys.stdin.fileno())
            tty.setcbreak(sys.stdin.fileno())
        except Exception:
            self._orig_term = None

    def exit(self):
        if not self.is_tty:
            return
        # restore terminal mode
        try:
            if self._orig_term is not None:
                import termios
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._orig_term)
        except Exception:
            pass
        # show cursor + leave alternate screen
        sys.stdout.write("\033[?25h\033[?1049l")
        sys.stdout.flush()

    @staticmethod
    def clear_home():
        sys.stdout.write("\033[2J\033[H")

    @staticmethod
    def size() -> Tuple[int, int]:
        sz = shutil.get_terminal_size(fallback=(100, 30))
        return sz.columns, sz.lines


def fit(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text + " " * (width - len(text))
    if width <= 1:
        return text[:width]
    return text[:width-1] + "…"


def sparkline(values: List[float], vmax: float = 100.0, width: int = 20) -> str:
    if width <= 0:
        return ""
    if not values:
        return " " * width
    # pega os últimos width pontos
    tail = values[-width:]
    out = []
    for v in tail:
        if v < 0:
            v = 0
        if vmax <= 0:
            idx = 0
        else:
            frac = min(1.0, max(0.0, v / vmax))
            idx = int(frac * (len(SPARK_CHARS) - 1))
        out.append(SPARK_CHARS[idx])
    return "".join(out)


def bar(percent: float, width: int = 12) -> str:
    if width <= 0:
        return ""
    p = max(0.0, min(100.0, percent))
    filled = int(round((p / 100.0) * width))
    return "█" * filled + "░" * (width - filled)


# ==========================================================
# WEBHOOK (notify) + CONTROL (poll commands) + LOCAL SERVER
# ==========================================================

def _http_post_json(url: str, payload: Dict[str, Any], headers: Dict[str, str], timeout: float) -> Tuple[bool, str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **headers}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return False, str(e)

def _http_get_json(url: str, headers: Dict[str, str], timeout: float) -> Tuple[bool, Any, str]:
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            return True, json.loads(raw), raw
    except Exception as e:
        return False, None, str(e)

class Webhook:
    def __init__(self, cfg: Dict[str, Any], logger: Logger):
        self.cfg = cfg
        self.logger = logger

    def _mode(self) -> str:
        mode = (self.cfg.get("webhook_mode") or "auto").lower()
        if mode == "auto":
            url = self.cfg.get("webhook_url", "")
            if "discord.com/api/webhooks" in url or "discordapp.com/api/webhooks" in url:
                return "discord"
            return "json"
        return mode

    def notify(self, event: str, data: Dict[str, Any]) -> None:
        url = self.cfg.get("webhook_url", "").strip()
        if not url:
            return
        if not self.cfg.get("webhook_notify_events", True):
            return

        mode = self._mode()
        payload: Dict[str, Any]

        if mode == "discord":
            # Discord webhook: usar "content"
            content = f"**{event}**\n```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```"
            payload = {"content": content}
        else:
            payload = {"event": event, "data": data, "ts": datetime.now().isoformat()}

        ok, resp = _http_post_json(url, payload, headers={}, timeout=6.0)
        if not ok:
            self.logger.log("ERR", f"Webhook notify falhou: {resp}")

class ControlPoller(threading.Thread):
    """
    Polling de comandos via URL (controle remoto).
    A URL deve retornar JSON:
      - Lista: [{"id": 1, "cmd": "restart", "package": "..."}]
      - Ou objeto: {"commands": [...]} ou {"id":..., "cmd":...}

    Comandos suportados:
      toggle_debug
      pause / resume
      restart_all
      restart (package ou index)
      set_threshold (value float)
      set_interval (value float)
      shutdown
      ping
    """
    def __init__(self, cfg: Dict[str, Any], cmd_queue: queue.Queue, logger: Logger):
        super().__init__(daemon=True)
        self.cfg = cfg
        self.cmd_queue = cmd_queue
        self.logger = logger
        self._stop = threading.Event()
        self.last_id = 0

    def stop(self):
        self._stop.set()

    def run(self):
        while not self._stop.is_set():
            url = (self.cfg.get("control_url") or "").strip()
            if not url:
                time.sleep(1.0)
                continue

            interval = float(self.cfg.get("control_poll_interval", 4.0))
            token = (self.cfg.get("control_token") or "").strip()
            token_header = (self.cfg.get("control_token_header") or "X-Control-Token").strip()

            headers = {}
            if token:
                headers[token_header] = token

            ok, obj, err = _http_get_json(url, headers=headers, timeout=6.0)
            if ok and obj is not None:
                cmds = []
                if isinstance(obj, list):
                    cmds = obj
                elif isinstance(obj, dict):
                    if "commands" in obj and isinstance(obj["commands"], list):
                        cmds = obj["commands"]
                    elif "cmd" in obj:
                        cmds = [obj]

                for c in cmds:
                    if not isinstance(c, dict):
                        continue
                    cid = c.get("id", 0)
                    try:
                        cid_int = int(cid)
                    except Exception:
                        cid_int = 0

                    # processa só novos ids (evita repetir)
                    if cid_int <= self.last_id:
                        continue

                    self.last_id = max(self.last_id, cid_int)
                    self.cmd_queue.put(c)
                    self.logger.log("INF", f"Cmd remoto enfileirado: {c.get('cmd')} (id={cid_int})")

            # silêncio em erro (pra não floodar), mas registra uma vez por ciclo
            elif not ok and err:
                self.logger.log("ERR", f"Control poll falhou: {err}")

            time.sleep(max(1.0, interval))

class LocalControlServer(threading.Thread):
    """
    Servidor local opcional:
      POST http://127.0.0.1:8765/cmd  body JSON {"cmd":"restart_all"} ...
    """
    def __init__(self, host: str, port: int, cmd_queue: queue.Queue, logger: Logger):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.cmd_queue = cmd_queue
        self.logger = logger
        self.httpd: Optional[HTTPServer] = None

    def run(self):
        cmd_queue = self.cmd_queue
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
                        cmd_queue.put(obj)
                        logger.log("INF", f"Cmd local recebido: {obj.get('cmd')}")
                        self.send_response(200); self.end_headers()
                        self.wfile.write(b'{"ok":true}')
                    else:
                        self.send_response(400); self.end_headers()
                        self.wfile.write(b'{"ok":false,"err":"invalid"}')
                except Exception as e:
                    self.send_response(400); self.end_headers()
                    self.wfile.write(json.dumps({"ok": False, "err": str(e)}).encode("utf-8"))

            def log_message(self, format, *args):
                # silencioso
                return

        try:
            self.httpd = HTTPServer((self.host, int(self.port)), Handler)
            self.logger.log("INF", f"Local control server ON: http://{self.host}:{self.port}/cmd")
            self.httpd.serve_forever()
        except Exception as e:
            self.logger.log("ERR", f"Local control server falhou: {e}")

    def stop(self):
        if self.httpd:
            try:
                self.httpd.shutdown()
            except Exception:
                pass


# ==========================================================
# ADB WRAPPER
# ==========================================================

class ADB:
    def __init__(self, serial: str = "", timeout: float = 6.0, logger: Optional[Logger] = None):
        self.serial = serial.strip()
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
            p = subprocess.run(
                self._base() + args,
                capture_output=True,
                text=True,
                timeout=t
            )
            return p.returncode, p.stdout.strip(), p.stderr.strip()
        except Exception as e:
            return 1, "", str(e)

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

    def shell(self, cmd: str, timeout: Optional[float] = None) -> str:
        rc, out, err = self.run(["shell"] + cmd.split(), timeout=timeout)
        if rc != 0 and self.logger and Debug.enabled:
            self.logger.log("DBG", f"adb shell falhou: {cmd} | {err}")
        return out

    def pidof(self, package: str) -> Optional[str]:
        out = self.shell(f"pidof {package}", timeout=3.0).strip()
        if out:
            return out.split()[0]

        # fallback: ps
        ps = self.shell(f"ps -A | grep {package}", timeout=4.0).strip()
        if ps:
            # formato comum: USER PID ... NAME
            parts = ps.split()
            if len(parts) >= 2:
                return parts[1]
        return None

    def cpu_of_pid(self, pid: str) -> float:
        if not pid:
            return 0.0

        # tenta top e pega o primeiro token que parece "12%" ou "12.3%"
        out = self.shell("top -n 1 -b", timeout=5.0)
        if not out:
            return 0.0

        # busca linha com pid no começo ou com pid isolado
        lines = out.splitlines()
        target = None
        for ln in lines:
            s = ln.strip()
            if s.startswith(pid + " ") or s.startswith(pid + "\t"):
                target = s
                break
        if not target:
            # fallback grep-like (mas sem grep pra não depender do busybox completo)
            for ln in lines:
                if f" {pid} " in f" {ln} ":
                    target = ln.strip()
                    break

        if not target:
            return 0.0

        tokens = target.replace(",", ".").split()
        # pega o primeiro token que tem % e é número
        for tok in tokens:
            if tok.endswith("%"):
                num = tok[:-1]
                try:
                    return float(num)
                except Exception:
                    pass
        # alguns topos não tem %, tenta achar float plausível
        for tok in tokens:
            try:
                v = float(tok)
                if 0.0 <= v <= 100.0:
                    return v
            except Exception:
                continue
        return 0.0

    def force_stop(self, package: str) -> None:
        self.shell(f"am force-stop {package}", timeout=5.0)

    def launch_monkey(self, package: str) -> None:
        self.shell(f"monkey -p {package} -c android.intent.category.LAUNCHER 1", timeout=6.0)

    def launch_vip(self, package: str, activity: str, url: str) -> None:
        # am start -n pkg/activity -a VIEW -d "url"
        cmd = f'am start -n {package}/{activity} -a android.intent.action.VIEW -d "{url}"'
        # shell split não lida com aspas; manda como "sh -c"
        self.shell(f'sh -c {json.dumps(cmd)}', timeout=8.0)


# ==========================================================
# UI DASHBOARD
# ==========================================================

class Dashboard:
    def __init__(self):
        self.frame = 0

    def render(
        self,
        title: str,
        subtitle: str,
        device_line: str,
        pkg_rows: List[str],
        logs: List[str],
        footer: str
    ) -> None:
        w, h = Terminal.size()
        Terminal.clear_home()

        top = "┌" + "─" * (w - 2) + "┐"
        bot = "└" + "─" * (w - 2) + "┘"
        mid = "│" + " " * (w - 2) + "│"

        def line(text: str) -> str:
            return "│" + fit(text, w - 2) + "│"

        # layout:
        # header 3 linhas
        # separator
        # tabela pacotes (até caber)
        # separator
        # logs (resto)
        # footer

        print(top)
        print(line(f"{title}  {SPINNER[self.frame % len(SPINNER)]}"))
        print(line(subtitle))
        print(line(device_line))
        print("├" + "─" * (w - 2) + "┤")

        # tabela pacotes
        for r in pkg_rows:
            print(line(r))

        print("├" + "─" * (w - 2) + "┤")

        # logs
        log_space = max(3, h - (3 + 1 + len(pkg_rows) + 1 + 2))  # aproximação
        tail = logs[-log_space:]
        for lg in tail:
            print(line(lg))
        # preenche espaço restante
        for _ in range(max(0, log_space - len(tail))):
            print(mid)

        print("├" + "─" * (w - 2) + "┤")
        print(line(footer))
        print(bot)

        sys.stdout.flush()
        self.frame += 1


# ==========================================================
# MONITOR
# ==========================================================

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

        self.cmd_q: queue.Queue = queue.Queue()
        self.poller: Optional[ControlPoller] = None
        self.local_server: Optional[LocalControlServer] = None

        # states
        self.running = True
        self.paused = False

        self.hist: Dict[str, List[float]] = {}   # cpu history por pkg
        self.low_strikes: Dict[str, int] = {}
        self.freeze_strikes: Dict[str, int] = {}
        self.cooldown_until: Dict[str, float] = {}
        self.last_action: Dict[str, str] = {}

        # usado pra UI e comandos
        self.last_snapshot: Dict[str, Dict[str, Any]] = {}

    def start_background(self):
        # control poller
        if (self.cfg.get("control_url") or "").strip():
            self.poller = ControlPoller(self.cfg, self.cmd_q, self.logger)
            self.poller.start()

        # local server
        if bool(self.cfg.get("local_control_server", False)):
            host = str(self.cfg.get("local_control_host", "127.0.0.1"))
            port = int(self.cfg.get("local_control_port", 8765))
            self.local_server = LocalControlServer(host, port, self.cmd_q, self.logger)
            self.local_server.start()

    def stop_background(self):
        if self.poller:
            self.poller.stop()
        if self.local_server:
            self.local_server.stop()

    def log(self, level: str, msg: str, pkg: str = ""):
        self.logger.log(level, msg, pkg=pkg)
        if self.cfg.get("webhook_notify_events", True) and level in ("INF", "WRN", "ERR"):
            # envia apenas eventos importantes (evita flood)
            self.webhook.notify(level, {"pkg": pkg, "msg": msg})

    def restart_pkg(self, package: str, reason: str):
        now = time.time()
        cd = float(self.cfg.get("restart_cooldown", 10.0))
        if self.cooldown_until.get(package, 0) > now:
            self.last_action[package] = f"cooldown {int(self.cooldown_until[package]-now)}s"
            return

        self.last_action[package] = f"restarting ({reason})"
        self.log("WRN", f"Restart: {reason}", pkg=package)

        try:
            self.adb.force_stop(package)
            time.sleep(1.2)

            mode = (self.cfg.get("launch_mode") or "vip").lower()
            if mode == "vip":
                self.adb.launch_vip(package, str(self.cfg.get("proto_activity")), str(self.cfg.get("web_link")))
            else:
                self.adb.launch_monkey(package)

            time.sleep(1.5)
        except Exception as e:
            self.log("ERR", f"Falha no restart: {e}", pkg=package)

        self.cooldown_until[package] = time.time() + cd
        self.low_strikes[package] = 0
        self.freeze_strikes[package] = 0

    def update_pkg(self, package: str) -> Dict[str, Any]:
        pid = self.adb.pidof(package)
        if not pid:
            self.restart_pkg(package, "offline")
            snap = {"pid": "-", "cpu": 0.0, "status": "OFFLINE", "package": package}
            return snap

        cpu = self.adb.cpu_of_pid(pid)
        cpu = float(cpu if cpu is not None else 0.0)

        # history
        self.hist.setdefault(package, []).append(cpu)
        if len(self.hist[package]) > 120:
            self.hist[package] = self.hist[package][-120:]

        low_thr = float(self.cfg.get("low_cpu_threshold", 5.0))
        frz_thr = float(self.cfg.get("freeze_cpu_threshold", 0.5))

        # strikes
        if cpu <= low_thr:
            self.low_strikes[package] = self.low_strikes.get(package, 0) + 1
        else:
            self.low_strikes[package] = 0

        if cpu <= frz_thr:
            self.freeze_strikes[package] = self.freeze_strikes.get(package, 0) + 1
        else:
            self.freeze_strikes[package] = 0

        # decide
        freeze_n = int(self.cfg.get("freeze_strikes", 4))
        if self.freeze_strikes.get(package, 0) >= freeze_n:
            self.restart_pkg(package, f"freeze cpu<= {frz_thr}% ({freeze_n}x)")
            status = "FREEZE"
        else:
            if cpu <= low_thr:
                status = "LOWCPU"
            else:
                status = "OK"

        snap = {"pid": pid, "cpu": cpu, "status": status, "package": package}
        return snap

    def handle_commands(self):
        # processa fila de comandos (remoto/local)
        while True:
            try:
                cmd = self.cmd_q.get_nowait()
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
                    if pkg:
                        self.restart_pkg(pkg, "remote restart")
                        ack["result"] = f"restart {pkg}"
                    elif idx is not None:
                        try:
                            i = int(idx)
                            pkgs = self.cfg.get("packages", [])
                            if 0 <= i < len(pkgs):
                                self.restart_pkg(pkgs[i], "remote restart index")
                                ack["result"] = f"restart index={i} pkg={pkgs[i]}"
                            else:
                                ack["ok"] = False
                                ack["result"] = "index out of range"
                        except Exception:
                            ack["ok"] = False
                            ack["result"] = "invalid index"
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

                elif c == "ping":
                    ack["result"] = "pong"

                elif c == "shutdown":
                    ack["result"] = "shutting down"
                    self.running = False

                else:
                    ack["ok"] = False
                    ack["result"] = f"unknown cmd: {c}"

            except Exception as e:
                ack["ok"] = False
                ack["result"] = str(e)
                self.log("ERR", f"Erro cmd remoto: {e}")

            # manda ACK pro webhook (se configurado)
            if (self.cfg.get("webhook_url") or "").strip():
                self.webhook.notify("CONTROL_ACK", ack)

    def read_key(self) -> Optional[str]:
        if not self.term.is_tty:
            return None
        try:
            import select
            r, _, _ = select.select([sys.stdin], [], [], 0)
            if r:
                ch = sys.stdin.read(1)
                return ch
        except Exception:
            return None
        return None

    def ui_rows(self) -> List[str]:
        # monta tabela compacta:
        # idx  pkgshort  pid  cpu  bar  spark  strikes action
        w, _ = Terminal.size()

        pkgs = self.cfg.get("packages", [])
        rows = []

        header = "IDX  PACKAGE                     PID        CPU%   BAR            GRAPH                ST  ACTION"
        rows.append(header)

        for i, p in enumerate(pkgs):
            snap = self.last_snapshot.get(p, {"pid": "-", "cpu": 0.0, "status": "?", "package": p})
            pid = str(snap.get("pid", "-"))
            cpu = float(snap.get("cpu", 0.0))
            status = str(snap.get("status", "?"))

            # barras
            b = bar(cpu, 12)
            g = sparkline(self.hist.get(p, []), vmax=100.0, width=20)

            low = self.low_strikes.get(p, 0)
            frz = self.freeze_strikes.get(p, 0)
            st = f"{status}:{low}/{frz}"

            act = self.last_action.get(p, "")
            pkgshort = p
            if len(pkgshort) > 26:
                pkgshort = pkgshort[:25] + "…"

            row = f"{i:>3}  {pkgshort:<26} {pid:<9} {cpu:>6.1f}  {b}  {g}  {st:<9} {act}"
            rows.append(row)

        # garante não estourar tela (vai cortar via fit)
        return rows

    def run(self):
        # signals
        def on_sig(*_):
            self.running = False
        signal.signal(signal.SIGINT, on_sig)
        signal.signal(signal.SIGTERM, on_sig)

        self.start_background()
        self.term.enter()

        self.log("INF", "Monitor iniciado")

        next_check = time.time()
        next_ui = time.time()
        last_adb_ok = False

        try:
            while self.running:
                # comandos remotos/locais
                self.handle_commands()

                # tecla
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

                # ADB connection status
                adb_ok = self.adb.is_connected()
                if adb_ok != last_adb_ok:
                    last_adb_ok = adb_ok
                    self.log("INF" if adb_ok else "WRN", f"ADB {'CONNECTED' if adb_ok else 'DISCONNECTED'}")

                # coleta status (no intervalo), se não pausado e adb ok
                if now >= next_check:
                    next_check = now + float(self.cfg.get("check_interval", 2.0))

                    if not self.paused and adb_ok:
                        for p in self.cfg.get("packages", []):
                            try:
                                snap = self.update_pkg(p)
                                self.last_snapshot[p] = snap
                                # ação padrão se tudo ok
                                if snap.get("status") == "OK":
                                    self.last_action[p] = ""
                                elif snap.get("status") == "LOWCPU":
                                    strikes = self.low_strikes.get(p, 0)
                                    if strikes >= int(self.cfg.get("lowcpu_strikes", 3)):
                                        self.last_action[p] = f"lowcpu {strikes}x"
                            except Exception as e:
                                self.log("ERR", f"update_pkg falhou: {e}", pkg=p)
                    elif not adb_ok:
                        # mantém UI viva, só não coleta
                        pass

                # render UI
                if now >= next_ui:
                    next_ui = now + float(self.cfg.get("ui_refresh", 0.2))

                    title = "ROBLOX CLUSTER MONITOR PRO"
                    sub = f"interval={self.cfg.get('check_interval')}s  refresh={self.cfg.get('ui_refresh')}s  debug={'ON' if Debug.enabled else 'OFF'}  paused={'YES' if self.paused else 'NO'}"
                    dev = self.adb.serial or "auto"
                    devline = f"ADB={('OK' if adb_ok else 'NO DEVICE')}  device={dev}  pkgs={len(self.cfg.get('packages', []))}  webhook={'ON' if (self.cfg.get('webhook_url') or '').strip() else 'OFF'}  control={'ON' if (self.cfg.get('control_url') or '').strip() else 'OFF'}"

                    rows = self.ui_rows()
                    logs = self.logger.tail(50)
                    footer = HELP_TEXT

                    self.ui.render(title, sub, devline, rows, logs, footer)

                time.sleep(0.02)

        finally:
            self.stop_background()
            self.term.exit()
            self.log("INF", "Monitor encerrado")


# ==========================================================
# MENU / SETUP
# ==========================================================

def adb_detect_packages(adb: ADB) -> List[str]:
    # tenta achar pacotes roblox
    out = adb.shell("pm list packages | grep roblox", timeout=6.0)
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

def print_examples():
    print("\n=== EXEMPLOS DE CONTROLE REMOTO (control_url) ===")
    print("Sua control_url deve retornar JSON. Exemplo (lista):")
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
    print("\nSe você preferir objeto:")
    print("""
{"commands":[{"id": 10, "cmd": "ping"}]}
""".strip())
    print("\nACKs são enviados para webhook_url como event CONTROL_ACK.\n")

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
        print(f"check_interval: {cfg.get('check_interval')}s | low_cpu_threshold: {cfg.get('low_cpu_threshold')}%")
        print(f"webhook: {'ON' if (cfg.get('webhook_url') or '').strip() else 'OFF'} | control: {'ON' if (cfg.get('control_url') or '').strip() else 'OFF'}")
        print("\n1) Detectar pacotes Roblox (adb)")
        print("2) Escolher device ADB (serial)")
        print("3) Editar web_link / launch_mode")
        print("4) Configurar webhook (notificações)")
        print("5) Configurar control_url (controle remoto)")
        print("6) Mostrar exemplos de comandos remotos")
        print("7) Iniciar monitor")
        print("8) Sair")

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
            save_config(cfg)
            input("\nEnter...")

        elif choice == "6":
            print_examples()
            input("\nEnter...")

        elif choice == "7":
            cfg = load_config()  # recarrega
            m = Monitor(cfg)
            m.run()
            input("\nVoltou ao menu. Enter...")

        elif choice == "8":
            return


if __name__ == "__main__":
    menu()
