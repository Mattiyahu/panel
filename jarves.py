#!/usr/bin/env python3
import os
import time
import json
import sys

CONFIG_FILE = "jarves_config.json"

DEFAULT_CONFIG = {
    "vip_link": "",
    "webhook_url": ""
}

# =============================
# 🎨 TEMA HACKER (SIMPLIFICADO)
# =============================
class JarvesTheme:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    GREEN = "\033[38;5;46m"
    CYAN = "\033[38;5;51m"
    RED = "\033[38;5;196m"
    YELLOW = "\033[38;5;226m"
    BLUE = "\033[38;5;39m"

    @staticmethod
    def clear():
        os.system("cls" if os.name == "nt" else "clear")

    @staticmethod
    def typing(text, delay=0.02):
        for c in text:
            print(c, end="", flush=True)
            time.sleep(delay)
        print()

    @staticmethod
    def loading(text="PROCESSING", duration=2):
        frames = ["▁▂▃▄▅▆▇█", "█▇▆▅▄▃▂▁"]
        start = time.time()
        i = 0
        while time.time() - start < duration:
            print(
                f"\r{JarvesTheme.CYAN}{frames[i % 2]} {text} {frames[i % 2]}{JarvesTheme.RESET}",
                end="",
                flush=True
            )
            i += 1
            time.sleep(0.15)
        print()

    @staticmethod
    def banner():
        print(f"""{JarvesTheme.GREEN}
 ██████╗  █████╗ ██████╗ ██╗   ██╗███████╗███████╗
 ██╔══██╗██╔══██╗██╔══██╗██║   ██║██╔════╝██╔════╝
 ██████╔╝███████║██████╔╝██║   ██║█████╗  ███████╗
 ██╔══██╗██╔══██║██╔══██╗╚██╗ ██╔╝██╔══╝  ╚════██║
 ██████╔╝██║  ██║██║  ██║ ╚████╔╝ ███████╗███████║
 ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝╚══════╝
{JarvesTheme.RESET}
        """)

# =============================
# ⚙️ CONFIG
# =============================
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {**DEFAULT_CONFIG, **data}
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

# =============================
# 📋 MENU
# =============================
def menu():
    cfg = load_config()

    while True:
        JarvesTheme.clear()
        JarvesTheme.banner()

        print(f"{JarvesTheme.CYAN}▶ JARVES CONTROL PANEL{JarvesTheme.RESET}\n")
        print(f"{JarvesTheme.BLUE}[1]{JarvesTheme.RESET} Set VIP Link")
        print(f"{JarvesTheme.BLUE}[2]{JarvesTheme.RESET} Set Webhook")
        print(f"{JarvesTheme.BLUE}[3]{JarvesTheme.RESET} Show Config")
        print(f"{JarvesTheme.RED}[0]{JarvesTheme.RESET} Exit\n")

        choice = input(f"{JarvesTheme.GREEN}➤ Select: {JarvesTheme.RESET}").strip()

        if choice == "1":
            JarvesTheme.loading("ACCESSING VIP CONFIG")
            cfg["vip_link"] = input("VIP Link: ").strip()
            save_config(cfg)
            JarvesTheme.typing("✔ VIP link saved.")

        elif choice == "2":
            JarvesTheme.loading("ACCESSING WEBHOOK CONFIG")
            cfg["webhook_url"] = input("Webhook URL: ").strip()
            save_config(cfg)
            JarvesTheme.typing("✔ Webhook saved.")

        elif choice == "3":
            JarvesTheme.loading("READING CONFIG")
            print(json.dumps(cfg, indent=2, ensure_ascii=False))
            input("\nPress Enter...")

        elif choice == "0":
            JarvesTheme.typing("Shutting down JARVES...")
            time.sleep(0.5)
            sys.exit(0)

        else:
            JarvesTheme.typing("Invalid option.")
            time.sleep(1)

# =============================
# 🚀 ENTRY
# =============================
if __name__ == "__main__":
    JarvesTheme.clear()
    JarvesTheme.banner()
    JarvesTheme.loading("INITIALIZING JARVES", 2)
    menu()
