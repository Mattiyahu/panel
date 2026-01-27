#!/usr/bin/env python3
"""
AUTO KEY CAPTURE - Delta Key Extractor
Captura a key automaticamente monitorando o tráfego de rede

Requer ROOT e tcpdump instalado no Termux

Instalação:
    pkg install root-repo
    pkg install tcpdump

Uso: python3 auto_key_capture.py
"""
import subprocess
import re
import os
import time
import threading
import signal
import sys

# ═══════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES
# ═══════════════════════════════════════════════════════════════════
KEY_PATTERN = r'FREE_[a-f0-9]{32}'
TICKET_PATTERN = r'"ticket":"([A-Za-z0-9]+)"'

# ═══════════════════════════════════════════════════════════════════
# FUNÇÕES AUXILIARES
# ═══════════════════════════════════════════════════════════════════
def run_cmd(cmd, timeout=10):
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL, timeout=timeout).decode(errors='ignore').strip()
    except:
        return ""

def run_root(cmd, timeout=10):
    return run_cmd(f"su -c '{cmd}'", timeout)

def copy_to_clipboard(text):
    """Copia texto para o clipboard"""
    try:
        # Método 1: termux-clipboard-set
        subprocess.run(f'echo "{text}" | termux-clipboard-set', shell=True, timeout=5)
    except:
        pass
    try:
        # Método 2: service call
        run_root(f'service call clipboard 2 i32 2 i32 {len(text)} str16 "{text}"')
    except:
        pass

def show_banner():
    print("""
╔══════════════════════════════════════════════════════════════╗
║           AUTO KEY CAPTURE - Delta Key Extractor             ║
║                                                              ║
║  Este script monitora o tráfego e captura a key              ║
║  automaticamente quando você clicar em Continue/Get Key      ║
╚══════════════════════════════════════════════════════════════╝
""")

# ═══════════════════════════════════════════════════════════════════
# MÉTODO 1: MONITORAR LOGCAT EM TEMPO REAL
# ═══════════════════════════════════════════════════════════════════
class LogcatMonitor:
    def __init__(self):
        self.running = False
        self.key_found = None
    
    def start(self):
        print("[LOGCAT] Iniciando monitoramento de logs...")
        self.running = True
        
        # Limpa logcat
        run_root("logcat -c")
        
        # Inicia processo de logcat
        proc = subprocess.Popen(
            "su -c 'logcat -v raw'",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True
        )
        
        while self.running:
            try:
                line = proc.stdout.readline()
                if not line:
                    continue
                
                # Procura por key
                key_match = re.search(KEY_PATTERN, line)
                if key_match:
                    self.key_found = key_match.group(0)
                    print(f"\n[LOGCAT] ✅ KEY ENCONTRADA: {self.key_found}")
                    return self.key_found
                
                # Procura por ticket
                if 'platorelay' in line.lower() or 'platoboost' in line.lower():
                    print(f"[LOGCAT] Atividade detectada: {line[:80]}...")
                    
            except:
                continue
        
        proc.terminate()
        return None
    
    def stop(self):
        self.running = False

# ═══════════════════════════════════════════════════════════════════
# MÉTODO 2: MONITORAR ARQUIVOS EM TEMPO REAL
# ═══════════════════════════════════════════════════════════════════
class FileMonitor:
    def __init__(self):
        self.running = False
        self.key_found = None
        self.watch_paths = [
            "/sdcard/Download/",
            "/sdcard/delta/",
            "/sdcard/Delta/",
            "/data/local/tmp/",
        ]
    
    def start(self):
        print("[FILES] Iniciando monitoramento de arquivos...")
        self.running = True
        
        while self.running:
            for path in self.watch_paths:
                # Procura arquivos modificados recentemente
                cmd = f"find {path} -type f -mmin -1 2>/dev/null"
                files = run_root(cmd, timeout=5)
                
                if files:
                    for f in files.splitlines():
                        content = run_root(f"cat '{f}' 2>/dev/null | tail -100")
                        if content:
                            key_match = re.search(KEY_PATTERN, content)
                            if key_match:
                                self.key_found = key_match.group(0)
                                print(f"\n[FILES] ✅ KEY ENCONTRADA em {f}: {self.key_found}")
                                return self.key_found
            
            time.sleep(1)
        
        return None
    
    def stop(self):
        self.running = False

# ═══════════════════════════════════════════════════════════════════
# MÉTODO 3: MONITORAR CLIPBOARD EM TEMPO REAL
# ═══════════════════════════════════════════════════════════════════
class ClipboardMonitor:
    def __init__(self):
        self.running = False
        self.key_found = None
        self.last_content = ""
    
    def start(self):
        print("[CLIPBOARD] Iniciando monitoramento de clipboard...")
        self.running = True
        
        while self.running:
            # Tenta ler clipboard
            content = run_cmd("termux-clipboard-get 2>/dev/null", timeout=3)
            
            if content and content != self.last_content:
                self.last_content = content
                
                # Procura key
                key_match = re.search(KEY_PATTERN, content)
                if key_match:
                    self.key_found = key_match.group(0)
                    print(f"\n[CLIPBOARD] ✅ KEY ENCONTRADA: {self.key_found}")
                    return self.key_found
                
                # Procura URL do platorelay
                if 'platorelay' in content:
                    print(f"[CLIPBOARD] URL detectada: {content[:60]}...")
            
            time.sleep(0.5)
        
        return None
    
    def stop(self):
        self.running = False

