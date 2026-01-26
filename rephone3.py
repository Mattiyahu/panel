#!/usr/bin/env python3
import subprocess, time, re, os, json, datetime

CFG="config.json"
CHECK=6
COOLDOWN=90
FOCUS_DELAY=0.7

WORDS_REJOIN = [
    "reconnect","reconnecting","disconnected","connection lost","lost connection",
    "reconectar","desconectado","tentar novamente","retry"
]
WORDS_HOME = ["home","discover","avatar","friends","search","pesquisar"]
WORDS_KEY  = ["welcome back","enter key","receive key","atlas","key system","continue"]

def sh(cmd, t=15):
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL, timeout=t).decode(errors="ignore").strip()
    except:
        return ""

def adb(cmd, t=15): return sh(f"adb shell {cmd}", t)

def load():
    d={"vip":"","wh":""}
    if os.path.exists(CFG):
        try: d.update(json.load(open(CFG,"r",encoding="utf-8")))
        except: pass
    return d

def save(d): json.dump(d, open(CFG,"w",encoding="utf-8"), indent=2, ensure_ascii=False)

def hook(msg, wh):
    if not wh: return
    try: subprocess.run(["python","-c",f"import requests;requests.post('{wh}',json={{'content':{msg!r}}},timeout=6)"], timeout=8)
    except: pass

def packages():
    out=adb("pm list packages", 12)
    pk=[]
    for l in out.splitlines():
        if l.startswith("package:"):
            p=l.replace("package:","").strip()
            if "roblox" in p.lower(): pk.append(p)
    return sorted(set(pk))

def focus(pkg):
    res=adb(f"cmd package resolve-activity --brief {pkg}", 10).splitlines()
    act=res[-1].strip() if res else ""
    if "/" in act: adb(f"am start -n {act}", 12)
    else: adb(f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1", 12)
    time.sleep(FOCUS_DELAY)

def screenshot_local(name="screen.png"):
    adb(f"screencap -p /sdcard/{name}", 10)
    sh(f"adb pull /sdcard/{name} ./{name}", 15)
    return os.path.exists(f"./{name}")

def ocr_text(img="screen.png"):
    # OCR rápido
    sh("rm -f out.txt", 5)
    sh(f"tesseract {img} out -l eng --psm 6", 25)
    if os.path.exists("out.txt"):
        txt=open("out.txt","r",encoding="utf-8",errors="ignore").read().lower()
        return re.sub(r"\s+"," ",txt)
    return ""

def stop(pkg): adb(f"am force-stop {pkg}", 10)

def start_vip(pkg, vip):
    out=adb(f"am start -n {pkg}/com.roblox.client.ActivityProtocolLaunch -a android.intent.action.VIEW -d '{vip}'", 15)
    if "Error" in out or "Exception" in out:
        adb(f"am start -a android.intent.action.VIEW -d '{vip}'", 15)
    time.sleep(2)

def main():
    cfg=load()
    if not cfg["vip"]:
        cfg["vip"]=input("Cole VIP link: ").strip()
        cfg["wh"]=input("Webhook (opcional): ").strip()
        save(cfg)

    pkgs=packages()
    if not pkgs:
        print("Sem pacotes roblox.")
        return
    print("Pacotes:", pkgs)

    cd={p:0 for p in pkgs}

    while True:
        for p in pkgs:
            if time.time()<cd[p]: 
                continue

            focus(p)

            if not screenshot_local("r.png"):
                continue

            txt=ocr_text("r.png")
            if not txt:
                # OCR falhou -> não faz nada
                continue

            if any(w in txt for w in WORDS_REJOIN):
                print("REJOIN:", p)
                stop(p); time.sleep(1)
                start_vip(p, cfg["vip"])
                cd[p]=time.time()+COOLDOWN
            elif sum(1 for w in WORDS_HOME if w in txt) >= 2:
                print("HOME:", p)
                stop(p); time.sleep(1)
                start_vip(p, cfg["vip"])
                cd[p]=time.time()+COOLDOWN
            elif any(w in txt for w in WORDS_KEY):
                print("KEY/CONTINUE:", p)
                # aqui você pode clicar ou só avisar
                # hook(f"🔑 KEY/CONTINUE em {p}", cfg["wh"])
                cd[p]=time.time()+20

        time.sleep(CHECK)

if __name__=="__main__":
    main()
