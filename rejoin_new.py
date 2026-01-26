import subprocess
import time
import re
import requests
import datetime

# Configurações
CHECK_INTERVAL = 15
LOW_CPU_THRESHOLD = 0.3
MAX_LOWCPU_TIME = 90
COOLDOWN_TIME = 120
WEBHOOK_URL = "" # O usuário deve preencher aqui

# Constantes do Roblox
PROTO_ACTIVITY = "com.roblox.client.ActivityProtocolLaunch"

def log(message):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[\033[90m{timestamp}\033[0m] {message}")

def run_adb(command):
    try:
        result = subprocess.run(f"adb shell {command}", shell=True, capture_output=True, text=True)
        return result.stdout.strip()
    except Exception as e:
        return ""

def get_roblox_packages():
    """Encontra qualquer pacote que contenha 'roblox' no nome."""
    output = run_adb("pm list packages roblox")
    packages = []
    for line in output.splitlines():
        if line.startswith("package:"):
            pkg = line.replace("package:", "").strip()
            packages.append(pkg)
    return packages

def get_pid(package):
    pid = run_adb(f"pidof {package}")
    return pid if pid else None

def get_cpu_usage(pid):
    output = run_adb(f"top -n 1 -p {pid}")
    # Procura a linha que contém o PID e extrai a CPU (geralmente a 9ª coluna)
    lines = output.splitlines()
    for line in lines:
        parts = line.split()
        if parts and parts[0] == pid:
            try:
                # O formato do top pode variar, mas geralmente CPU é a 9ª coluna
                # Em algumas versões do Android/top, pode ser diferente.
                # Vamos tentar encontrar o valor que parece uma porcentagem.
                for part in parts:
                    if "%" in part:
                        return float(part.replace("%", "").replace(",", "."))
                # Se não achou com %, tenta a 9ª coluna padrão
                return float(parts[8].replace(",", "."))
            except:
                return None
    return None

def check_ui_state(package):
    """
    Verifica o estado da UI:
    - 'bolha': Roblox em modo flutuante/bubble
    - 'home': Área de início
    - 'disconnected': Tela de desconexão
    - 'key_request': Pedido de key do Atlas
    """
    # Verifica o foco atual
    focus = run_adb("dumpsys window windows | grep -E 'mCurrentFocus'")
    
    # Se o foco estiver no sistema ou em algo que não seja o pacote, mas o processo existe
    # Isso geralmente indica que o app está em background ou em modo 'bolha' (overlay)
    if package not in focus:
        # Se houver um processo mas não estiver em foco, tratamos como 'bolha' ou fora de jogo
        return "bubble_or_background"

    # Captura a hierarquia da UI para análise de texto (mais preciso)
    # Tentamos capturar rápido, se falhar pulamos para não travar o loop
    ui_xml = run_adb("uiautomator dump /sdcard/view.xml > /dev/null 2>&1 && cat /sdcard/view.xml")
    
    if not ui_xml:
        return "ok" # Se não conseguir ler a UI, assume OK para evitar falsos positivos

    # Lógica de detecção por palavras-chave
    ui_lower = ui_xml.lower()
    
    # Desconectado
    if "disconnected" in ui_lower or "desconectado" in ui_lower or "connection lost" in ui_lower:
        return "disconnected"
    
    # Home / Área de Início (Roblox App fora de um jogo)
    # Geralmente tem botões de 'Home', 'Avatar', 'Chat'
    if "home" in ui_lower and "discover" in ui_lower and "avatar" in ui_lower:
        return "home"
    
    # Atlas Key Request
    # O Atlas costuma ter um campo de texto ou título específico
    if "atlas" in ui_lower and ("key" in ui_lower or "enter" in ui_lower):
        return "key_request"

    return "ok"

def send_webhook(message):
    if not WEBHOOK_URL:
        log("⚠️ Webhook URL não configurada.")
        return
    try:
        payload = {"content": message}
        requests.post(WEBHOOK_URL, json=payload)
        log("🚀 Webhook enviado!")
    except Exception as e:
        log(f"❌ Erro ao enviar webhook: {e}")

def reconnect(package, vip_link):
    log(f"🔄 Reiniciando sessão: {package}")
    run_adb(f"am force-stop {package}")
    time.sleep(2)
    log("🌐 Abrindo VIP...")
    run_adb(f"am start -n {package}/{PROTO_ACTIVITY} -a android.intent.action.VIEW -d '{vip_link}'")
    time.sleep(6)

def main():
    print("\033[95;1m")
    print("        ██████╗ ███████╗     ██╗ ██████╗ ██╗███╗   ██╗████████╗ ██████╗  ██████╗")
    print("        ██╔══██╗██╔════╝     ██║██╔═══██╗██║████╗  ██║╚══██╔══╝██╔═══██╗██╔═══██╗")
    print("        ██████╔╝█████╗       ██║██║   ██║██║██╔██╗ ██║   ██║   ██║   ██║██║   ██║")
    print("        ██╔══██╗██╔══╝  ██   ██║██║   ██║██║██║╚██╗██║   ██║   ██║   ██║██║   ██║")
    print("        ██║  ██║███████╗╚█████╔╝╚██████╔╝██║██║ ╚████║   ██║   ╚██████╔╝╚██████╔╝")
    print("        ╚═╝  ╚═╝╚══════╝ ╚════╝  ╚═════╝ ╚═╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝  ╚═════╝")
    print("\033[96;1m                      AutoRejoin Panel • Python Edition\033[0m")
    print("")

    vip_link = input("\033[97;1mCole o link do seu Servidor VIP:\033[0m ")
    if "roblox.com/games/" not in vip_link:
        print("❌ Link inválido.")
        return

    global WEBHOOK_URL
    WEBHOOK_URL = input("\033[97;1mCole a URL do Webhook (opcional):\033[0m ")

    packages = get_roblox_packages()
    if not packages:
        log("❌ Nenhum pacote Roblox encontrado.")
        return
    
    log(f"✅ Encontrados {len(packages)} pacotes: {', '.join(packages)}")
    
    lowcpu_count = {pkg: 0 for pkg in packages}
    cooldowns = {pkg: 0 for pkg in packages}

    while True:
        now = time.time()
        
        for pkg in packages:
            if now < cooldowns[pkg]:
                continue

            pid = get_pid(pkg)
            if not pid:
                log(f"⚠️ {pkg} fechado. Reiniciando...")
                reconnect(pkg, vip_link)
                cooldowns[pkg] = time.time() + COOLDOWN_TIME
                continue

            # Verificar estado da UI
            state = check_ui_state(pkg)
            if state == "disconnected":
                log(f"⚠️ {pkg} desconectado em {pkg}. Reiniciando...")
                reconnect(pkg, vip_link)
                cooldowns[pkg] = time.time() + COOLDOWN_TIME
                continue
            elif state == "home":
                log(f"⚠️ {pkg} na tela Home. Reiniciando...")
                reconnect(pkg, vip_link)
                cooldowns[pkg] = time.time() + COOLDOWN_TIME
                continue
            elif state == "bubble_or_background":
                log(f"⚠️ {pkg} em modo bolha ou background. Reiniciando...")
                reconnect(pkg, vip_link)
                cooldowns[pkg] = time.time() + COOLDOWN_TIME
                continue
            elif state == "key_request":
                log(f"🔑 Atlas pedindo key em {pkg}!")
                send_webhook(f"⚠️ **Atlas Key Request** detectado no pacote: `{pkg}`")
                # Após o webhook, podemos esperar ou reiniciar. Vamos apenas avisar por enquanto.
            
            # Checagem de CPU
            cpu = get_cpu_usage(pid)
            if cpu is not None:
                if cpu <= LOW_CPU_THRESHOLD:
                    lowcpu_count[pkg] += 1
                    log(f"🟡 {pkg} com CPU baixa ({cpu}%). Verificação {lowcpu_count[pkg]}/{MAX_LOWCPU_TIME//CHECK_INTERVAL}")
                    if lowcpu_count[pkg] >= (MAX_LOWCPU_TIME // CHECK_INTERVAL):
                        log(f"⚠️ Reconexão preventiva: {pkg}")
                        reconnect(pkg, vip_link)
                        lowcpu_count[pkg] = 0
                else:
                    lowcpu_count[pkg] = 0
                    # log(f"✅ {pkg} OK ({cpu}%)")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
