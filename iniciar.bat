@echo off
title Downloader 5K+ - Servidor Web
color 0B
chcp 65001 >nul

echo =======================================================
echo          Iniciando Downloader 5K+ (Windows 10)
echo =======================================================
echo.

cd /d "%~dp0"

:: Verifica se o ambiente virtual existe
if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Criando ambiente virtual Python...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERRO] Python nao encontrado no PATH do sistema.
        pause
        exit /b 1
    )
    echo [2/3] Instalando dependencias essenciais...
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
)

echo [3/3] Iniciando aplicacao e abrindo navegador...
echo.
.\.venv\Scripts\python.exe main.py

pause
