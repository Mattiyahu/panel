#!/usr/bin/env python3
import subprocess, time, re, json, os, datetime
import requests
from rich.live import Live
from rich.table import Table
from rich.console import Console

C = Console()
CFG_FILE="config.json"
CHECK=3
COOLDOWN=120
CPU_SUS=4.0
SUS_LIMIT=6      # 6*3s=18s
FOCUS_DELAY=0.7

def sh(cmd, t=10):
    try: return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL, timeout=t).decode(errors="ignore").strip()
    except: return ""

def adb(cmd, t=10): return sh(f"adb shell {cmd}", t)

def cfg_load():
    d={"vip":"", "wh":"", "close_browser":True, "browsers":["com.android.chrome","com.brave.browser","com.microsoft.emmx"]}
    if os.path.exists(CFG_FILE):
        try: d.update(json.load(open(CFG_FILE,"r",encoding="utf-8")))
        except: pass
    return d

def cfg_save(d): json.dump(d, open(CFG_FILE,"w",encoding="utf-8"), indent=2, ensure_ascii=False)

CFG=cfg_load()

def hook(msg):
    if not CFG["wh"]: return
    try: requests.post(CFG["wh"], json={"content":msg}, timeout=6)
    except: pass

def packages():
    out=adb("pm list packages", 12)
    return sorted({l.replace("package:","").strip() for l in out.splitlines() if l.startswith("package:") and "roblox" in l.lower()})

def pid(pkg): return adb(f"pidof {pkg}", 5)
def cpu(pid):
    if not pid: return 0.0
    top=adb(f"top -n 1 -p {pid} | grep {pid}", 6)
    for p in top.split():
        if "%" in p:
            try: return float(p.replace("%","").replace(",","."))
            except: pass
    return 0.0

def focus(pkg):
    # melhor no VSPhone: resolve activity e start
    res=adb(f"cmd package resolve-activity --brief {pkg}", 8).splitlines()
    act=res[-1].strip() if res else ""
    if "/" in act: adb(f"am start -n {act}", 12)
    else: adb(f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1", 12)
    time.sleep(FOCUS_DELAY)

def ui_xml():
    adb("uiautomator dump /sdcard/u.xml >/dev/null 2>&1", 12)
    time.sleep(0.2)
    return adb("cat /sdcard/u.xml", 8)

def close_browsers():
    if not CFG.get("close_browser", True): return
    for b in CFG.get("browsers", []): adb(f"am force-stop {b}", 6)

def start_vip(pkg):
    vip=CFG["vip"]
    if not vip: return
    out=adb(f"am start -n {pkg}/com.roblox.client.ActivityProtocolLaunch -a android.intent.action.VIEW -d '{vip}'", 15)
    if "Error" in out or "Exception" in out:
        adb(f"am start -a android.intent.action.VIEW -d '{vip}'", 15)
    time.sleep(1.5)

def restart(pkg, reason):
    hook(f"🔄 `{pkg.split('.')[-1]}` -> {reason}")
    adb(f"am force-stop {pkg}", 10)
    time.sleep(1)
    close_browsers()
    start_vip(pkg)

def detect_bubble(xml):
    # “bolha” costuma ter número 1..10 em texto visível no overlay
    # Pegamos textos do XML e vemos se existe um text="1"..."10"
    # (isso não é perfeito mas funciona no seu caso)
    nums=set(str(i) for i in range(1,11))
    for t in re.findall(r'text="([^"]*)"', xml):
        if t.strip() in nums:
            return True
    return False

def detect_state(xml):
    x=xml.lower()
    if any(w in x for w in ["disconnected","connection lost","reconnect","reconectar","retry"]): return "DISCONNECTED"
    if "home" in x and "discover" in x and ("avatar" in x or "friends" in x): return "HOME"
    if any(w in x for w in ["welcome back","enter key","receive key","atlas","key system"]): return "KEY"
    return "OK"

def try_fix_bubble():
    # tenta “desbolhar” sem tap no meio (pra não chamar teclado)
    adb("input keyevent 4", 4)    # BACK
    time.sleep(0.2)
    adb("input keyevent 187", 4)  # APP_SWITCH
    time.sleep(0.4)
    adb("input keyevent 187", 4)  # volta
    time.sleep(0.4)

class Inst:
    def __init__(s,p):
        s.p=p; s.pid=""; s.cpu=0; s.sus=0; s.cd=0; s.st="INIT"; s.last="..."
    def tick(s):
        now=time.time()
        if now<s.cd: s.st="SYNC"; s.sus=0; return
        s.pid=pid(s.p)
        s.cpu=cpu(s.pid) if s.pid else 0.0
        if not s.pid: s.st="DEAD"; s.sus=SUS_LIMIT
        elif s.cpu>12: s.st="OK"; s.sus=0
        elif s.cpu<CPU_SUS: s.sus+=1; s.st="SUS" if s.sus>=SUS_LIMIT else "LOW"
        else: s.st="LOW"

def hud(insts):
    t=Table(title="REJOIN COMPACTO • Anti-Bolha", expand=True)
    t.add_column("PKG"); t.add_column("PID"); t.add_column("CPU", justify="right"); t.add_column("SUS", justify="right"); t.add_column("ST")
    for i in insts:
        name=i.p.split(".")[-1]
        t.add_row(name, (i.pid or "-")[:7], f"{i.cpu:.1f}%", f"{i.sus}/{SUS_LIMIT}", i.st)
    return t

def main():
    if not CFG["vip"]:
        CFG["vip"]=input("Cole VIP link (roblox:// ou https://): ").strip()
        CFG["wh"]=input("Webhook (opcional): ").strip()
        cfg_save(CFG)

    pkgs=packages()
    if not pkgs:
        print("Nenhum pacote roblox encontrado.")
        return

    insts=[Inst(p) for p in pkgs]
    next_check=0

    with Live(hud(insts), refresh_per_second=2, screen=True) as live:
        while True:
            for i in insts:
                i.tick()

                # só age quando SUS/DEAD
                if i.sus>=SUS_LIMIT and time.time()>=i.cd:
                    focus(i.p)
                    xml=ui_xml()

                    # bolha detectada -> tenta desbolhar -> recheck
                    if xml and detect_bubble(xml):
                        try_fix_bubble()
                        time.sleep(0.4)
                        xml=ui_xml()

                    state=detect_state(xml or "")
                    if state in ["DISCONNECTED","HOME"]:
                        restart(i.p, state)
                        i.cd=time.time()+COOLDOWN
                        i.sus=0
                    elif state=="KEY":
                        hook(f"🔑 `{i.p.split('.')[-1]}` -> KEY DETECTADA")
                        # opcional: se quiser reentrar ao invés de esperar:
                        # restart(i.p,"KEY")
                        i.cd=time.time()+15
                        i.sus=0
                    else:
                        # se UI veio vazia ou ficou bolha, força restart
                        if not xml or len(xml)<200:
                            restart(i.p, "UI_FAIL/BUBBLE")
                            i.cd=time.time()+COOLDOWN
                        i.sus=0

            live.update(hud(insts))
            time.sleep(CHECK)

if __name__=="__main__":
    main()
