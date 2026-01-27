#!/usr/bin/env python3
"""
Script de Descoberta de Key do Delta - Múltiplos Métodos
Testa várias formas de encontrar o ticket/key sem clicar em Get Key

Uso: python3 test_key_discovery.py
"""
import subprocess
import re
import os
import time
import requests

# ═══════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES
# ═══════════════════════════════════════════════════════════════════
ROBLOX_PACKAGES = [
    "com.roblox.cliene",
    "com.roblox.clienb", 
    "com.roblox.cliend",
    "com.roblox.client",
]

# Padrões para busca
TICKET_PATTERN = r'[A-Za-z0-9]{100,500}'  # Ticket é um código longo
URL_PATTERN = r'https://auth\.platorelay\.com/a\?d=([A-Za-z0-9]+)'
KEY_PATTERN = r'FREE_[a-f0-9]{32}'

# ═══════════════════════════════════════════════════════════════════
# FUNÇÕES AUXILIARES
# ═══════════════════════════════════════════════════════════════════
def run_cmd(cmd, timeout=30):
    """Executa comando shell"""
    try:
        result = subprocess.check_output(
            cmd, shell=True, stderr=subprocess.DEVNULL, timeout=timeout
        ).decode(errors='ignore').strip()
        return result
    except:
        return ""

def run_root(cmd, timeout=30):
    """Executa comando como root"""
    return run_cmd(f"su -c '{cmd}'", timeout)

def get_pid(package):
    """Obtém o PID de um pacote"""
    pid = run_root(f"pidof {package}")
    if pid and pid.split()[0].isdigit():
        return pid.split()[0]
    return None

def get_running_roblox():
    """Encontra processos Roblox rodando"""
    running = []
    for pkg in ROBLOX_PACKAGES:
        pid = get_pid(pkg)
        if pid:
            running.append((pkg, pid))
    return running

def get_key_from_api(ticket):
    """Faz requisição para API e obtém a key"""
    try:
        url = f"https://auth.platorelay.com/api/session/status?ticket={ticket}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
            'Accept': 'application/json',
            'x-client-version': '5.3.2',
            'x-client-name': 'platoboost webclient',
        }
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        if data.get('success') and data.get('data', {}).get('key'):
            return data['data']['key']
    except Exception as e:
        print(f"    [!] Erro na API: {e}")
    return None

# ═══════════════════════════════════════════════════════════════════
# MÉTODO 1: LEITURA DE MEMÓRIA RAM
# ═══════════════════════════════════════════════════════════════════
def method_1_memory_scan(pid, pkg):
    """Escaneia a memória RAM procurando pelo ticket"""
    print(f"\n[MÉTODO 1] Escaneando memória RAM do {pkg} (PID: {pid})...")
    
    results = []
    
    # 1.1: Busca por URL completa
    print("  [1.1] Buscando URL completa...")
    cmd = f"grep -ao 'auth.platorelay.com/a?d=[A-Za-z0-9]*' /proc/{pid}/mem 2>/dev/null | head -3"
    out = run_root(cmd, timeout=60)
    if out:
        for line in out.splitlines():
            match = re.search(r'd=([A-Za-z0-9]+)', line)
            if match:
                ticket = match.group(1)
                print(f"    [+] Ticket encontrado: {ticket[:50]}...")
                results.append(('memory_url', ticket))
    
    # 1.2: Busca em regiões específicas de memória
    print("  [1.2] Buscando em regiões heap/dalvik...")
    maps = run_root(f"cat /proc/{pid}/maps | grep -E 'heap|dalvik|anon'")
    if maps:
        for line in maps.splitlines()[:10]:  # Limita a 10 regiões
            try:
                addr = line.split()[0]
                start, end = addr.split('-')
                start_int = int(start, 16)
                end_int = int(end, 16)
                size = end_int - start_int
                
                if size > 10 * 1024 * 1024:  # Pula regiões > 10MB
                    continue
                
                cmd = f"dd if=/proc/{pid}/mem bs=4096 skip={start_int//4096} count={size//4096} 2>/dev/null | strings | grep -E 'platorelay|FREE_'"
                out = run_root(cmd, timeout=30)
                
                if out:
                    # Procura ticket
                    url_match = re.search(URL_PATTERN, out)
                    if url_match:
                        results.append(('memory_region', url_match.group(1)))
                    
                    # Procura key direta
                    key_match = re.search(KEY_PATTERN, out)
                    if key_match:
                        results.append(('memory_key', key_match.group(0)))
                        
            except:
                continue
    
    # 1.3: Strings em todo o processo
    print("  [1.3] Strings em /proc/{pid}/mem...")
    cmd = f"strings /proc/{pid}/mem 2>/dev/null | grep -E 'platorelay|FREE_' | head -10"
    out = run_root(cmd, timeout=60)
    if out:
        url_match = re.search(URL_PATTERN, out)
        if url_match:
            results.append(('strings', url_match.group(1)))
        key_match = re.search(KEY_PATTERN, out)
        if key_match:
            results.append(('strings_key', key_match.group(0)))
    
    return results

