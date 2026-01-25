import os
import time
import subprocess
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)

# ====== CONFIG FIXA (clones 01/02/03) ======
PACKAGES = [
    ("01", "com.roblox.clienb"),
    ("02", "com.roblox.cliend"),
    ("03", "com.roblox.cliene"),
]

PROTO_ACTIVITY = "com.roblox.client.ActivityProtocolLaunch"

CHECK_INTERVAL = 10

CPU_THRESHOLD = 0.3
IDLE_OPEN_AGAIN_TIME = 30
RESTART_IDLE_TIME = 90
COOLDOWN_TIME = 120


# =================== UTIL ===================
def adb(cmd: str) -> str:
    try:
        out = subprocess.check_output(f"adb {cmd}", shell=True, stderr=subprocess.DEVNULL)
        return out.decode(errors="ignore").replace("\r", "").strip()
    except subprocess.CalledProcessError:
        return ""


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def now_str():
    return datetime.now().strftime("%H:%M:%S")


def hr():
    print(Fore.WHITE + "─" * 78)


def badge(text, color):
    return color + Style.BRIGHT + f" {text} " + Style.RESET_ALL


def logo():
    print(Fore.MAGENTA + Style.BRIGHT + r"""
 ██████╗ ███████╗     ██╗ ██████╗ ██╗███╗   ██╗████████╗ ██████╗  ██████╗ ██╗         ██╗   ██╗██████╗ 
 ██╔══██╗██╔════╝     ██║██╔═══██╗██║████╗  ██║╚══██╔══╝██╔═══██╗██╔═══██╗██║         ██║   ██║╚════██╗
 ██████╔╝█████╗       ██║██║   ██║██║██╔██╗ ██║   ██║   ██║   ██║██║   ██║██║         ██║   ██║ █████╔╝
 ██╔══██╗██╔══╝  ██   ██║██║   ██║██║██║╚██╗██║   ██║   ██║   ██║██║   ██║██║         ╚██╗ ██╔╝██╔═══╝ 
 ██║  ██║███████╗╚█████╔╝╚██████╔╝██║██║ ╚████║   ██║   ╚██████╔╝╚██████╔╝███████╗     ╚████╔╝ ███████╗
 ╚═╝  ╚═╝╚══════╝ ╚════╝  ╚═════╝ ╚═╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝  ╚═════╝ ╚══════╝      ╚═══╝  ╚══════╝
""" + Style.RESET_ALL)

    print(Fore.CYAN + Style.BRIGHT + "                  AutoRejoin Tool Panel • by MSA")
    print(Fore.YELLOW + "          Compatível somente com clones 01 / 02 / 03\n")


def get_pid(pkg: str) -> str:
    return adb(f"shell pidof {pkg}")


def force_stop(pkg: str):
    adb(f"shell am force-stop {pkg}")


def open_vip(pkg: str, vip_link: str):
    adb(
        f'shell am start -n {pkg}/{PROTO_ACTIVITY} '
        f'-a android.intent.action.VIEW -d "{vip_link}"'
    )


def get_cpu_percent(pkg: str) -> float | None:
    pid = get_pid(pkg)
    if not pid:
        return None

    top_out = adb("shell top -n 1")
    if not top_out:
        return None

    for line in top_out.splitlines():
        parts = line.split()
        # precisa ter pelo menos: PID ... S CPU MEM ...
        if len(parts) >= 10 and parts[0] == pid:
            cpu = parts[8].replace("%", "").replace(",", ".")
            try:
                return float(cpu)
            except:
                return None

    return None


def ask_vip_link() -> str:
    clear()
    logo()
    hr()
    print(Fore.WHITE + Style.BRIGHT + " Cole o link do seu Servidor VIP do Roblox:")
    print(Fore.WHITE + " Exemplo:")
    print(Fore.BLUE + " https://www.roblox.com/games/PLACEID/NOME?privateServerLinkCode=XXXX")
    hr()
    vip = input(Fore.GREEN + Style.BRIGHT + "VIP Link: " + Style.RESET_ALL).strip()

    # validação simples
    if "privateServerLinkCode=" not in vip or "roblox.com/games/" not in vip:
        print(Fore.RED + Style.BRIGHT + "\nLink inválido ou incompleto.")
        print(Fore.YELLOW + "Cole o link VIP correto e tente de novo.")
        time.sleep(2)
        return ask_vip_link()

    return vip


