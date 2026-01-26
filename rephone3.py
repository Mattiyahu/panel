#!/usr/bin/env python3
import subprocess, time, re, datetime, os, json

CFG_FILE="config.json"

DEFAULT = {
    "vip_link": "",
    "cycle_delay": 2.0,       # tempo entre clones
    "join_wait": 12.0,        # quanto espera após mandar join
    "max_join_tries": 3,      # tentativas de entrar sem fechar
    "force_restart_after": 2  # se falhar X joins, aí força stop
}

HOME_KEYS = ["home", "discover", "avatar", "friends", "search", "pesquisar", "recommended", "recomendados", "robux"]
ERROR_KEYS = ["disconnected","reconnect","connection lost","lost connection","desconectado","reconectar","retry","tentar novamente"]

def log(msg):
    t=datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{t}] {msg}", flush=True)

def sh(cmd, t=12):
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL, timeout=t).decode(errors="ignore").strip()
    except:
        return ""

def adb(cmd, t=12):
    return sh(f"adb shell {cmd}", t)

def load_cfg():
    d=DEFAULT.copy()
    if os.path.exists(CFG_FILE):
        try:
            d.update(json.load(open(CFG_FILE,"r",encoding="utf-8")))
        except:
            pass
    return d

def save_cfg(d):
    json.dump(d, open(CFG_FILE,"w",encoding="utf-8"), indent=2, ensure_ascii=False)

CFG=load_cfg()

def get_packages():
    out = adb("pm list packages", 12)
    pkgs=[]
    for l in out.splitlines():
        if l.startswith("package:"):
            p=l.replace("package:","").strip()
            if "roblox" in p.lower():
                pkgs.append(p)
    return sorted(set(pkgs))

def resolve_activity(pkg):
    res = adb(f"cmd package resolve-activity --brief {pkg}", 10)
    lines=[x.strip() for x in res.splitlines() if x.strip()]
    return lines[-1] if lines else ""

def focus_pkg(pkg):
    act = resolve_activity(pkg)
    if "/" in act:
        adb(f"am start -n {act}", 15)
    else:
        adb(f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1", 15)
    time.sleep(0.8)

def dump_ui():
    adb("uiautomator dump /sdcard/ui.xml >/dev/null 2>&1", 12)
    time.sleep(0.2)
    return adb("cat /sdcard/ui.xml 2>/dev/null", 10)

def detect_home(xml):
    x=(xml or "").lower()
    count=sum(1 for k in HOME_KEYS if k in x)
    return count >= 2

def detect_error(xml):
    x=(xml or "").lower()
    return any(k in x for k in ERROR_KEYS)

def join_vip(pkg, vip):
    # entrar no jogo sem fechar o app
    # tenta mandar pro pacote certo
    adb(f"am start -a android.intent.action.VIEW -d '{vip}' {pkg}", 15)

def force_restart(pkg, vip):
    adb(f"am force-stop {pkg}", 10)
    time.sleep(1.5)
    adb(f"am start -a android.intent.action.VIEW -d '{vip}'", 15)

def pid(pkg):
    return adb(f"pidof {pkg}", 6)

def main():
    global CFG
    if not CFG["vip_link"]:
        CFG["vip_link"]=input("Cole o VIP link: ").strip()
        save_cfg(CFG)

    vip=CFG["vip_link"]
    pkgs=get_packages()
    if not pkgs:
        log("❌ Nenhum pacote Roblox encontrado.")
        return

    log("✅ Pacotes detectados:")
    for p in pkgs:
        log(f"  - {p}")

    join_fail = {p:0 for p in pkgs}

    log("🚀 Round-robin iniciado (1 por 1). CTRL+C para sair.\n")

    while True:
        for p in pkgs:
            name=p.split(".")[-1].upper()

            log(f"🟦 FOCANDO {name}...")
            focus_pkg(p)

            if not pid(p):
                log(f"❌ {name} está fechado -> abrindo VIP")
                force_restart(p, vip)
                join_fail[p]=0
                time.sleep(CFG["cycle_delay"])
                continue

            log(f"🔎 LENDO TELA {name} (uiautomator)...")
            xml=dump_ui()

            if not xml or len(xml) < 80:
                # UI falhou (normal no DeltaClone)
                log(f"⚠️ {name} UI vazia -> tentando JOIN VIP mesmo assim")
                join_vip(p, vip)
                time.sleep(CFG["join_wait"])
                time.sleep(CFG["cycle_delay"])
                continue

            if detect_error(xml):
                log(f"⚠️ {name} erro (disconnect/reconnect) -> FORCE RESTART")
                force_restart(p, vip)
                join_fail[p]=0
                time.sleep(CFG["cycle_delay"])
                continue

            if detect_home(xml):
                log(f"🏠 {name} HOME detectada -> tentando entrar SEM fechar (JOIN VIP)")
                join_vip(p, vip)
                time.sleep(CFG["join_wait"])

                # re-checa
                xml2=dump_ui()
                if xml2 and detect_home(xml2):
                    join_fail[p]+=1
                    log(f"❌ {name} ainda HOME (fail {join_fail[p]}/{CFG['max_join_tries']})")
                    if join_fail[p] >= CFG["max_join_tries"]:
                        log(f"💥 {name} falhou muito -> FORCE RESTART")
                        force_restart(p, vip)
                        join_fail[p]=0
                else:
                    log(f"✅ {name} parece que saiu da HOME (ok)")
                    join_fail[p]=0

            else:
                log(f"✅ {name} OK (não está em HOME)")

            time.sleep(CFG["cycle_delay"])

if __name__=="__main__":
    main()
