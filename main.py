# Downloader 5K+ - Inicializador do Servidor e Interface Web
import os
import sys
import time
import webbrowser
import threading
import uvicorn

def open_browser():
    """Abre o navegador padrão automaticamente após a inicialização do servidor."""
    time.sleep(1.2)
    url = "http://127.0.0.1:8000"
    print(f"\n[OK] Abrindo Downloader 5K+ no navegador: {url}")
    webbrowser.open(url)

if __name__ == "__main__":
    print("=" * 60)
    print("           Downloader 5K+ - Servidor Iniciado")
    print("=" * 60)
    print(" * Interface Web:   http://127.0.0.1:8000")
    print(" * Motor Multimídia: yt-dlp + FFmpeg 9.0")
    print(" * Pressione CTRL + C no terminal para encerrar.")
    print("=" * 60)

    # Inicia abertura automática do navegador em uma thread separada
    threading.Thread(target=open_browser, daemon=True).start()

    # Inicia o servidor ASGI Uvicorn
    uvicorn.run(
        "backend.api:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
        reload=False
    )