# ═══════════════════════════════════════════════════════════════════
# MÉTODO 2: ARQUIVOS DO EXECUTOR
# ═══════════════════════════════════════════════════════════════════
def method_2_executor_files():
    """Procura em arquivos do executor Delta"""
    print("\n[MÉTODO 2] Procurando em arquivos do executor...")
    
    results = []
    
    # Possíveis caminhos do Delta
    paths = [
        "/sdcard/Download/",
        "/sdcard/Android/data/com.roblox.client/",
        "/sdcard/Android/data/com.roblox.cliene/",
        "/sdcard/Android/data/com.roblox.clienb/",
        "/sdcard/Android/data/com.roblox.cliend/",
        "/data/data/com.roblox.client/",
        "/data/data/com.roblox.cliene/",
        "/data/data/com.roblox.clienb/",
        "/data/data/com.roblox.cliend/",
        "/sdcard/delta/",
        "/sdcard/Delta/",
        "/sdcard/executor/",
    ]
    
    for path in paths:
        print(f"  [*] Verificando {path}...")
        
        # Procura arquivos de log/config
        cmd = f"find {path} -type f -name '*.txt' -o -name '*.log' -o -name '*.json' 2>/dev/null | head -20"
        files = run_root(cmd, timeout=10)
        
        if files:
            for f in files.splitlines():
                content = run_root(f"cat '{f}' 2>/dev/null | head -100")
                if content:
                    # Procura ticket
                    url_match = re.search(URL_PATTERN, content)
                    if url_match:
                        print(f"    [+] Encontrado em {f}")
                        results.append(('file', url_match.group(1), f))
                    
                    # Procura key
                    key_match = re.search(KEY_PATTERN, content)
                    if key_match:
                        print(f"    [+] KEY em {f}: {key_match.group(0)}")
                        results.append(('file_key', key_match.group(0), f))
    
    # Procura em SharedPreferences
    print("  [*] Verificando SharedPreferences...")
    for pkg in ROBLOX_PACKAGES:
        prefs_path = f"/data/data/{pkg}/shared_prefs/"
        cmd = f"cat {prefs_path}*.xml 2>/dev/null"
        content = run_root(cmd, timeout=10)
        if content and ('platorelay' in content or 'FREE_' in content):
            print(f"    [+] Encontrado em SharedPreferences de {pkg}")
            url_match = re.search(URL_PATTERN, content)
            if url_match:
                results.append(('prefs', url_match.group(1), pkg))
            key_match = re.search(KEY_PATTERN, content)
            if key_match:
                results.append(('prefs_key', key_match.group(0), pkg))
    
    return results

# ═══════════════════════════════════════════════════════════════════
# MÉTODO 3: CLIPBOARD
# ═══════════════════════════════════════════════════════════════════
def method_3_clipboard():
    """Verifica a área de transferência"""
    print("\n[MÉTODO 3] Verificando clipboard...")
    
    results = []
    
    # Método via service call
    cmd = "service call clipboard 2 s16 com.android.shell"
    out = run_root(cmd, timeout=5)
    if out and 'platorelay' in out:
        print("    [+] URL encontrada no clipboard!")
        url_match = re.search(URL_PATTERN, out)
        if url_match:
            results.append(('clipboard', url_match.group(1)))
    
    # Método via dumpsys
    cmd = "dumpsys clipboard"
    out = run_root(cmd, timeout=5)
    if out and 'platorelay' in out:
        print("    [+] URL encontrada via dumpsys!")
        url_match = re.search(URL_PATTERN, out)
        if url_match:
            results.append(('clipboard_dump', url_match.group(1)))
    
    return results

