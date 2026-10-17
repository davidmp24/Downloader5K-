@echo off
cd /d "%~dp0"

:: Se o ambiente virtual nao existir ou a instalacao nao estiver completa, executa configuracao
if not exist ".venv\Scripts\python.exe" (
    echo [Downloader 5K+] Criando ambiente virtual Python...
    python -m venv .venv
)

if not exist ".venv\.installed" (
    echo [Downloader 5K+] Instalando dependencias do sistema...
    .\.venv\Scripts\pip install -r requirements.txt
    if %ERRORLEVEL% equ 0 (
        echo instalacao_concluida > .venv\.installed
    ) else (
        echo [Downloader 5K+] ERRO: Falha ao instalar dependencias.
        pause
        exit /b 1
    )
)

:: Inicia o servidor Python e o navegador em segundo plano de forma oculta
if exist "iniciar.vbs" (
    wscript //nologo "iniciar.vbs"
) else (
    start "" /b ".\.venv\Scripts\python.exe" main.py
)
exit
