#!/bin/bash

echo -e "\033[95;1m"
echo "Starting Auto-Setup for Roblox Monitor..."
echo -e "\033[0m"

# Atualizar repositórios
pkg update -y && pkg upgrade -y

# Instalar X11 Repo e ImageMagick
pkg install x11-repo -y
pkg install imagemagick -y
pkg install tesseract -y # Para OCR se necessário no futuro

# Instalar Python e dependências de sistema
pkg install python python-pip ncurses-utils -y

# Instalar bibliotecas Python solicitadas
pip install requests psutil rich pysqlite3

echo -e "\033[92;1m"
echo "Setup complete! All dependencies installed."
echo "Now you can run: python panel.py"
echo -e "\033[0m"