# ═══════════════════════════════════════════════════════════════════
# MÉTODO 4: LOGCAT
# ═══════════════════════════════════════════════════════════════════
def method_4_logcat():
    """Procura nos logs do sistema"""
    print("\n[MÉTODO 4] Verificando logcat...")
    
    results = []
    
    # Limpa e captura logs recentes
    cmd = "logcat -d | grep -iE 'platorelay|platoboost|delta|FREE_' | tail -50"
    out = run_root(cmd, timeout=15)
    
    if out:
        print("    [+] Logs relevantes encontrados!")
        url_match = re.search(URL_PATTERN, out)
        if url_match:
            results.append(('logcat', url_match.group(1)))
        key_match = re.search(KEY_PATTERN, out)
        if key_match:
            results.append(('logcat_key', key_match.group(0)))
    
    return results

# ═══════════════════════════════════════════════════════════════════
# MÉTODO 5: NETWORK CONNECTIONS
# ═══════════════════════════════════════════════════════════════════
def method_5_network():
    """Verifica conexões de rede ativas"""
    print("\n[MÉTODO 5] Verificando conexões de rede...")
    
    results = []
    
    # Verifica conexões TCP
    cmd = "netstat -an | grep -i 'ESTABLISHED'"
    out = run_root(cmd, timeout=10)
    if out:
        print(f"    [*] {len(out.splitlines())} conexões ativas")
    
    # Procura em /proc/net
    cmd = "cat /proc/net/tcp /proc/net/tcp6 2>/dev/null"
    out = run_root(cmd, timeout=10)
    # Isso mostra conexões mas não o conteúdo
    
    return results

# ═══════════════════════════════════════════════════════════════════
# MÉTODO 6: SQLITE DATABASES
# ═══════════════════════════════════════════════════════════════════
def method_6_databases():
    """Procura em bancos de dados SQLite"""
    print("\n[MÉTODO 6] Verificando bancos de dados...")
    
    results = []
    
    for pkg in ROBLOX_PACKAGES:
        db_path = f"/data/data/{pkg}/databases/"
        
        # Lista databases
        cmd = f"ls {db_path} 2>/dev/null"
        dbs = run_root(cmd, timeout=5)
        
        if dbs:
            print(f"    [*] Databases em {pkg}: {dbs.replace(chr(10), ', ')}")
            
            for db in dbs.splitlines():
                if db.endswith('.db') or db.endswith('.sqlite'):
                    # Tenta ler com strings
                    cmd = f"strings {db_path}{db} 2>/dev/null | grep -E 'platorelay|FREE_'"
                    out = run_root(cmd, timeout=10)
                    if out:
                        print(f"    [+] Encontrado em {db}!")
                        url_match = re.search(URL_PATTERN, out)
                        if url_match:
                            results.append(('database', url_match.group(1), db))
                        key_match = re.search(KEY_PATTERN, out)
                        if key_match:
                            results.append(('database_key', key_match.group(0), db))
    
    return results

# ═══════════════════════════════════════════════════════════════════
# MÉTODO 7: WEBVIEW CACHE
# ═══════════════════════════════════════════════════════════════════
def method_7_webview_cache():
    """Procura no cache do WebView"""
    print("\n[MÉTODO 7] Verificando cache do WebView...")
    
    results = []
    
    for pkg in ROBLOX_PACKAGES:
        cache_paths = [
            f"/data/data/{pkg}/cache/",
            f"/data/data/{pkg}/app_webview/",
            f"/data/data/{pkg}/app_webview/Default/Cache/",
        ]
        
        for cache_path in cache_paths:
            cmd = f"find {cache_path} -type f 2>/dev/null | head -30"
            files = run_root(cmd, timeout=10)
            
            if files:
                for f in files.splitlines():
                    cmd = f"strings '{f}' 2>/dev/null | grep -E 'platorelay|FREE_' | head -5"
                    out = run_root(cmd, timeout=10)
                    if out:
                        print(f"    [+] Encontrado em cache: {f}")
                        url_match = re.search(URL_PATTERN, out)
                        if url_match:
                            results.append(('cache', url_match.group(1), f))
                        key_match = re.search(KEY_PATTERN, out)
                        if key_match:
                            results.append(('cache_key', key_match.group(0), f))
    
    return results

