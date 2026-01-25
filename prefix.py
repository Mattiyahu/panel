import time
import subprocess
from datetime import datetime

# ====== CONFIG (somente 01/02/03) ======
PACKAGES = [
    "com.roblox.clienb",
    "com.roblox.cliend",
    "com.roblox.cliene",
]

PROTO_ACTIVITY = "com.roblox.client.ActivityProtocolLaunch"

CHECK_INTERVAL = 15
LOW_CPU_THRESHOLD = 0.3
MAX_LOWCPU_TIME = 90
COOLDOWN_TIME = 120


# ===================== UTIL =====================
def adb(args: str) -> str:
    """Executa um comando adb e retorna saída limpa."""
    try:
        out = subprocess.check_output(
            f"adb {args}",
            shell=True,
            stderr=subprocess.DEVNULL
        )
        return out.decode(errors="ignore").replace("\r", "").strip()
    except subprocess.CalledProcessError:
        return ""


def now():
    return datetime.now().strftime("%H:%M:%S")


def msg(text: str):
    print(f"[{now()}] {text}")


def get_pid(pkg: str) -> str:
    return adb(f"shell pidof {pkg}")


def get_cpu_by_pid(pid: str) -> float | None:
    """
    Lê %CPU pelo PID usando `top -n 1` e awk-like parsing.
    No seu Android, %CPU estava na 9ª coluna (index 8).
    """
    top_out = adb("shell top -n 1")
    if not top_out:
        return None

    for line in top_out.splitlines():
        parts = line.split()
        if len(parts) >= 10 and parts[0] == pid:
            cpu_str = parts[8].replace("%", "").replace(",", ".")
            try:
                return float(cpu_str)
            except:
                return None
    return None


def open_vip(pkg: str, vip_link: str):
    adb(
        f'shell am start -n {pkg}/{PROTO_ACTIVITY} '
        f'-a android.intent.action.VIEW -d "{vip_link}"'
    )
    time.sleep(6)


def force_stop(pkg: str):
    adb(f"shell am force-stop {pkg}")
    time.sleep(2)


def validate_vip_link(link: str) -> bool:
    link = link.strip()
    return ("roblox.com/games/" in link) and ("privateServerLinkCode=" in link)


# ===================== CORE =====================
def reconnect_pkg(pkg: str, vip_link: str, cooldown: dict):
    msg(f"🔄 Reiniciando sessão: {pkg}")
    force_stop(pkg)
    msg("🌐 Abrindo VIP...")
    open_vip(pkg, vip_link)
    cooldown[pkg] = int(time.time()) + COOLDOWN_TIME


def main():
    print("\n=== AutoRejoin (Python) ===")
    print("Compatível somente com clones 01/02/03")
    print("Cole o link do seu Servidor VIP:\n")

    vip_link = input("VIP Link: ").strip()

    if not validate_vip_link(vip_link):
        print("\n❌ Link inválido. Cole o link VIP completo do Roblox.")
        return

    msg("✅ Link configurado.")
    msg("🟢 Iniciando clones...")

    lowcpu_count = {pkg: 0 for pkg in PACKAGES}
    cooldown = {pkg: 0 for pkg in PACKAGES}

    max_count = MAX_LOWCPU_TIME // CHECK_INTERVAL

    # Abre todos uma vez
    for pkg in PACKAGES:
        reconnect_pkg(pkg, vip_link, cooldown)

    msg("✅ Monitoramento ativo.\n")

    while True:
        now_ts = int(time.time())

        for pkg in PACKAGES:
            # cooldown
            if cooldown.get(pkg, 0) > now_ts:
                msg(f"⏳ Aguardando estabilidade: {pkg}")
                continue

            pid = get_pid(pkg)

            # caiu/fechou
            if not pid:
                msg(f"⚠️ Sessão indisponível detectada: {pkg}")
                lowcpu_count[pkg] = 0
                reconnect_pkg(pkg, vip_link, cooldown)
                continue

            # CPU check (interno, sem expor)
            cpu = get_cpu_by_pid(pid)

            if cpu is None:
                msg(f"⚠️ Sem resposta momentânea: {pkg}")
                continue

            if cpu <= LOW_CPU_THRESHOLD:
                lowcpu_count[pkg] += 1
                msg(f"🟡 Verificando sessão: {pkg}")

                if lowcpu_count[pkg] >= max_count:
                    msg(f"⚠️ Reconexão preventiva: {pkg}")
                    lowcpu_count[pkg] = 0
                    reconnect_pkg(pkg, vip_link, cooldown)
            else:
                lowcpu_count[pkg] = 0
                msg(f"✅ OK: {pkg}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
