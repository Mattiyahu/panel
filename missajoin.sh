#!/bin/bash

# ====== PACKAGES (somente 01/02/03) ======
PACKAGES=(
  "com.roblox.clienb"
  "com.roblox.cliend"
  "com.roblox.cliene"
)

PROTO_ACTIVITY="com.roblox.client.ActivityProtocolLaunch"

CHECK_INTERVAL=15
LOW_CPU_THRESHOLD="0.3"
MAX_LOWCPU_TIME=90
COOLDOWN_TIME=120

MAX_COUNT=$((MAX_LOWCPU_TIME / CHECK_INTERVAL))

declare -A lowcpu_count
declare -A cooldown

# ===================== UI =====================
logo() {
  clear
  echo -e "\033[95;1m"
  cat <<'EOF'
        ██████╗ ███████╗     ██╗ ██████╗ ██╗███╗   ██╗████████╗ ██████╗  ██████╗
        ██╔══██╗██╔════╝     ██║██╔═══██╗██║████╗  ██║╚══██╔══╝██╔═══██╗██╔═══██╗
        ██████╔╝█████╗       ██║██║   ██║██║██╔██╗ ██║   ██║   ██║   ██║██║   ██║
        ██╔══██╗██╔══╝  ██   ██║██║   ██║██║██║╚██╗██║   ██║   ██║   ██║██║   ██║
        ██║  ██║███████╗╚█████╔╝╚██████╔╝██║██║ ╚████║   ██║   ╚██████╔╝╚██████╔╝
        ╚═╝  ╚═╝╚══════╝ ╚════╝  ╚═════╝ ╚═╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝  ╚═════╝
EOF
  echo -e "\033[96;1m                      AutoRejoin Panel • by MSA"
  echo -e "\033[93m              (Compatível somente com clones 01 / 02 / 03)\033[0m"
  echo ""
}

msg() {
  # mensagem discreta com hora
  local text="$1"
  echo -e "\033[90m[$(date +%H:%M:%S)]\033[0m $text"
}

# ===================== CORE =====================
get_pid() {
  adb shell pidof "$1" 2>/dev/null | tr -d '\r'
}

get_cpu_by_pid() {
  adb shell top -n 1 | tr -d '\r' | awk -v p="$1" '$1==p {print $9; exit}'
}

open_vip() {
  local pkg="$1"
  adb shell am start \
    -n "${pkg}/${PROTO_ACTIVITY}" \
    -a android.intent.action.VIEW \
    -d "$WEB_LINK" >/dev/null 2>&1
  sleep 6
}

reconnect_pkg() {
  local pkg="$1"

  msg "🔄 Reiniciando sessão: $pkg"
  adb shell am force-stop "$pkg" >/dev/null 2>&1
  sleep 2

  msg "🌐 Abrindo VIP..."
  open_vip "$pkg"

  cooldown["$pkg"]=$(( $(date +%s) + COOLDOWN_TIME ))
}

# ===================== START =====================
logo

echo -e "\033[97;1mCole o link do seu Servidor VIP:\033[0m"
echo -e "\033[90mEx: https://www.roblox.com/games/1537690962/... ?privateServerLinkCode=XXXX\033[0m"
read -r -p "VIP Link: " WEB_LINK
echo ""

# validação simples
if [[ "$WEB_LINK" != *"roblox.com/games/"* ]] || [[ "$WEB_LINK" != *"privateServerLinkCode="* ]]; then
  msg "❌ Link inválido. Cole o link VIP completo."
  exit 1
fi

msg "✅ Link configurado."
msg "🟢 Iniciando clones (01/02/03)..."
echo ""

# Abre todos uma vez
for pkg in "${PACKAGES[@]}"; do
  reconnect_pkg "$pkg"
done

msg "✅ Monitoramento ativo."
echo ""

# ===================== LOOP =====================
while true; do
  now=$(date +%s)

  for pkg in "${PACKAGES[@]}"; do

    # cooldown
    if [ -n "${cooldown["$pkg"]}" ] && [ "$now" -lt "${cooldown["$pkg"]}" ]; then
      # mensagem discreta
      msg "⏳ Aguardando estabilidade: $pkg"
      continue
    fi

    pid="$(get_pid "$pkg")"

    # caiu/fechou
    if [ -z "$pid" ]; then
      msg "⚠️ Sessão indisponível detectada: $pkg"
      lowcpu_count["$pkg"]=0
      reconnect_pkg "$pkg"
      continue
    fi

    # checagem interna (sem revelar)
    cpu="$(get_cpu_by_pid "$pid")"
    cpu="${cpu/,/.}"
    cpu="$(echo "$cpu" | tr -d '%')"

    if [ -z "$cpu" ]; then
      msg "⚠️ Sem resposta momentânea: $pkg"
      continue
    fi

    below=$(awk -v c="$cpu" -v t="$LOW_CPU_THRESHOLD" 'BEGIN{print (c <= t) ? 1 : 0}')

    if [ "$below" -eq 1 ]; then
      lowcpu_count["$pkg"]=$(( ${lowcpu_count["$pkg"]:-0} + 1 ))

      # não mostra CPU, só status
      msg "🟡 Verificando sessão: $pkg"

      if [ "${lowcpu_count["$pkg"]}" -ge "$MAX_COUNT" ]; then
        msg "⚠️ Reconexão preventiva: $pkg"
        lowcpu_count["$pkg"]=0
        reconnect_pkg "$pkg"
      fi
    else
      lowcpu_count["$pkg"]=0
      msg "✅ OK: $pkg"
    fi
  done

  sleep "$CHECK_INTERVAL"
done