# ═══════════════════════════════════════════════════════════════════
# MÉTODO 8: ENVIRONMENT VARIABLES
# ═══════════════════════════════════════════════════════════════════
def method_8_environ(pid):
    """Verifica variáveis de ambiente do processo"""
    print(f"\n[MÉTODO 8] Verificando environ do PID {pid}...")
    
    results = []
    
    cmd = f"cat /proc/{pid}/environ 2>/dev/null | tr '\\0' '\\n'"
    out = run_root(cmd, timeout=10)
    
    if out and ('platorelay' in out or 'FREE_' in out):
        print("    [+] Encontrado em environ!")
        url_match = re.search(URL_PATTERN, out)
        if url_match:
            results.append(('environ', url_match.group(1)))
        key_match = re.search(KEY_PATTERN, out)
        if key_match:
            results.append(('environ_key', key_match.group(0)))
    
    return results

# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════
def main():
    print("=" * 70)
    print("  DESCOBERTA DE KEY DO DELTA - MÚLTIPLOS MÉTODOS")
    print("=" * 70)
    
    # Verifica ROOT
    print("\n[*] Verificando ROOT...")
    if "root" not in run_root("whoami"):
        print("[!] ROOT não detectado!")
        return
    print("[+] ROOT OK!")
    
    # Encontra processos Roblox
    print("\n[*] Procurando processos Roblox...")
    running = get_running_roblox()
    
    if not running:
        print("[-] Nenhum processo Roblox encontrado!")
        print("[*] Certifique-se de que o Roblox está aberto com a tela de key.")
        return
    
    print(f"[+] Encontrados {len(running)} processos:")
    for pkg, pid in running:
        print(f"    - {pkg} (PID: {pid})")
    
    # Coleta todos os resultados
    all_results = []
    
    # Executa todos os métodos
    for pkg, pid in running:
        all_results.extend(method_1_memory_scan(pid, pkg))
        all_results.extend(method_8_environ(pid))
    
    all_results.extend(method_2_executor_files())
    all_results.extend(method_3_clipboard())
    all_results.extend(method_4_logcat())
    all_results.extend(method_5_network())
    all_results.extend(method_6_databases())
    all_results.extend(method_7_webview_cache())
    
    # Processa resultados
    print("\n" + "=" * 70)
    print("  RESULTADOS")
    print("=" * 70)
    
    tickets_found = []
    keys_found = []
    
    for result in all_results:
        if 'key' in result[0].lower() and len(result) >= 2:
            keys_found.append(result)
        elif len(result) >= 2:
            tickets_found.append(result)
    
    # Mostra tickets encontrados
    if tickets_found:
        print(f"\n[+] {len(tickets_found)} TICKETS encontrados:")
        for i, t in enumerate(tickets_found[:5]):
            source = t[0]
            ticket = t[1]
            print(f"\n    [{i+1}] Fonte: {source}")
            print(f"        Ticket: {ticket[:60]}...")
            
            # Tenta obter a key via API
            print(f"        [*] Tentando obter key via API...")
            key = get_key_from_api(ticket)
            if key:
                print(f"        [+] ✅ KEY OBTIDA: {key}")
                keys_found.append(('api', key))
            else:
                print(f"        [-] Não foi possível obter key")
    
    # Mostra keys encontradas
    if keys_found:
        print(f"\n[+] {len(keys_found)} KEYS encontradas:")
        for k in keys_found:
            print(f"    ✅ {k[1]} (via {k[0]})")
    
    if not tickets_found and not keys_found:
        print("\n[-] Nenhum ticket ou key encontrado.")
        print("\n[*] Possíveis razões:")
        print("    1. A tela 'Welcome Back!' ainda não apareceu")
        print("    2. O executor Delta não está injetado")
        print("    3. O ticket pode estar em formato diferente")
        print("    4. Pode precisar de mais permissões")
    
    print("\n" + "=" * 70)
    print("  FIM DO SCAN")
    print("=" * 70)

if __name__ == "__main__":
    main()
