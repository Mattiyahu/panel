#!/usr/bin/env python3
import subprocess
import time
import json
import os
import statistics

STATE_FILE = "jarves_state.json"

CHECK_INTERVAL = 10          # segundos
LEARN_TIME = 120             # segundos (fase de aprendizado)
FAIL_LIMIT = 6               # leituras ruins seguidas
COOLDOWN = 30                # segundos entre restarts

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

def restart(pkg):
    adb(f"shell am force-stop {pkg}")
    time.sleep(2)
    adb(
        f'shell am start -n {pkg}/com.roblox.client.ActivityProtocolLaunch '
        f'-a android.intent.action.VIEW'
    )

# =============================
# 🧠 LEARNING CORE
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

    state = load_state()

    print("JARVES — Learning system started")
    print(f"Packages: {len(packages)}")
    print("Learning phase...")

    start_time = time.time()

    # Inicializar estruturas
    for p in packages:
        state.setdefault(p, {
            "cpu_samples": [],
            "ram_samples": [],
            "cpu_min": None,
            "ram_min": None,
            "fails": 0,
            "last_restart": 0
        })

    # =============================
    # FASE DE APRENDIZADO
    # =============================
    while time.time() - start_time < LEARN_TIME:
        for pkg in packages:
            pid = get_pid(pkg)
            if not pid:
                continue

            cpu = get_cpu(pid)
            ram = get_ram(pid)

            if cpu > 0 and ram > 0:
                state[pkg]["cpu_samples"].append(cpu)
                state[pkg]["ram_samples"].append(ram)

        time.sleep(CHECK_INTERVAL)

    # Criar baseline
    for pkg, data in state.items():
        if data["cpu_samples"] and data["ram_samples"]:
            cpu_avg = statistics.mean(data["cpu_samples"])
            ram_avg = statistics.mean(data["ram_samples"])

            data["cpu_min"] = round(cpu_avg * 0.35, 2)
            data["ram_min"] = round(ram_avg * 0.45, 2)

            print(f"{pkg}")
            print(f"  CPU avg {cpu_avg:.2f}% → min {data['cpu_min']}%")
            print(f"  RAM avg {ram_avg:.0f}MB → min {data['ram_min']}MB")

            data["cpu_samples"].clear()
            data["ram_samples"].clear()

    save_state(state)
    print("Learning complete. Monitoring...")

    # =============================
    # MONITORAMENTO CONTÍNUO
    # =============================
    while True:
        for pkg, data in state.items():
            pid = get_pid(pkg)
            if not pid:
                continue

            cpu = get_cpu(pid)
            ram = get_ram(pid)

            bad = (
                cpu < data["cpu_min"] or
                ram < data["ram_min"]
            )

            if bad:
                data["fails"] += 1
                print(f"[WARN] {pkg} low CPU/RAM ({cpu:.1f}% | {ram:.0f}MB) [{data['fails']}]")
            else:
                data["fails"] = 0

            if (
                data["fails"] >= FAIL_LIMIT and
                time.time() - data["last_restart"] > COOLDOWN
            ):
                print(f"[RESTART] {pkg}")
                restart(pkg)
                data["fails"] = 0
                data["last_restart"] = time.time()

        save_state(state)
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
