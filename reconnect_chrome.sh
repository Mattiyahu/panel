#!/bin/bash

# ============================================
# 🚀 SETUP - Roblox AutoRejoin Hacker Edition
# ============================================
# Script de configuração automática do ambiente
# Compatível com Termux e Linux
# ============================================

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Função para printar mensagens coloridas
print_header() {
    echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${GREEN}  🖥️  ROBLOX AUTOREJOIN - HACKER EDITION SETUP  🖥️  ${CYAN}║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_step() {
    echo -e "${BLUE}[▶]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

print_info() {
    echo -e "${CYAN}[ℹ]${NC} $1"
}

# Detecta o ambiente
detect_environment() {
    if [ -n "$TERMUX_VERSION" ] || [ -d "/data/data/com.termux" ]; then
        ENV="termux"
        print_success "Ambiente detectado: Termux"
    else
        ENV="linux"
        print_success "Ambiente detectado: Linux/Unix"
    fi
}

# Verifica se está rodando como root (não recomendado no Termux)
check_root() {
    if [ "$EUID" -eq 0 ] && [ "$ENV" != "termux" ]; then 
        print_warning "Rodando como root. Não é recomendado para uso pessoal."
        read -p "Continuar assim mesmo? (s/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Ss]$ ]]; then
            exit 1
        fi
    fi
}

# Atualiza repositórios
update_repos() {
    print_step "Atualizando repositórios..."
    
    if [ "$ENV" = "termux" ]; then
        pkg update -y || {
            print_error "Falha ao atualizar repositórios do Termux"
            return 1
        }
    else
        if command -v apt-get &> /dev/null; then
            sudo apt-get update -y || print_warning "Falha ao atualizar apt"
        elif command -v yum &> /dev/null; then
            sudo yum update -y || print_warning "Falha ao atualizar yum"
        elif command -v pacman &> /dev/null; then
            sudo pacman -Sy || print_warning "Falha ao atualizar pacman"
        fi
    fi
    
    print_success "Repositórios atualizados"
}

# Instala Python
install_python() {
    print_step "Verificando instalação do Python..."
    
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        print_success "Python já instalado: v$PYTHON_VERSION"
        return 0
    fi
    
    print_warning "Python não encontrado. Instalando..."
    
    if [ "$ENV" = "termux" ]; then
        pkg install python -y || {
            print_error "Falha ao instalar Python no Termux"
            return 1
        }
    else
        if command -v apt-get &> /dev/null; then
            sudo apt-get install python3 python3-pip -y
        elif command -v yum &> /dev/null; then
            sudo yum install python3 python3-pip -y
        elif command -v pacman &> /dev/null; then
            sudo pacman -S python python-pip --noconfirm
        else
            print_error "Gerenciador de pacotes não suportado"
            return 1
        fi
    fi
    
    print_success "Python instalado com sucesso"
}

# Instala ADB
install_adb() {
    print_step "Verificando instalação do ADB..."
    
    if command -v adb &> /dev/null; then
        ADB_VERSION=$(adb --version | head -n1)
        print_success "ADB já instalado: $ADB_VERSION"
        return 0
    fi
    
    print_warning "ADB não encontrado. Instalando..."
    
    if [ "$ENV" = "termux" ]; then
        pkg install android-tools -y || {
            print_error "Falha ao instalar ADB no Termux"
            return 1
        }
    else
        if command -v apt-get &> /dev/null; then
            sudo apt-get install android-tools-adb -y
        elif command -v yum &> /dev/null; then
            sudo yum install android-tools -y
        elif command -v pacman &> /dev/null; then
            sudo pacman -S android-tools --noconfirm
        else
            print_error "Gerenciador de pacotes não suportado"
            return 1
        fi
    fi
    
    print_success "ADB instalado com sucesso"
}

# Instala pacotes Python necessários
install_python_packages() {
    print_step "Instalando pacotes Python..."
    
    # Verifica se pip está instalado
    if ! command -v pip3 &> /dev/null && ! command -v pip &> /dev/null; then
        print_error "pip não encontrado. Instalando..."
        
        if [ "$ENV" = "termux" ]; then
            pkg install python-pip -y
        else
            if command -v apt-get &> /dev/null; then
                sudo apt-get install python3-pip -y
            fi
        fi
    fi
    
    # Define o comando pip correto
    if command -v pip3 &> /dev/null; then
        PIP_CMD="pip3"
    else
        PIP_CMD="pip"
    fi
    
    print_info "Usando: $PIP_CMD"
    
    # Atualiza pip
    print_step "Atualizando pip..."
    $PIP_CMD install --upgrade pip --quiet
    
    # Lista de pacotes necessários (o script atual não requer pacotes externos)
    # Mas vamos preparar para futuras necessidades
    PACKAGES=""
    
    if [ -n "$PACKAGES" ]; then
        print_step "Instalando dependências Python: $PACKAGES"
        $PIP_CMD install $PACKAGES --quiet || {
            print_warning "Algumas dependências podem ter falha na instalação"
        }
        print_success "Pacotes Python instalados"
    else
        print_info "Nenhum pacote Python adicional necessário"
    fi
}

# Cria estrutura de diretórios
create_directories() {
    print_step "Criando estrutura de diretórios..."
    
    # Diretório para logs (opcional, para futuras implementações)
    mkdir -p logs 2>/dev/null
    
    print_success "Diretórios criados"
}

# Configura permissões
set_permissions() {
    print_step "Configurando permissões..."
    
    # Torna o script principal executável se existir
    if [ -f "shoko.py" ]; then
        chmod +x shoko.py
        print_success "shoko.py configurado como executável"
    else
        print_warning "shoko.py não encontrado no diretório atual"
    fi
    
    # Torna este script executável
    chmod +x "$0" 2>/dev/null
}

# Testa conexão ADB
test_adb_connection() {
    print_step "Testando conexão ADB..."
    
    if ! command -v adb &> /dev/null; then
        print_error "ADB não está disponível"
        return 1
    fi
    
    # Inicia servidor ADB
    adb start-server &>/dev/null
    
    # Verifica dispositivos conectados
    DEVICES=$(adb devices | grep -w "device" | wc -l)
    
    if [ "$DEVICES" -gt 0 ]; then
        print_success "Dispositivo(s) ADB conectado(s): $DEVICES"
        adb devices
    else
        print_warning "Nenhum dispositivo ADB conectado"
        print_info "Conecte seu dispositivo Android e ative a Depuração USB"
        print_info "Depois execute: adb devices"
    fi
}

# Cria arquivo de configuração exemplo
create_sample_config() {
    print_step "Criando arquivo de configuração exemplo..."
    
    if [ -f "hacker_config.json" ]; then
        print_info "Arquivo de configuração já existe"
        return 0
    fi
    
    cat > hacker_config.json << 'EOF'
{
  "web_link": "https://www.roblox.com/games/1537690962/Bee-Swarm-Simulator?privateServerLinkCode=05888256464342538313491710978310",
  "webhook_url": "",
  "check_interval": 10,
  "low_cpu_threshold": 8.0,
  "max_lowcpu_time": 10,
  "cooldown_time": 10,
  "packages": []
}
EOF
    
    print_success "Arquivo de configuração criado: hacker_config.json"
}

# Mostra instruções finais
show_final_instructions() {
    echo ""
    echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${GREEN}              SETUP CONCLUÍDO COM SUCESSO! ✓              ${CYAN}║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}📋 PRÓXIMOS PASSOS:${NC}"
    echo ""
    echo -e "${GREEN}1.${NC} Conecte seu dispositivo Android via USB"
    echo -e "${GREEN}2.${NC} Ative a Depuração USB nas configurações do desenvolvedor"
    echo -e "${GREEN}3.${NC} Execute: ${CYAN}adb devices${NC} (e autorize no dispositivo)"
    echo -e "${GREEN}4.${NC} Inicie o programa: ${CYAN}python3 shoko.py${NC}"
    echo ""
    echo -e "${YELLOW}⚙️  COMANDOS ÚTEIS:${NC}"
    echo ""
    echo -e "  ${CYAN}adb devices${NC}          - Lista dispositivos conectados"
    echo -e "  ${CYAN}adb connect IP:5555${NC} - Conecta via WiFi (requer root/setup)"
    echo -e "  ${CYAN}python3 shoko.py${NC}     - Inicia o monitor"
    echo ""
    echo -e "${YELLOW}📁 ARQUIVOS CRIADOS:${NC}"
    echo ""
    echo -e "  ${CYAN}hacker_config.json${NC}   - Configurações do sistema"
    echo -e "  ${CYAN}logs/${NC}                - Diretório para logs (futuro)"
    echo ""
    echo -e "${GREEN}🚀 Sistema pronto para uso! Boa sorte, hacker!${NC}"
    echo ""
}

# ============================================
# EXECUÇÃO PRINCIPAL
# ============================================

clear
print_header

print_info "Iniciando configuração do ambiente..."
echo ""

# Detecta ambiente
detect_environment
check_root

# Instalações
update_repos
install_python
install_adb
install_python_packages

# Configurações
create_directories
set_permissions
create_sample_config

# Testes
test_adb_connection

# Finalização
show_final_instructions

exit 0
