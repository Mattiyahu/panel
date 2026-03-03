#!/usr/bin/env python3
"""
🖥️ Roblox AutoRejoin - Hacker Theme 🖥️
Interface cyberpunk para monitoramento de clones Roblox
Versão: 4.2 - Deeplink Edition (TITANIYAHU)

FIX PRINCIPAL:
- Para link antigo com privateServerLinkCode:
  https://www.roblox.com/games/<placeId>/...?privateServerLinkCode=XXXX
  -> roblox://navigation/game_details?gameId=<placeId>&privateServerLinkCode=XXXX
- Abre SOMENTE deeplink (não abre navegador)

Requisitos:
- Termux + android-tools (adb)
- ADB conectado (USB ou Wireless Debugging)
"""

import os
import sys
import time
import json
import signal
import subprocess
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs

# ============================================
# 🎮 CONFIGURAÇÃO
# ============================================
CONFIG_FILE = "hacker_config.json"
DEFAULT_CONFIG = {
    # Seu link antigo (https + privateServerLinkCode) funciona,
    # o script converte automaticamente para roblox://game_details...
    "web_link": "https://www.roblox.com/games/1537690962/Bee-Swarm-Simulator?privateServerLinkCode=05888256464342538313491710978310",

    "webhook_url": "",
    "check_interval": 10,

    "low_cpu_threshold": 8.0,
    "max_lowcpu_time": 30,      # segundos (antes era 10, muito agressivo)
    "cooldown_time": 12,

    "launch_wait_sec": 14,      # tempo para esperar PID após abrir
    "packages": [],

    # ADB opcional
    "adb_serial": "",           # se usar adb -s <serial>
}

# ============================================
# 🎨 TEMA HACKER CYBERPUNK
# ============================================
class HackerTheme:
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
    GREEN_MEDIUM = "\033[38;5;28m"
    GREEN_LIGHT = "\033[38;5;34m"
    GREEN_NEON = "\033[38;5;82m"
    GREEN_DIM = "\033[38;5;22m"   # corrigido (v4 chamava GREEN_DIM sem existir)

    BG_BLACK = "\033[48;5;232m"

    GLITCH = f"{BLINK}{RED}"
    HIGHLIGHT = f"{BOLD}{GREEN_NEON}"
    TERMINAL = f"{GREEN_LIGHT}"
    SUCCESS = f"{BOLD}{CYAN}"
    ERROR = f"{BOLD}{RED}"
    WARNING = f"{BOLD}{YELLOW}"
    INFO = f"{BOLD}{BLUE}"

    SYMBOLS = {
        "terminal": "⌘",
        "pointer": "▶",
        "arrow": "➤",
        "warning": "⚠",
        "loading": "⌛"
    }