def main():
    vip_link = ask_vip_link()

    idle_seconds = {pkg: 0 for _, pkg in PACKAGES}
    cooldown_until = {pkg: 0 for _, pkg in PACKAGES}
    restarts = {pkg: 0 for _, pkg in PACKAGES}
    last_event = {pkg: "-" for _, pkg in PACKAGES}

    # Inicializa: abre todos
    clear()
    logo()
    print(Fore.WHITE + "Iniciando clones 01/02/03 no VIP...\n")
    for clone_id, pkg in PACKAGES:
        force_stop(pkg)
        time.sleep(1)
        open_vip(pkg, vip_link)
        time.sleep(4)
        restarts[pkg] += 1
        cooldown_until[pkg] = time.time() + COOLDOWN_TIME
        last_event[pkg] = "start vip"

    while True:
        clear()
        logo()

        print(Fore.WHITE + Style.BRIGHT + f"VIP: {vip_link}")
        print(Fore.WHITE + f"Atualizado: {now_str()} | Intervalo: {CHECK_INTERVAL}s")
        hr()

        print(Fore.WHITE + Style.BRIGHT + " CLONE  PACKAGE               STATUS        RESTARTS   INFO")
        hr()

        now = time.time()

        for clone_id, pkg in PACKAGES:
            pid = get_pid(pkg)

            # Cooldown
            if now < cooldown_until[pkg]:
                remaining = int(cooldown_until[pkg] - now)
                status = badge("COOLDOWN", Fore.BLUE)
                info = f"aguarde {remaining}s"
                print(f"  {clone_id}    {pkg:<20} {status:<12}  {restarts[pkg]:<8}  {info}")
                continue

            # Down
            if not pid:
                status = badge("DOWN", Fore.RED)
                info = "reabrindo VIP"
                print(f"  {clone_id}    {pkg:<20} {status:<12}  {restarts[pkg]:<8}  {info}")

                force_stop(pkg)
                time.sleep(2)
                open_vip(pkg, vip_link)
                time.sleep(6)

                restarts[pkg] += 1
                idle_seconds[pkg] = 0
                cooldown_until[pkg] = time.time() + COOLDOWN_TIME
                last_event[pkg] = "down -> vip"
                continue

            # CPU check (sem mostrar CPU)
            cpu = get_cpu_percent(pkg)

            if cpu is None:
                status = badge("RUNNING", Fore.WHITE)
                info = "sem leitura"
                print(f"  {clone_id}    {pkg:<20} {status:<12}  {restarts[pkg]:<8}  {info}")
                continue

            # IN GAME (ativo)
            if cpu > CPU_THRESHOLD:
                idle_seconds[pkg] = 0
                status = badge("IN GAME", Fore.GREEN)
                info = "ok"
                print(f"  {clone_id}    {pkg:<20} {status:<12}  {restarts[pkg]:<8}  {info}")
                continue

            # IDLE
            idle_seconds[pkg] += CHECK_INTERVAL

            # tenta abrir VIP de novo sem fechar
            if IDLE_OPEN_AGAIN_TIME <= idle_seconds[pkg] < RESTART_IDLE_TIME:
                status = badge("IDLE", Fore.YELLOW)
                info = f"tentando VIP ({idle_seconds[pkg]}s)"
                print(f"  {clone_id}    {pkg:<20} {status:<12}  {restarts[pkg]:<8}  {info}")

                open_vip(pkg, vip_link)
                time.sleep(3)
                continue

            # reinicia se travado
            if idle_seconds[pkg] >= RESTART_IDLE_TIME:
                status = badge("RESTART", Fore.MAGENTA)
                info = f"parado {idle_seconds[pkg]}s"
                print(f"  {clone_id}    {pkg:<20} {status:<12}  {restarts[pkg]:<8}  {info}")

                force_stop(pkg)
                time.sleep(2)
                open_vip(pkg, vip_link)
                time.sleep(6)

                restarts[pkg] += 1
                idle_seconds[pkg] = 0
                cooldown_until[pkg] = time.time() + COOLDOWN_TIME
                last_event[pkg] = "idle -> restart"
                continue

            # ainda contando idle
            status = badge("IDLE", Fore.YELLOW)
            info = f"parado {idle_seconds[pkg]}s"
            print(f"  {clone_id}    {pkg:<20} {status:<12}  {restarts[pkg]:<8}  {info}")

        hr()
        print(Fore.WHITE + f"Dica: se reiniciar demais, chama dm.\n")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
