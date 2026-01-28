#!/data/data/com.termux/files/usr/bin/bash
# Script de instalação do Shouko para Termux
# Execute com: bash install.sh

echo -e "\033[1;36m╔════════════════════════════════════════════════════════════╗\033[0m"
echo -e "\033[1;36m║     SHOUKO INSTALLER - TERMUX EDITION                     ║\033[0m"
echo -e "\033[1;36m╚════════════════════════════════════════════════════════════╝\033[0m"
echo ""

# Cores
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
RED='\033[1;31m'
CYAN='\033[1;36m'
NC='\033[0m' # No Color

# Função para imprimir com cor
print_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
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

# Verificar se está no Termux
if [ ! -d "/data/data/com.termux" ]; then
    print_error "Este script deve ser executado no Termux!"
    exit 1
fi

print_success "Termux detectado!"
echo ""

# Solicitar permissões de armazenamento
print_info "Solicitando permissões de armazenamento..."
termux-setup-storage
sleep 2
print_success "Permissões configuradas!"
echo ""

# Atualizar repositórios
print_info "Atualizando repositórios do Termux..."
pkg update -y > /dev/null 2>&1
print_success "Repositórios atualizados!"
echo ""

# Instalar dependências do sistema
print_info "Instalando dependências do sistema..."
PACKAGES="python git wget curl"
for pkg in $PACKAGES; do
    print_info "Instalando $pkg..."
    pkg install -y $pkg > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        print_success "$pkg instalado!"
    else
        print_error "Erro ao instalar $pkg"
    fi
done
echo ""

# Instalar módulos Python
print_info "Instalando módulos Python..."
PYTHON_PACKAGES="prettytable requests psutil rich"
for pypkg in $PYTHON_PACKAGES; do
    print_info "Instalando $pypkg..."
    pip install $pypkg --upgrade > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        print_success "$pypkg instalado!"
    else
        print_error "Erro ao instalar $pypkg"
    fi
done
echo ""

# Criar diretório do projeto
print_info "Criando estrutura de diretórios..."
mkdir -p ~/shouko
cd ~/shouko
print_success "Diretórios criados!"
echo ""

# Tornar o script executável
if [ -f "shouko_termux.py" ]; then
    chmod +x shouko_termux.py
    print_success "Permissões de execução configuradas!"
else
    print_warning "Arquivo shouko_termux.py não encontrado no diretório atual"
fi
echo ""

# Criar alias para execução fácil
print_info "Criando atalho 'shouko' para execução..."
echo 'alias shouko="cd ~/shouko && python shouko_termux.py"' >> ~/.bashrc
source ~/.bashrc 2>/dev/null
print_success "Atalho criado! Use o comando 'shouko' para executar"
echo ""

# Mensagem final
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║            INSTALAÇÃO CONCLUÍDA COM SUCESSO!               ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}Como usar:${NC}"
echo -e "  1. Execute: ${YELLOW}cd ~/shouko${NC}"
echo -e "  2. Execute: ${YELLOW}python shouko_termux.py${NC}"
echo -e "  ${GREEN}OU${NC}"
echo -e "  - Use o comando: ${YELLOW}shouko${NC} (após reiniciar o Termux)"
echo ""
echo -e "${YELLOW}Nota:${NC} Algumas funções podem requerer acesso root"
echo -e "${YELLOW}Nota:${NC} Certifique-se de ter apps Roblox instalados"
echo ""

read -p "Pressione Enter para continuar..."