# ============================================
# 🎨 INTERFACE HACKER
# ============================================
class HackerUI:
    @staticmethod
    def clear_screen():
        os.system('cls' if os.name == 'nt' else 'clear')

    @staticmethod
    def print_header(title: str, subtext: str = ""):
        HackerUI.clear_screen()
        width = 70

        print(f"\n{HackerTheme.BG_BLACK}{HackerTheme.MATRIX}{'▁'*width}{HackerTheme.RESET}")
        print(f"{HackerTheme.BG_BLACK}{HackerTheme.MATRIX}╔{'═'*(width-2)}╗{HackerTheme.RESET}")

        title_line = f"║ {HackerTheme.HIGHLIGHT}▸ {title} ◂{HackerTheme.MATRIX}"
        print(f"{HackerTheme.BG_BLACK}{HackerTheme.MATRIX}{title_line:<{width-1}}║{HackerTheme.RESET}")

        if subtext:
            sub_line = f"║ {HackerTheme.TERMINAL}{subtext}{HackerTheme.MATRIX}"
            print(f"{HackerTheme.BG_BLACK}{HackerTheme.MATRIX}{sub_line:<{width-1}}║{HackerTheme.RESET}")

        print(f"{HackerTheme.BG_BLACK}{HackerTheme.MATRIX}╚{'═'*(width-2)}╝{HackerTheme.RESET}")
        print(f"{HackerTheme.BG_BLACK}{HackerTheme.MATRIX}{'▔'*width}{HackerTheme.RESET}\n")

    @staticmethod
    def print_terminal_box(content: str, title: str = "TERMINAL"):
        lines = content.split('\n')
        max_len = max(len(line) for line in lines) if lines else 0
        pad = max(0, max_len - len(title) + 5)

        print(f"{HackerTheme.GREEN_DARK}┌─[{HackerTheme.CYAN}{title}{HackerTheme.GREEN_DARK}]─{'─'*pad}┐{HackerTheme.RESET}")
        for line in lines:
            print(f"{HackerTheme.GREEN_DARK}│ {HackerTheme.TERMINAL}{line}{' '*(max_len - len(line))} {HackerTheme.GREEN_DARK}│{HackerTheme.RESET}")
        print(f"{HackerTheme.GREEN_DARK}└{'─'*(max_len + 7)}┘{HackerTheme.RESET}")

    @staticmethod
    def print_status_line(label: str, value: str, status: str = "info"):
        colors = {
            "success": HackerTheme.SUCCESS,
            "error": HackerTheme.ERROR,
            "warning": HackerTheme.WARNING,
            "info": HackerTheme.INFO,
            "neutral": HackerTheme.TERMINAL
        }
        color = colors.get(status, HackerTheme.TERMINAL)
        print(f"{HackerTheme.GREEN_DARK}[{HackerTheme.CYAN}{HackerTheme.SYMBOLS['pointer']}{HackerTheme.GREEN_DARK}] "
              f"{HackerTheme.TERMINAL}{label}: {color}{value}{HackerTheme.RESET}")

    @staticmethod
    def print_log_entry(package: str, message: str, level: str = "INFO"):
        levels = {
            "INFO": HackerTheme.INFO,
            "WARN": HackerTheme.WARNING,
            "ERROR": HackerTheme.ERROR,
            "SUCCESS": HackerTheme.SUCCESS,
            "DEBUG": HackerTheme.PURPLE
        }
        color = levels.get(level, HackerTheme.TERMINAL)
        timestamp = datetime.now().strftime("%H:%M:%S")

        print(f"{HackerTheme.GREEN_DARK}[{HackerTheme.CYAN}{timestamp}{HackerTheme.GREEN_DARK}] "
              f"[{color}{level:<7}{HackerTheme.GREEN_DARK}] "
              f"[{HackerTheme.YELLOW}{package:<20}{HackerTheme.GREEN_DARK}] "
              f"{HackerTheme.TERMINAL}{message}{HackerTheme.RESET}")

    @staticmethod
    def print_matrix_banner():
        banner = f"""
{HackerTheme.MATRIX}╔══════════════════════════════════════════════════════════════╗
║  {HackerTheme.CYAN}░█▀▀░█░░░█▀█░█▀▀░▀█▀░█▀▀░░░█▀▀░█▀█░█▀▄░█▀▀░█▀▄  {HackerTheme.MATRIX}║
║  {HackerTheme.CYAN}░█▀▀░█░░░█▀█░▀▀█░░█░░█▀▀░░░▀▀█░█▀█░█▀▄░█▀▀░█▀▄  {HackerTheme.MATRIX}║
║  {HackerTheme.CYAN}░▀▀▀░▀▀▀░▀░▀░▀▀▀░░▀░░▀▀▀░░░▀▀▀░▀░▀░▀░▀░▀▀▀░▀░▀  {HackerTheme.MATRIX}║
║  {HackerTheme.GREEN_NEON}░█▀▀░█▀█░█▀▄░█▀▀░▀█▀░█▀▀░█▀█░█░░░█░░░█▀▀░█▀▀  {HackerTheme.MATRIX}║
║  {HackerTheme.GREEN_NEON}░▀▀█░█▀█░█░█░█▀▀░░█░░█░░░█▀█░█░░░█░░░▀▀█░█▀▀  {HackerTheme.MATRIX}║
║  {HackerTheme.GREEN_NEON}░▀▀▀░▀░▀░▀▀░░▀▀▀░░▀░░▀▀▀░▀░▀░▀▀▀░▀▀▀░▀▀▀░▀▀▀  {HackerTheme.MATRIX}║
╠══════════════════════════════════════════════════════════════╣
║  {HackerTheme.PINK}TITANIYAHU • Deeplink Edition • Access Granted  {HackerTheme.MATRIX}║
╚══════════════════════════════════════════════════════════════╝{HackerTheme.RESET}
        """
        print(banner)

    @staticmethod
    def animate_loading(text: str, duration: int = 2):
        frames = ["[▓▓▓▓▓▓▓▓▓▓]", "[█▓▓▓▓▓▓▓▓▓]", "[██▓▓▓▓▓▓▓▓]", "[███▓▓▓▓▓▓▓]",
                  "[████▓▓▓▓▓▓]", "[█████▓▓▓▓▓]", "[██████▓▓▓▓]", "[███████▓▓▓]",
                  "[████████▓▓]", "[█████████▓]", "[██████████]"]
        for i in range(duration * 10):
            frame = frames[i % len(frames)]
            print(f"\r{HackerTheme.CYAN}{frame} {HackerTheme.TERMINAL}{text}{HackerTheme.RESET}", end="")
            time.sleep(0.1)
        print()

    @staticmethod
    def print_menu(options: List[Dict]):
        print(f"\n{HackerTheme.GREEN_DARK}┌─[{HackerTheme.CYAN}MAIN MENU{HackerTheme.GREEN_DARK}]─{'─'*50}┐{HackerTheme.RESET}")
        for i, option in enumerate(options, 1):
            icon = option.get('icon', HackerTheme.SYMBOLS['pointer'])
            color = option.get('color', HackerTheme.TERMINAL)
            print(f"{HackerTheme.GREEN_DARK}│ {HackerTheme.CYAN}{i:2d}{HackerTheme.GREEN_DARK} {icon} "
                  f"{color}{option['text']}{HackerTheme.RESET}")
        print(f"{HackerTheme.GREEN_DARK}└{'─'*60}┘{HackerTheme.RESET}")

