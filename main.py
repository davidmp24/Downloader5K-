# Downloader 5K+ - Inicializador do Servidor e Interface Web
import os
import sys
import time
import webbrowser
import threading
import subprocess

# Garante suporte seguro a stdout/stderr mesmo sem console
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

def kill_stale_process_on_port(port: int = 8000):
    """Encerra processos órfãos na porta para evitar conflitos de segundo plano."""
    try:
        current_pid = str(os.getpid())
        output = subprocess.check_output(
            f"netstat -ano | findstr :{port}",
            shell=True,
            stderr=subprocess.DEVNULL
        ).decode("latin-1", errors="ignore")

        for line in output.strip().splitlines():
            parts = line.strip().split()
            if len(parts) >= 5 and "LISTENING" in parts:
                pid = parts[-1]
                if pid.isdigit() and pid != current_pid and pid != "0":
                    subprocess.run(
                        f"taskkill /F /PID {pid}",
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    time.sleep(0.3)
    except Exception:
        pass

def open_browser():
    """Abre o navegador padrão automaticamente após a inicialização do servidor."""
    time.sleep(1.2)
    url = "http://127.0.0.1:8000"
    try:
        webbrowser.open(url)
    except Exception:
        pass

if __name__ == "__main__":
    # Libera a porta 8000 caso tenha ficado algum processo anterior aberto
    kill_stale_process_on_port(8000)

    try:
        print("=" * 60)
        print("           Downloader 5K+ - Servidor Iniciado")
        print("=" * 60)
        print(" * Interface Web:   http://127.0.0.1:8000")
        print(" * Motor Multimídia: yt-dlp + FFmpeg")
        print("=" * 60)
    except Exception:
        pass

    # Inicia abertura automática do navegador em uma thread separada
    threading.Thread(target=open_browser, daemon=True).start()

    # Inicia o servidor ASGI Uvicorn
    import uvicorn
    from backend.api import app
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="info",
        use_colors=False,
        reload=False
    )
