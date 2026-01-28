#!/data/data/com.termux/files/usr/bin/bash

# ============================================
#   SHAKO.DEV - AUTO SETUP PARA TERMUX
#   Script de instalação automática
# ============================================

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Banner
print_banner() {
    echo -e "${CYAN}"
    echo "      _           _                 _            "
    echo "  ___| |__   __ _| | _____       __| | _____   __"
    echo " / __| '_ \\ / _\` | |/ / _ \\     / _\` |/ _ \\ \\ / /"
    echo " \\__ \\ | | | (_| |   < (_) |   | (_| |  __/\\ V / "
    echo " |___/_| |_|\\__,_|_|\\_\\___(_)   \\__,_|\\___| \\_/  "
    echo -e "${NC}"
    echo -e "${MAGENTA}${BOLD}        AUTO SETUP FOR TERMUX${NC}"
    echo -e "${YELLOW}        Version 1.0.4 - Termux Compatible${NC}"
    echo ""
}

# Função para imprimir status
print_status() {
    echo -e "${CYAN}[*]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Verificar se está rodando no Termux
check_termux() {
    if [ ! -d "/data/data/com.termux" ]; then
        print_error "Este script deve ser executado no Termux!"
        exit 1
    fi
    print_success "Ambiente Termux detectado"
}

# Atualizar repositórios
update_repos() {
    print_status "Atualizando repositórios do Termux..."
    pkg update -y > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        print_success "Repositórios atualizados"
    else
        print_warning "Falha ao atualizar repositórios (continuando...)"
    fi
}

# Instalar dependências do sistema
install_system_deps() {
    print_status "Instalando dependências do sistema..."
    
    # Lista de pacotes necessários
    PACKAGES="python git"
    
    for pkg in $PACKAGES; do
        if ! command -v $pkg &> /dev/null; then
            print_status "Instalando $pkg..."
            pkg install -y $pkg > /dev/null 2>&1
            if [ $? -eq 0 ]; then
                print_success "$pkg instalado"
            else
                print_error "Falha ao instalar $pkg"
            fi
        else
            print_success "$pkg já está instalado"
        fi
    done
}

# Instalar pip se necessário
install_pip() {
    print_status "Verificando pip..."
    if ! command -v pip &> /dev/null; then
        print_status "Instalando pip..."
        python -m ensurepip --upgrade > /dev/null 2>&1
        if [ $? -ne 0 ]; then
            pkg install -y python-pip > /dev/null 2>&1
        fi
    fi
    print_success "pip disponível"
}

# Instalar dependências Python
install_python_deps() {
    print_status "Instalando dependências Python..."
    
    # Lista de pacotes Python necessários
    PYTHON_PACKAGES="requests rich prettytable psutil"
    
    for pkg in $PYTHON_PACKAGES; do
        print_status "Instalando $pkg..."
        pip install $pkg --quiet > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            print_success "$pkg instalado"
        else
            print_warning "Falha ao instalar $pkg (pode já estar instalado)"
        fi
    done
}

# Configurar permissões de armazenamento
setup_storage() {
    print_status "Configurando acesso ao armazenamento..."
    
    if [ ! -d "$HOME/storage" ]; then
        print_warning "Execute 'termux-setup-storage' manualmente se precisar de acesso ao armazenamento"
    else
        print_success "Armazenamento já configurado"
    fi
}

# Criar diretório de trabalho
setup_workspace() {
    print_status "Configurando diretório de trabalho..."
    
    SHAKO_DIR="$HOME/shako"
    
    if [ ! -d "$SHAKO_DIR" ]; then
        mkdir -p "$SHAKO_DIR"
        print_success "Diretório $SHAKO_DIR criado"
    else
        print_success "Diretório $SHAKO_DIR já existe"
    fi
    
    # Criar subdiretórios
    mkdir -p "$SHAKO_DIR/Shako.dev"
    
    # Copiar script principal se existir no mesmo diretório
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [ -f "$SCRIPT_DIR/shako.py" ]; then
        cp "$SCRIPT_DIR/shako.py" "$SHAKO_DIR/"
        print_success "shako.py copiado para $SHAKO_DIR"
    elif [ -f "./shako.py" ]; then
        cp "./shako.py" "$SHAKO_DIR/"
        print_success "shako.py copiado para $SHAKO_DIR"
    else
        print_warning "shako.py não encontrado. Copie manualmente para $SHAKO_DIR"
    fi
}

# Criar script de inicialização rápida
create_launcher() {
    print_status "Criando launcher..."
    
    LAUNCHER_PATH="$PREFIX/bin/shako"
    
    cat > "$LAUNCHER_PATH" << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
cd ~/shako
python shako.py "$@"
EOF
    
    chmod +x "$LAUNCHER_PATH"
    print_success "Launcher criado. Use 'shako' para iniciar"
}

# Verificar se tem acesso root (necessário para algumas funções)
check_root() {
    print_status "Verificando acesso root..."
    
    if command -v su &> /dev/null; then
        su -c "echo test" > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            print_success "Acesso root disponível"
            return 0
        fi
    fi
    
    print_warning "Acesso root não detectado"
    print_warning "Algumas funções podem não funcionar corretamente sem root"
    print_warning "Para funcionalidade completa, use Termux com Magisk/KernelSU"
    return 1
}

# Criar arquivo de configuração inicial
create_initial_config() {
    print_status "Criando configuração inicial..."
    
    CONFIG_DIR="$HOME/shako/Shako.dev"
    
    if [ ! -f "$CONFIG_DIR/config.json" ]; then
        cat > "$CONFIG_DIR/config.json" << 'EOF'
{
    "check_executor": "1",
    "command_8_configured": false,
    "disable_ui": "0",
    "interval": null,
    "lua_script_template": null,
    "package_prefix": "com.roblox",
    "webhook_url": null,
    "device_name": null
}
EOF
        print_success "Configuração inicial criada"
    else
        print_success "Configuração já existe"
    fi
}

# Função principal
main() {
    clear
    print_banner
    
    echo -e "${BOLD}Iniciando instalação do Shako.dev...${NC}"
    echo ""
    
    check_termux
    update_repos
    install_system_deps
    install_pip
    install_python_deps
    setup_storage
    setup_workspace
    create_initial_config
    create_launcher
    check_root
    
    echo ""
    echo -e "${GREEN}${BOLD}============================================${NC}"
    echo -e "${GREEN}${BOLD}   INSTALAÇÃO CONCLUÍDA COM SUCESSO!${NC}"
    echo -e "${GREEN}${BOLD}============================================${NC}"
    echo ""
    echo -e "${CYAN}Para iniciar o Shako.dev:${NC}"
    echo -e "  ${YELLOW}1.${NC} Digite: ${GREEN}shako${NC}"
    echo -e "  ${YELLOW}ou${NC}"
    echo -e "  ${YELLOW}2.${NC} Navegue até ~/shako e execute: ${GREEN}python shako.py${NC}"
    echo ""
    echo -e "${MAGENTA}Diretório de trabalho: ~/shako${NC}"
    echo ""
    
    if [ ! -f "$HOME/shako/shako.py" ]; then
        echo -e "${YELLOW}${BOLD}ATENÇÃO:${NC} Copie o arquivo shako.py para ~/shako/"
        echo ""
    fi
    
    echo -e "${CYAN}Dica: Se precisar de acesso root, use Magisk ou KernelSU${NC}"
    echo ""
}

# Executar
main "$@"