# ============================================
# 🔗 DEEPLINK CONVERTER
# ============================================
def to_roblox_deeplink(link: str) -> str:
    """
    Converte web_link em roblox:// deeplink.
    Suporta:
    - roblox://... (já pronto)
    - https://www.roblox.com/games/<placeId>/...?privateServerLinkCode=XXXX
      -> roblox://navigation/game_details?gameId=<placeId>&privateServerLinkCode=XXXX
    - https://www.roblox.com/share?code=XXXX&type=Server
      -> roblox://navigation/share_links?code=XXXX&type=Server
    """
    link = (link or "").strip()
    if not link:
        return ""

    if link.lower().startswith("roblox://"):
        return link

    u = urlparse(link)
    host = (u.netloc or "").lower()
    path = u.path or ""
    q = parse_qs(u.query or "")

    # Novo share link
    if "roblox.com" in host and path.rstrip("/") == "/share":
        code = (q.get("code", [""])[0] or "").strip()
        typ = (q.get("type", ["Server"])[0] or "Server").strip()
        if code and typ.lower() == "server":
            return f"roblox://navigation/share_links?code={code}&type=Server"

    # Antigo privateServerLinkCode (seu caso)
    pscode = (q.get("privateServerLinkCode", [""])[0] or "").strip()
    if pscode:
        m = re.search(r"/games/(\d+)", path)
        place_id = m.group(1) if m else ""
        if place_id:
            return f"roblox://navigation/game_details?gameId={place_id}&privateServerLinkCode={pscode}"
        # fallback (menos confiável)
        return f"roblox://navigation/game_details?privateServerLinkCode={pscode}"

    return ""  # não cai pro navegador

# ============================================
# 📱 ADB CLIENT (sem quebrar args)
# ============================================
class ADBClient:
    def __init__(self, serial: str = ""):
        self.serial = (serial or "").strip()

    def _base(self) -> List[str]:
        cmd = ["adb"]
        if self.serial:
            cmd += ["-s", self.serial]
        return cmd

    def run(self, args: List[str], timeout: int = 12) -> Tuple[int, str, str]:
        try:
            p = subprocess.run(self._base() + args, capture_output=True, text=True, timeout=timeout)
            return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
        except Exception as e:
            return 1, "", str(e)

    def shell_list(self, argv: List[str], timeout: int = 12) -> Tuple[int, str, str]:
        # adb shell <argv...>  (sem sh -c)
        return self.run(["shell"] + argv, timeout=timeout)

    def devices(self) -> str:
        rc, out, err = self.run(["devices"], timeout=10)
        return out or err or ""

    def has_device(self) -> bool:
        out = self.devices()
        for line in out.splitlines():
            if "\tdevice" in line:
                return True
        return False