# ═══════════════════════════════════════════════════════════════════
# MÉTODO 4: TCPDUMP (CAPTURA DE PACOTES)
# ═══════════════════════════════════════════════════════════════════
class TcpdumpMonitor:
    def __init__(self):
        self.running = False
        self.key_found = None
    
    def start(self):
        print("[TCPDUMP] Iniciando captura de pacotes...")
        self.running = True
        
        # Verifica se tcpdump está instalado
        if not run_root("which tcpdump"):
            print("[TCPDUMP] tcpdump não instalado. Pulando...")
            return None
        
        # Inicia tcpdump filtrando tráfego HTTP
        proc = subprocess.Popen(
            "su -c 'tcpdump -A -s 0 -l port 443 2>/dev/null'",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True
        )
        
        buffer = ""
        while self.running:
            try:
                line = proc.stdout.readline()
                if not line:
                    continue
                
                buffer += line
                
                # Procura key no buffer
                key_match = re.search(KEY_PATTERN, buffer)
                if key_match:
                    self.key_found = key_match.group(0)
                    print(f"\n[TCPDUMP] ✅ KEY ENCONTRADA: {self.key_found}")
                    proc.terminate()
                    return self.key_found
                
                # Limpa buffer se ficar muito grande
                if len(buffer) > 100000:
                    buffer = buffer[-50000:]
                    
            except:
                continue
        
        proc.terminate()
        return None
    
    def stop(self):
        self.running = False

# ═══════════════════════════════════════════════════════════════════
# MÉTODO 5: MONITORAR RESPOSTA HTTP VIA /proc/net
# ═══════════════════════════════════════════════════════════════════
class ProcNetMonitor:
    def __init__(self):
        self.running = False
        self.key_found = None
    
    def get_roblox_uid(self):
        """Obtém UID dos apps Roblox"""
        uids = []
        for pkg in ["com.roblox.cliene", "com.roblox.clienb", "com.roblox.cliend", "com.roblox.client"]:
            out = run_root(f"dumpsys package {pkg} | grep userId")
            match = re.search(r'userId=(\d+)', out)
            if match:
                uids.append(match.group(1))
        return uids
    
    def start(self):
        print("[PROCNET] Iniciando monitoramento de /proc/net...")
        self.running = True
        
        uids = self.get_roblox_uid()
        print(f"[PROCNET] UIDs do Roblox: {uids}")
        
        while self.running:
            # Monitora tráfego TCP
            for uid in uids:
                # Verifica bytes recebidos
                rx_path = f"/proc/uid_stat/{uid}/tcp_rcv"
                rx = run_root(f"cat {rx_path} 2>/dev/null")
                if rx:
                    # Tráfego detectado
                    pass
            
            time.sleep(0.5)
        
        return None
    
    def stop(self):
        self.running = False

# ═══════════════════════════════════════════════════════════════════
# CONTROLADOR PRINCIPAL
# ═══════════════════════════════════════════════════════════════════
class KeyCapture:
    def __init__(self):
        self.monitors = []
        self.key_found = None
        self.running = False
    
    def start_all_monitors(self):
        """Inicia todos os monitores em threads separadas"""
        self.running = True
        
        # Cria monitores
        monitors_classes = [
            LogcatMonitor,
            ClipboardMonitor,
            FileMonitor,
            # TcpdumpMonitor,  # Descomentado se tcpdump estiver instalado
        ]
        
        threads = []
        for MonitorClass in monitors_classes:
            monitor = MonitorClass()
            self.monitors.append(monitor)
            t = threading.Thread(target=self._run_monitor, args=(monitor,))
            t.daemon = True
            t.start()
            threads.append(t)
        
        return threads
    
    def _run_monitor(self, monitor):
        """Executa um monitor e verifica se encontrou key"""
        key = monitor.start()
        if key:
            self.key_found = key
            self.running = False
    
    def stop_all(self):
        """Para todos os monitores"""
        self.running = False
        for monitor in self.monitors:
            monitor.stop()
    
    def wait_for_key(self, timeout=120):
        """Aguarda até encontrar uma key ou timeout"""
        start_time = time.time()
        
        while self.running and (time.time() - start_time) < timeout:
            if self.key_found:
                return self.key_found
            time.sleep(0.5)
        
        return self.key_found

# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════
def main():
    show_banner()
    
    # Verifica ROOT
    print("[*] Verificando ROOT...")
    if "root" not in run_root("whoami"):
        print("[!] ROOT não detectado! Este script requer ROOT.")
        return
    print("[+] ROOT OK!\n")
    
    print("[*] Iniciando monitores...")
    print("[*] Agora vá no Roblox e clique em Continue/Get Key")
    print("[*] A key será capturada automaticamente!\n")
    print("-" * 60)
    
    capture = KeyCapture()
    
    # Handler para Ctrl+C
    def signal_handler(sig, frame):
        print("\n\n[*] Parando monitores...")
        capture.stop_all()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Inicia monitores
    capture.start_all_monitors()
    
    # Aguarda key
    print("\n[*] Aguardando key... (Ctrl+C para sair)\n")
    key = capture.wait_for_key(timeout=300)  # 5 minutos
    
    capture.stop_all()
    
    if key:
        print("\n" + "=" * 60)
        print("  ✅ KEY CAPTURADA COM SUCESSO!")
        print("=" * 60)
        print(f"\n  KEY: {key}\n")
        
        # Copia para clipboard
        copy_to_clipboard(key)
        print("[+] Key copiada para o clipboard!")
        
        # Pergunta se quer usar automaticamente
        resp = input("\nDeseja colar a key no jogo automaticamente? (s/n): ")
        if resp.lower() == 's':
            # Volta para o Roblox e cola
            run_cmd("am start -n com.roblox.cliene/com.roblox.client.startup.ActivitySplash")
            time.sleep(2)
            run_root("input keyevent 279")  # Paste
            print("[+] Key colada!")
    else:
        print("\n[-] Timeout - Key não encontrada")
        print("[*] Tente novamente ou verifique se o tráfego está sendo capturado")

if __name__ == "__main__":
    main()
