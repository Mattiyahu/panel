#!/usr/bin/env python3
import subprocess
import time
import json
import os
import statistics

STATE_FILE = "jarves_state.json"

CHECK_INTERVAL = 10      # segundos
LEARN_TIME = 120         # segundos (learning após Roblox rodar)
FAIL_LIMIT = 6           # leituras ruins consecutivas
COOLDOWN = 30            # cooldown entre reinícios

VIP_LINK = ""            # opcional (se vazio, só abre o app)

# =============================
# 🔧 ADB HELPERS
# =============================
def adb(cmd):
    try:
        return subprocess.check_output(
            ["adb"] + cmd.split(),
            stderr=subprocess.DEVNULL,
            text=True
        ).strip()
    except:
        return ""

def get_packages():
    out = adb("shell pm list packages | grep roblox")
    return [l.replace("package:", "").strip() for l in out.splitlines() if l]

def get_pid(pkg):
    return adb(f"shell pidof {pkg}")

def get_cpu(pid):
    try:
        out = adb(f"shell top -n 1 -b | grep '^{pid}'")
        return float(out.split()[8].replace('%', '').replace(',', '.'))
    except:
        return 0.0

def get_ram(pid):
    try:
        out = adb(f"shell dumpsys meminfo {pid} | grep TOTAL")
        kb = int(out.split()[1])
        return kb / 1024
    except:
        return 0.0

def start(pkg):
    if VIP_LINK:
        adb(
            f'shell am start -n {pkg}/com.roblox.client.ActivityProtocolLaunch '
            f'-a android.intent.action.VIEW -d "{VIP_LINK}"'
        )
    else:
        adb(f"shell monkey -p {pkg} 1")

def restart(pkg):
    adb(f"shell am force-stop {pkg}")
    time.sleep(2)
    start(pkg)

# =============================
# 💾 STATE
# =============================
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

# =============================
# 🚀 MAIN
# =============================
def main():
    packages = get_packages()
    if not packages:
        print("No Roblox packages found.")
        return

    print(f"JARVES ONLINE — packages: {len(packages)}")

    state = load_state()

    # Inicializa estado
    for pkg in packages:
        state.setdefault(pkg, {
            "learned": False,
            "learning_start": None,
            "cpu_samples": [],
            "ram_samples": [],
            "cpu_min": None,
            "ram_min": None,
            "fails": 0,
            "last_restart": 0
        })

    save_state(state)

    # Start inicial
    print("Starting Roblox...")
    for pkg in packages:
        start(pkg)
        time.sleep(3)

    print("Monitoring...")

    # =============================
    # LOOP DE MONITORAMENTO
    # =============================
    while True:
        for pkg in packages:
            data = state[pkg]
            pid = get_pid(pkg)

            # Roblox caiu
            if not pid:
                print(f"[OFFLINE] {pkg} restarting")
                restart(pkg)
                data["learning_start"] = None
                data["learned"] = False
                data["cpu_samples"].clear()
                data["ram_samples"].clear()
                continue

            cpu = get_cpu(pid)
            ram = get_ram(pid)

            # =============================
            # LEARNING PHASE (SÓ AGORA)
            # =============================
            if not data["learned"]:
                if data["learning_start"] is None:
                    print(f"[LEARN] {pkg} started")
                    data["learning_start"] = time.time()

                if cpu > 0 and ram > 0:
                    data["cpu_samples"].append(cpu)
                    data["ram_samples"].append(ram)

                if time.time() - data["learning_start"] >= LEARN_TIME:
                    if data["cpu_samples"] and data["ram_samples"]:
                        cpu_avg = statistics.mean(data["cpu_samples"])
                        ram_avg = statistics.mean(data["ram_samples"])

                        data["cpu_min"] = round(cpu_avg * 0.35, 2)
                        data["ram_min"] = round(ram_avg * 0.45, 2)

                        print(
                            f"[BASELINE] {pkg} "
                            f"CPU avg {cpu_avg:.2f}% → min {data['cpu_min']}% | "
                            f"RAM avg {ram_avg:.0f}MB → min {data['ram_min']}MB"
                        )

                        data["learned"] = True
                        data["cpu_samples"].clear()
                        data["ram_samples"].clear()
                    continue

                print(f"[LEARNING] {pkg} cpu {cpu:.1f}% ram {ram:.0f}MB")
                continue

            # =============================
            # MONITOR REAL
            # =============================
            bad = (
                cpu < data["cpu_min"] or
                ram < data["ram_min"]
            )

            if bad:
                data["fails"] += 1
                print(
                    f"[WARN] {pkg} low cpu/ram "
                    f"{cpu:.1f}% | {ram:.0f}MB "
                    f"[{data['fails']}/{FAIL_LIMIT}]"
                )
            else:
                data["fails"] = 0
                print(
                    f"[OK] {pkg} "
                    f"{cpu:.1f}% | {ram:.0f}MB"
                )

            if (
                data["fails"] >= FAIL_LIMIT and
                time.time() - data["last_restart"] > COOLDOWN
            ):
                print(f"[RESTART] {pkg}")
                restart(pkg)
                data["fails"] = 0
                data["last_restart"] = time.time()
                data["learned"] = False
                data["learning_start"] = None
                data["cpu_samples"].clear()
                data["ram_samples"].clear()

        save_state(state)
        time.sleep(CHECK_INTERVAL)

# =============================
# ENTRY
# =============================
if __name__ == "__main__":
    main()