# ============================================
# 🎮 MONITOR HACKER
# ============================================
class HackerMonitor:
    def __init__(self, config: dict):
        self.config = config
        self.adb = ADBClient(config.get("adb_serial", ""))

        self.lowcpu_count: Dict[str, int] = {}
        self.cooldown: Dict[str, float] = {}
        self.max_count = max(1, int(config["max_lowcpu_time"] // config["check_interval"]))
        self.running = True

        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, *_):
        print(f"\n\n{HackerTheme.ERROR}⚠️  INTERRUPÇÃO DETECTADA • Encerrando monitoramento...{HackerTheme.RESET}")
        self.running = False

    def get_pid(self, package: str) -> Optional[str]:
        rc, out, err = self.adb.shell_list(["pidof", package], timeout=8)
        if rc != 0 or not out:
            return None
        return out.split()[0]

    def get_cpu_usage(self, pid: str) -> float:
        """
        Lê 'top' inteiro e procura linha do PID (sem grep/pipes).
        """
        rc, out, err = self.adb.shell_list(["top", "-n", "1", "-b"], timeout=10)
        if rc != 0 or not out:
            return 0.0

        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            # Algumas versões colocam PID como primeiro token
            if line.startswith(pid + " "):
                parts = line.split()
                # pega o primeiro token que parece "12%" ou "12.3%"
                for tok in parts:
                    if tok.endswith("%"):
                        try:
                            return float(tok.replace("%", "").replace(",", "."))
                        except:
                            continue
        return 0.0

    def check_package_status(self, package: str) -> Dict:
        pid = self.get_pid(package)
        status = {
            "package": package,
            "pid": pid,
            "running": pid is not None,
            "cpu": 0.0,
            "needs_restart": False
        }

        if pid:
            cpu = self.get_cpu_usage(pid)
            status["cpu"] = cpu

            if cpu <= self.config["low_cpu_threshold"]:
                self.lowcpu_count[package] = self.lowcpu_count.get(package, 0) + 1
                if self.lowcpu_count[package] >= self.max_count:
                    status["needs_restart"] = True
            else:
                self.lowcpu_count[package] = 0

        return status

    def soft_restart(self, package: str) -> bool:
        current_time = time.time()

        if package in self.cooldown and current_time < self.cooldown[package]:
            HackerUI.print_log_entry(package, f"Cooldown: {self.cooldown[package]-current_time:.0f}s", "WARN")
            return False

        HackerUI.print_log_entry(package, "Iniciando reinício suave...", "INFO")

        try:
            # Force-stop
            self.adb.shell_list(["am", "force-stop", package], timeout=10)
            time.sleep(1.5)

            # Abre VIP via DEEPLINK
            ok = self.open_vip(package)

            self.cooldown[package] = time.time() + self.config["cooldown_time"]
            self.lowcpu_count[package] = 0

            if ok:
                pid_after = self.get_pid(package)
                HackerUI.print_log_entry(package, f"Reinício completo • PID: {pid_after or '??'}", "SUCCESS")
            else:
                HackerUI.print_log_entry(package, "Reinício pode ter falhado (sem PID)", "WARN")

            return ok

        except Exception as e:
            HackerUI.print_log_entry(package, f"Erro no reinício: {str(e)}", "ERROR")
            return False

    def open_vip(self, package: str) -> bool:
        """
        Abre servidor VIP usando deeplink.
        Nunca abre navegador.
        """
        deeplink = to_roblox_deeplink(self.config.get("web_link", ""))
        if not deeplink:
            HackerUI.print_log_entry(package, "web_link não virou deeplink. Verifique o link.", "ERROR")
            return False

        # 1) tenta com -p (força abrir no pacote Roblox)
        rc1, out1, err1 = self.adb.shell_list(
            ["am", "start", "-a", "android.intent.action.VIEW", "-d", deeplink, "-p", package],
            timeout=18
        )
        txt1 = (out1 + "\n" + err1).strip()

        # 2) fallback sem -p
        rc2, out2, err2 = self.adb.shell_list(
            ["am", "start", "-a", "android.intent.action.VIEW", "-d", deeplink],
            timeout=18
        )
        txt2 = (out2 + "\n" + err2).strip()

        if rc1 != 0 and rc2 != 0:
            HackerUI.print_log_entry(package, "DEEPLINK falhou. Debug abaixo:", "ERROR")
            HackerUI.print_terminal_box(
                f"DEEPLINK: {deeplink}\n\n[com -p]\nRC:{rc1}\n{txt1 or '(vazio)'}\n\n[sem -p]\nRC:{rc2}\n{txt2 or '(vazio)'}",
                "DEEPLINK DEBUG"
            )
            return False

        # espera PID aparecer
        wait_sec = int(self.config.get("launch_wait_sec", 14))
        end = time.time() + wait_sec
        while time.time() < end:
            if self.get_pid(package):
                return True
            time.sleep(0.4)

        return False

    def monitor(self):
        HackerUI.print_header("SISTEMA DE MONITORAMENTO", "Hacker Edition • Deeplink Edition • Iniciando...")

        deeplink = to_roblox_deeplink(self.config.get("web_link", ""))
        config_info = f"""
{HackerTheme.GREEN_DARK}┌─[{HackerTheme.CYAN}CONFIGURAÇÃO{HackerTheme.GREEN_DARK}]─{'─'*45}┐
│ {HackerTheme.TERMINAL}• CPU Limite:    {HackerTheme.CYAN}{self.config['low_cpu_threshold']}%
│ {HackerTheme.TERMINAL}• Intervalo:     {HackerTheme.CYAN}{self.config['check_interval']}s
│ {HackerTheme.TERMINAL}• Cooldown:      {HackerTheme.CYAN}{self.config['cooldown_time']}s
│ {HackerTheme.TERMINAL}• Pacotes:       {HackerTheme.CYAN}{len(self.config['packages'])}
│ {HackerTheme.TERMINAL}• Deeplink:      {HackerTheme.CYAN}{(deeplink[:48] + '...') if deeplink else 'ERRO'}
{HackerTheme.GREEN_DARK}└{'─'*60}┘{HackerTheme.RESET}
        """
        print(config_info)

        # Checa ADB
        if not self.adb.has_device():
            HackerUI.print_log_entry("ADB", "Nenhum dispositivo conectado (adb devices)", "ERROR")
            HackerUI.print_terminal_box(self.adb.devices(), "ADB DEVICES")
            input(f"\n{HackerTheme.TERMINAL}Pressione Enter...{HackerTheme.RESET}")
            return

        # Inicialização
        HackerUI.animate_loading("Inicializando pacotes", 2)
        for package in self.config["packages"]:
            self.soft_restart(package)
            time.sleep(2)

        cycle = 0
        while self.running:
            cycle += 1

            print(f"\n{HackerTheme.GREEN_DARK}{'─'*60}{HackerTheme.RESET}")
            print(f"{HackerTheme.CYAN}🛰️  CICLO {cycle:04d} • {datetime.now().strftime('%H:%M:%S')} • SCANNING...{HackerTheme.RESET}")
            print(f"{HackerTheme.GREEN_DARK}{'─'*60}{HackerTheme.RESET}\n")

            for package in self.config["packages"]:
                status = self.check_package_status(package)

                if not status["running"]:
                    HackerUI.print_log_entry(package, "PROCESSO OFFLINE", "ERROR")
                    self.soft_restart(package)

                elif status["needs_restart"]:
                    cpu_color = HackerTheme.RED if status["cpu"] < 2 else HackerTheme.YELLOW
                    HackerUI.print_log_entry(
                        package,
                        f"CPU CRÍTICA: {cpu_color}{status['cpu']:.1f}%{HackerTheme.TERMINAL} • REINICIANDO...",
                        "WARN"
                    )
                    self.soft_restart(package)

                elif status["cpu"] <= self.config["low_cpu_threshold"]:
                    count = self.lowcpu_count.get(package, 0)
                    HackerUI.print_log_entry(
                        package,
                        f"CPU BAIXA: {HackerTheme.YELLOW}{status['cpu']:.1f}%{HackerTheme.TERMINAL} [{count}/{self.max_count}]",
                        "INFO"
                    )

                else:
                    cpu_color = HackerTheme.GREEN_NEON if status["cpu"] > 20 else HackerTheme.CYAN
                    HackerUI.print_log_entry(
                        package,
                        f"STATUS: {cpu_color}{status['cpu']:.1f}%{HackerTheme.TERMINAL} • OPERACIONAL",
                        "SUCCESS"
                    )

            for i in range(self.config["check_interval"], 0, -1):
                time_str = f"⏳ {i:02d}s"
                if i <= 3:
                    time_str = f"{HackerTheme.BLINK}{HackerTheme.RED}⚠️  {i:02d}s{HackerTheme.RESET}"

                print(f"\r{HackerTheme.GREEN_DARK}[{HackerTheme.CYAN}AGUARDANDO{HackerTheme.GREEN_DARK}] "
                      f"{HackerTheme.TERMINAL}Próximo scan em {time_str}{HackerTheme.RESET}", end="")
                time.sleep(1)
            print()

# ============================================
# ⚙️ GERENCIAMENTO
# ============================================
def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                defaults = DEFAULT_CONFIG.copy()
                defaults.update(config)
                return defaults
        except Exception:
            HackerUI.print_log_entry("SYSTEM", "Falha ao carregar config, usando padrões", "ERROR")
    return DEFAULT_CONFIG.copy()

def save_config(config: dict):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def setup_wizard():
    HackerUI.print_header("CONFIGURAÇÃO DO SISTEMA (DEEPLINK)")

    config = load_config()

    print(f"\n{HackerTheme.GREEN_DARK}┌─[{HackerTheme.CYAN}CONFIGURAÇÕES{HackerTheme.GREEN_DARK}]─{'─'*50}┐{HackerTheme.RESET}")

    # Link VIP
    HackerUI.print_status_line("web_link atual", config['web_link'][:55] + ("..." if len(config['web_link']) > 55 else ""))
    if input(f"\n{HackerTheme.TERMINAL}Alterar web_link? (s/n): {HackerTheme.RESET}").lower() == 's':
        config['web_link'] = input(f"{HackerTheme.TERMINAL}Novo link: {HackerTheme.RESET}").strip()

    deeplink = to_roblox_deeplink(config.get("web_link", ""))
    HackerUI.print_status_line("DEEPLINK gerado", deeplink if deeplink else "ERRO (link não suportado)", "success" if deeplink else "error")

    # ADB serial
    HackerUI.print_status_line("ADB serial", config.get("adb_serial") or "(vazio)", "info")
    if input(f"\n{HackerTheme.TERMINAL}Definir ADB serial? (s/n): {HackerTheme.RESET}").lower() == 's':
        config["adb_serial"] = input(f"{HackerTheme.TERMINAL}Serial (ou vazio): {HackerTheme.RESET}").strip()

    # Config técnicas
    print(f"\n{HackerTheme.INFO}⚙️  CONFIGURAÇÕES TÉCNICAS:{HackerTheme.RESET}")
    print(f"{HackerTheme.TERMINAL}(Pressione Enter para manter){HackerTheme.RESET}")

    try:
        cpu_thresh = input(f"{HackerTheme.TERMINAL}Limite CPU [{config['low_cpu_threshold']}]: {HackerTheme.RESET}").strip()
        interval = input(f"{HackerTheme.TERMINAL}Intervalo [{config['check_interval']}]: {HackerTheme.RESET}").strip()
        cooldown = input(f"{HackerTheme.TERMINAL}Cooldown [{config['cooldown_time']}]: {HackerTheme.RESET}").strip()
        lowcpu_time = input(f"{HackerTheme.TERMINAL}Tempo CPU baixa (s) [{config['max_lowcpu_time']}]: {HackerTheme.RESET}").strip()
        wait_pid = input(f"{HackerTheme.TERMINAL}Esperar PID (s) [{config.get('launch_wait_sec',14)}]: {HackerTheme.RESET}").strip()

        if cpu_thresh: config['low_cpu_threshold'] = float(cpu_thresh)
        if interval: config['check_interval'] = int(interval)
        if cooldown: config['cooldown_time'] = int(cooldown)
        if lowcpu_time: config['max_lowcpu_time'] = int(lowcpu_time)
        if wait_pid: config['launch_wait_sec'] = int(wait_pid)
    except Exception:
        HackerUI.print_log_entry("CONFIG", "Valores inválidos, mantendo", "WARN")

    save_config(config)
    HackerUI.print_log_entry("SYSTEM", "Configuração salva com sucesso", "SUCCESS")
    print(f"{HackerTheme.GREEN_DARK}└{'─'*60}┘{HackerTheme.RESET}")
    return config

# ============================================
# 📱 MENU PRINCIPAL
# ============================================
def main_menu():
    while True:
        HackerUI.clear_screen()
        HackerUI.print_matrix_banner()
        config = load_config()

        deeplink = to_roblox_deeplink(config.get("web_link", ""))
        status_box = f"""
{HackerTheme.GREEN_DARK}┌─[{HackerTheme.CYAN}STATUS DO SISTEMA{HackerTheme.GREEN_DARK}]─{'─'*40}┐
│ {HackerTheme.TERMINAL}• Pacotes monitorados: {HackerTheme.CYAN}{len(config.get('packages', []))}
│ {HackerTheme.TERMINAL}• CPU Limite:         {HackerTheme.CYAN}{config['low_cpu_threshold']}%
│ {HackerTheme.TERMINAL}• Intervalo:          {HackerTheme.CYAN}{config['check_interval']}s
│ {HackerTheme.TERMINAL}• Deeplink OK:        {HackerTheme.CYAN}{'SIM' if deeplink else 'NÃO'}
│ {HackerTheme.TERMINAL}• Última atualização: {HackerTheme.CYAN}{datetime.now().strftime('%H:%M:%S')}
{HackerTheme.GREEN_DARK}└{'─'*60}┘{HackerTheme.RESET}
        """
        print(status_box)

        menu_options = [
            {"icon": "🖥️", "text": "Iniciar Monitoramento", "color": HackerTheme.CYAN},
            {"icon": "🔧", "text": "Configurar Sistema", "color": HackerTheme.GREEN_NEON},
            {"icon": "🔍", "text": "Detectar Pacotes (Roblox)", "color": HackerTheme.BLUE},
            {"icon": "📡", "text": "Testar Conexão ADB", "color": HackerTheme.ORANGE},
            {"icon": "🧪", "text": "Testar Deeplink Agora", "color": HackerTheme.PINK},
            {"icon": "⏹️", "text": "Sair do Sistema", "color": HackerTheme.RED}
        ]
        HackerUI.print_menu(menu_options)

        try:
            choice = input(f"\n{HackerTheme.CYAN}{HackerTheme.SYMBOLS['terminal']} {HackerTheme.BOLD}ESCOLHA (1-6): {HackerTheme.RESET}").strip()

            if choice == "1":
                if not config.get("packages"):
                    HackerUI.print_log_entry("SYSTEM", "Nenhum pacote configurado!", "ERROR")
                    input(f"\n{HackerTheme.TERMINAL}Pressione Enter...{HackerTheme.RESET}")
                    continue
                monitor = HackerMonitor(config)
                monitor.monitor()

            elif choice == "2":
                setup_wizard()
                input(f"\n{HackerTheme.TERMINAL}Pressione Enter...{HackerTheme.RESET}")

            elif choice == "3":
                HackerUI.print_header("DETECÇÃO DE PACOTES")
                adb = ADBClient(config.get("adb_serial",""))
                if not adb.has_device():
                    HackerUI.print_log_entry("ADB", "Sem device (adb devices).", "ERROR")
                    HackerUI.print_terminal_box(adb.devices(), "ADB DEVICES")
                    input(f"\n{HackerTheme.TERMINAL}Pressione Enter...{HackerTheme.RESET}")
                    continue

                rc, out, err = adb.shell_list(["pm", "list", "packages", "-3"], timeout=18)
                if rc != 0 or not out:
                    HackerUI.print_log_entry("ADB", "Falha ao listar pacotes.", "ERROR")
                    HackerUI.print_terminal_box(err or "(sem erro)", "ADB ERROR")
                    input(f"\n{HackerTheme.TERMINAL}Pressione Enter...{HackerTheme.RESET}")
                    continue

                pkgs = []
                for line in out.splitlines():
                    line = line.strip()
                    if line.startswith("package:"):
                        pkg = line.replace("package:", "").strip()
                        if "roblox" in pkg.lower():
                            pkgs.append(pkg)

                if pkgs:
                    config["packages"] = sorted(set(pkgs))
                    save_config(config)
                    HackerUI.print_terminal_box("\n".join(config["packages"]), "PACOTES DETECTADOS")
                    HackerUI.print_log_entry("SYSTEM", f"{len(config['packages'])} pacotes salvos", "SUCCESS")
                else:
                    HackerUI.print_log_entry("DETECT", "Nenhum pacote Roblox encontrado", "ERROR")

                input(f"\n{HackerTheme.TERMINAL}Pressione Enter...{HackerTheme.RESET}")

            elif choice == "4":
                HackerUI.print_header("TESTE DE CONEXÃO ADB")
                adb = ADBClient(config.get("adb_serial",""))
                HackerUI.animate_loading("Testando conexão ADB", 1)
                devices = adb.devices()
                if adb.has_device():
                    HackerUI.print_log_entry("ADB", "Conexão estabelecida", "SUCCESS")
                    HackerUI.print_terminal_box(devices, "DISPOSITIVOS")
                else:
                    HackerUI.print_log_entry("ADB", "Nenhum dispositivo conectado", "ERROR")
                    HackerUI.print_terminal_box(devices or "(vazio)", "ADB DEVICES")
                input(f"\n{HackerTheme.TERMINAL}Pressione Enter...{HackerTheme.RESET}")

            elif choice == "5":
                HackerUI.print_header("TESTE DE DEEPLINK")
                deeplink = to_roblox_deeplink(config.get("web_link",""))
                if not deeplink:
                    HackerUI.print_log_entry("DEEPLINK", "Falha ao gerar deeplink. Confira web_link.", "ERROR")
                    input(f"\n{HackerTheme.TERMINAL}Pressione Enter...{HackerTheme.RESET}")
                    continue

                adb = ADBClient(config.get("adb_serial",""))
                if not adb.has_device():
                    HackerUI.print_log_entry("ADB", "Sem device (adb devices).", "ERROR")
                    HackerUI.print_terminal_box(adb.devices(), "ADB DEVICES")
                    input(f"\n{HackerTheme.TERMINAL}Pressione Enter...{HackerTheme.RESET}")
                    continue

                pkg = (config.get("packages") or ["com.roblox.client"])[0]
                HackerUI.print_log_entry("DEEPLINK", f"Tentando abrir em: {pkg}", "INFO")
                rc, out, err = adb.shell_list(["am", "start", "-a", "android.intent.action.VIEW", "-d", deeplink, "-p", pkg], timeout=18)
                HackerUI.print_terminal_box(f"DEEPLINK:\n{deeplink}\n\nRC:{rc}\n{(out + '\\n' + err).strip() or '(vazio)'}", "RESULTADO")
                input(f"\n{HackerTheme.TERMINAL}Pressione Enter...{HackerTheme.RESET}")

            elif choice == "6":
                print(f"\n{HackerTheme.CYAN}{'─'*60}{HackerTheme.RESET}")
                print(f"{HackerTheme.GREEN_NEON}🚀 Sistema encerrado. Até a próxima! 🚀{HackerTheme.RESET}")
                print(f"{HackerTheme.CYAN}{'─'*60}{HackerTheme.RESET}")
                sys.exit(0)

            else:
                HackerUI.print_log_entry("INPUT", "Opção inválida", "ERROR")
                time.sleep(1)

        except KeyboardInterrupt:
            print(f"\n{HackerTheme.ERROR}Interrupção detectada. Voltando ao menu...{HackerTheme.RESET}")
            time.sleep(1)
        except Exception as e:
            HackerUI.print_log_entry("ERROR", f"Erro: {str(e)}", "ERROR")
            time.sleep(2)

# ============================================
# 🚀 INICIALIZAÇÃO
# ============================================
def main():
    try:
        HackerUI.clear_screen()
        HackerUI.print_matrix_banner()
        time.sleep(0.6)

        print(f"\n{HackerTheme.GREEN_DARK}┌─[{HackerTheme.CYAN}VERIFICAÇÃO INICIAL{HackerTheme.GREEN_DARK}]─{'─'*38}┐{HackerTheme.RESET}")

        try:
            result = subprocess.run(["adb", "--version"], capture_output=True, text=True)
            HackerUI.print_status_line("ADB", "OK" if result.returncode == 0 else "Não encontrado", "success" if result.returncode == 0 else "error")
        except Exception:
            HackerUI.print_status_line("ADB", "Erro na verificação", "error")

        HackerUI.print_status_line("Python", f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}", "info")
        if "termux" in os.environ.get("PREFIX", ""):
            HackerUI.print_status_line("Ambiente", "Termux", "success")
        else:
            HackerUI.print_status_line("Ambiente", "Sistema padrão", "warning")

        print(f"{HackerTheme.GREEN_DARK}└{'─'*60}┘{HackerTheme.RESET}")
        time.sleep(0.6)

        main_menu()

    except KeyboardInterrupt:
        print(f"\n\n{HackerTheme.ERROR}🔴 SISTEMA INTERROMPIDO PELO USUÁRIO{HackerTheme.RESET}")
    except Exception as e:
        print(f"\n{HackerTheme.ERROR}💥 ERRO CRÍTICO: {str(e)}{HackerTheme.RESET}")
        print(f"{HackerTheme.TERMINAL}Relate este erro para manutenção.{HackerTheme.RESET}")

if __name__ == "__main__":
    main()
