@echo off
cd /d "%~dp0"

:: Se o ambiente virtual nao existir, realiza instalacao inicial
if not exist ".venv\Scripts\python.exe" (
    echo [Downloader 5K+] Configurando ambiente virtual Python...
    python -m venv .venv
    .\.venv\Scripts\pip install -r requirements.txt
)

:: Inicia o servidor Python e o navegador em segundo plano de forma oculta
if exist "iniciar.vbs" (
    wscript //nologo "iniciar.vbs"
) else (
    start "" /b ".\.venv\Scripts\python.exe" main.py
)
exit
