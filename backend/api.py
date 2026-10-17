# Downloader5K - Servidor de API FastAPI & WebSockets
import os
import sys
import asyncio
import logging
import threading
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.db import init_db, get_db_connection, load_settings, save_settings, DEFAULT_DOWNLOAD_DIR
from backend.downloader import MediaInspector, download_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DownloaderAPI")

# Whitelist de formatos e resoluções para segurança (C4)
ALLOWED_RESOLUTIONS = {"best", "4320", "2160", "1440", "1080", "720", "480", "360", "240", "144"}
ALLOWED_CONTAINERS = {"mp4", "mkv", "webm", "mov"}
ALLOWED_AUDIO_FORMATS = {"mp3", "m4a", "flac", "wav", "opus"}
ALLOWED_AUDIO_QUALITIES = {"0", "320", "256", "192", "128", "96", "64"}

_folder_dialog_lock = threading.Lock()

def validate_and_sanitize_options(options: Dict[str, Any]) -> Dict[str, Any]:
    """Valida e sanitiza caminhos e parâmetros de formato recebidos do cliente (C4)."""
    sanitized = dict(options or {})
    dest_dir = sanitized.get("dest_dir")
    settings = load_settings()

    if not dest_dir:
        dest_dir = settings.get("download_dir", DEFAULT_DOWNLOAD_DIR)

    dest_path = os.path.normpath(os.path.abspath(dest_dir))
    win_dir = os.environ.get("SystemRoot", "C:\\Windows")
    if dest_path.lower().startswith(win_dir.lower()):
        dest_path = DEFAULT_DOWNLOAD_DIR

    sanitized["dest_dir"] = dest_path

    if "resolution" in sanitized and str(sanitized["resolution"]) not in ALLOWED_RESOLUTIONS:
        sanitized["resolution"] = "1080"
    if "container" in sanitized and sanitized["container"].lower() not in ALLOWED_CONTAINERS:
        sanitized["container"] = "mp4"
    if "audio_format" in sanitized and sanitized["audio_format"].lower() not in ALLOWED_AUDIO_FORMATS:
        sanitized["audio_format"] = "mp3"
    if "audio_quality" in sanitized and str(sanitized["audio_quality"]) not in ALLOWED_AUDIO_QUALITIES:
        sanitized["audio_quality"] = "320"

    return sanitized


class ConnectionManager:
    """Gerencia conexões WebSocket ativas para streaming em tempo real e auto-shutdown seguro (C2, A1)."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.loop = None
        self.shutdown_timer: Optional[asyncio.TimerHandle] = None
        self.has_connected_once: bool = False

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.has_connected_once = True

        # Cancela qualquer contagem de desligamento se uma nova aba/recarregamento ocorrer
        if self.shutdown_timer:
            self.shutdown_timer.cancel()
            self.shutdown_timer = None
            logger.info("Nova aba/conexão detectada. Desligamento automático cancelado.")

        logger.info(f"Cliente WebSocket conectado. Total ativos: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"Cliente WebSocket desconectado. Total ativos: {len(self.active_connections)}")

        # Se não há mais nenhuma aba ativa e o usuário já abriu o sistema anteriormente, inicia timer para desligamento
        if len(self.active_connections) == 0 and self.has_connected_once:
            self.schedule_shutdown(delay=4.0)

    def schedule_shutdown(self, delay: float = 4.0):
        """Agenda encerramento seguro do processo python caso nenhuma aba seja aberta."""
        if self.shutdown_timer:
            self.shutdown_timer.cancel()
            self.shutdown_timer = None

        logger.info(f"Nenhuma janela web ativa. Servidor será encerrado em {delay}s caso não haja atividade...")

        def _do_shutdown():
            if len(self.active_connections) > 0:
                logger.info("Shutdown cancelado: conexão WebSocket ainda ativa.")
                return
            if len(download_manager.active_tasks) > 0:
                logger.info("Shutdown adiado: downloads ainda em andamento.")
                self.schedule_shutdown(delay=10.0)
                return
            logger.info("Janela do sistema fechada pelo usuário. Encerrando servidor Python automaticamente.")
            os._exit(0)

        if self.loop and self.loop.is_running():
            self.shutdown_timer = self.loop.call_later(delay, _do_shutdown)

    async def broadcast_async(self, message: Dict[str, Any]):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for d in disconnected:
            self.disconnect(d)

    def broadcast(self, message: Dict[str, Any]):
        """Método síncrono chamado por threads do yt-dlp para despachar no event loop."""
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast_async(message), self.loop)


ws_manager = ConnectionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    ws_manager.loop = asyncio.get_running_loop()
    download_manager.set_broadcast_callback(ws_manager.broadcast)
    logger.info("Downloader5K Core iniciado com sucesso.")
    yield
    logger.info("Downloader5K Core desligado.")

app = FastAPI(title="Downloader5K API", lifespan=lifespan)

# CORS restrito exclusivamente às origens locais seguras (C3)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1",
        "http://localhost",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

@app.get("/api/inspect")
async def inspect_url(url: str = Query(...)):
    """Inspeciona URL e extrai títulos, durações e resoluções."""
    if not url:
        raise HTTPException(status_code=400, detail="URL inválida ou vazia.")

    try:
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, MediaInspector.inspect, url)
        settings = load_settings()
        data["smart_mode"] = settings.get("smart_mode", False)
        data["settings"] = settings
        return data
    except Exception as e:
        logger.error(f"Erro ao inspecionar: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/download")
async def start_download(payload: Dict[str, Any] = Body(...)):
    url = payload.get("url")
    title = payload.get("title", "Vídeo sem título")
    author = payload.get("author", "Desconhecido")
    thumbnail = payload.get("thumbnail", "")
    duration = payload.get("duration", 0)
    download_type = payload.get("download_type", "video")
    format_note = payload.get("format_note", "")
    raw_options = payload.get("options", {})

    if not url:
        raise HTTPException(status_code=400, detail="URL obrigatória.")

    options = validate_and_sanitize_options(raw_options)

    task_id = download_manager.create_download(
        url=url,
        title=title,
        author=author,
        thumbnail=thumbnail,
        duration=duration,
        download_type=download_type,
        format_note=format_note,
        options=options,
    )

    return {"task_id": task_id, "status": "pending"}

@app.post("/api/download/batch")
async def start_batch_download(payload: Dict[str, Any] = Body(...)):
    """Inicia o download de múltiplos vídeos selecionados de uma playlist."""
    items = payload.get("items", [])
    download_type = payload.get("download_type", "video")
    format_note = payload.get("format_note", "")
    raw_options = payload.get("options", {})

    if not items:
        raise HTTPException(status_code=400, detail="Nenhum vídeo selecionado na playlist.")

    options = validate_and_sanitize_options(raw_options)

    created_tasks = []
    for item in items:
        url = item.get("url")
        if not url:
            continue
        title = item.get("title", "Vídeo de Playlist")
        author = item.get("uploader") or item.get("author", "YouTube")
        thumbnail = item.get("thumbnail", "")
        duration = item.get("duration", 0)

        task_id = download_manager.create_download(
            url=url,
            title=title,
            author=author,
            thumbnail=thumbnail,
            duration=duration,
            download_type=download_type,
            format_note=format_note,
            options=options,
        )
        created_tasks.append({
            "task_id": task_id,
            "title": title,
            "author": author,
            "thumbnail": thumbnail,
            "download_type": download_type,
            "format_note": format_note,
        })

    return {"status": "queued", "count": len(created_tasks), "tasks": created_tasks}

@app.post("/api/download/smart")
async def smart_download(payload: Dict[str, str] = Body(...)):
    """Executa o download diretamente com as preferências do Smart Mode."""
    url = payload.get("url", "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL inválida.")

    settings = load_settings()
    loop = asyncio.get_running_loop()
    try:
        info = await loop.run_in_executor(None, MediaInspector.inspect, url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if info.get("is_playlist"):
        return {"is_playlist": True, "info": info}

    download_type = settings.get("default_type", "video")
    raw_options = {
        "dest_dir": settings.get("download_dir"),
        "resolution": settings.get("default_quality", "1080"),
        "container": settings.get("default_video_format", "mp4"),
        "audio_format": settings.get("default_audio_format", "mp3"),
        "audio_quality": settings.get("default_audio_bitrate", "320"),
        "embed_subtitles": settings.get("embed_subtitles", True),
        "organize_by_genre": settings.get("organize_by_genre", True),
    }
    options = validate_and_sanitize_options(raw_options)

    if download_type == "audio":
        format_note = f"{options['audio_format'].upper()} ({options['audio_quality']}k)"
    else:
        format_note = f"{options['resolution']}p ({options['container'].upper()})"

    task_id = download_manager.create_download(
        url=url,
        title=info.get("title", "Vídeo"),
        author=info.get("uploader", "Desconhecido"),
        thumbnail=info.get("thumbnail", ""),
        duration=info.get("duration", 0),
        download_type=download_type,
        format_note=format_note,
        options=options,
    )

    return {"task_id": task_id, "status": "pending", "title": info.get("title")}

@app.get("/api/downloads")
async def get_downloads():
    """Retorna histórico de downloads ordenado com limite."""
    return download_manager.get_all_downloads()

@app.get("/api/downloads/active")
async def get_active_downloads():
    """Retorna downloads atualmente em andamento ou na fila para ressincronização da tela (A7)."""
    return download_manager.get_active_tasks_summary()

@app.post("/api/downloads/cancel-all")
async def cancel_all_downloads():
    cancelled_count = download_manager.cancel_all_downloads()
    return {"success": True, "cancelled_count": cancelled_count}

@app.post("/api/downloads/{task_id}/cancel")
async def cancel_download(task_id: str):
    success = download_manager.cancel_download(task_id)
    return {"success": success}

@app.delete("/api/downloads/{task_id}")
async def delete_download(task_id: str, delete_file: bool = Query(False)):
    success = download_manager.delete_download(task_id, delete_file=delete_file)
    return {"success": success}

@app.delete("/api/downloads/clear/all")
async def clear_all_downloads(delete_files: bool = Query(False)):
    """Cancela downloads ativos e limpa todo o histórico de downloads do banco de dados (A6)."""
    download_manager.cancel_all_downloads()

    if delete_files:
        with get_db_connection() as conn:
            rows = conn.execute("SELECT file_path FROM downloads WHERE file_path IS NOT NULL").fetchall()
            for r in rows:
                fp = r["file_path"]
                if fp and os.path.exists(fp):
                    try:
                        os.remove(fp)
                    except Exception:
                        pass

    from backend.db import execute_write
    execute_write("DELETE FROM downloads")
    download_manager.active_tasks.clear()
    return {"success": True, "cleared": True}

@app.post("/api/shutdown")
async def shutdown_system():
    """Recebe notificação de fechamento do navegador para desligar o servidor Python automaticamente (C2, A1)."""
    if len(ws_manager.active_connections) > 0:
        return {"status": "cancelled", "reason": "other_tabs_open"}
    if len(download_manager.active_tasks) > 0:
        return {"status": "delayed", "reason": "active_downloads"}
    logger.info("Recebida solicitação de encerramento do sistema.")
    ws_manager.schedule_shutdown(delay=3.0)
    return {"status": "shutting_down"}

@app.post("/api/downloads/{task_id}/open-folder")
async def open_download_folder(task_id: str):
    with get_db_connection() as conn:
        row = conn.execute("SELECT file_path FROM downloads WHERE id = ?", (task_id,)).fetchone()
        if not row or not row["file_path"]:
            raise HTTPException(status_code=404, detail="Arquivo não localizado no histórico.")

        file_path = os.path.normpath(row["file_path"])
        if os.path.exists(file_path):
            try:
                # Executa explorer em thread separada para não bloquear o event loop (M11)
                await asyncio.to_thread(subprocess.run, ["explorer", f"/select,{file_path}"], False)
                return {"success": True}
            except Exception as e:
                logger.error(f"Erro ao abrir explorer: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        else:
            parent_dir = os.path.dirname(file_path)
            if os.path.exists(parent_dir):
                await asyncio.to_thread(os.startfile, parent_dir)
                return {"success": True, "note": "Arquivo ausente, pasta aberta."}
            raise HTTPException(status_code=404, detail="Arquivo e pasta não encontrados.")

@app.post("/api/downloads/{task_id}/play")
async def play_download(task_id: str):
    with get_db_connection() as conn:
        row = conn.execute("SELECT file_path FROM downloads WHERE id = ?", (task_id,)).fetchone()
        if not row or not row["file_path"]:
            raise HTTPException(status_code=404, detail="Arquivo não encontrado no histórico.")

        file_path = os.path.normpath(row["file_path"])
        if os.path.exists(file_path):
            try:
                # Executa startfile em thread separada para não bloquear o event loop (M11)
                await asyncio.to_thread(os.startfile, file_path)
                return {"success": True}
            except Exception as e:
                logger.error(f"Erro ao reproduzir arquivo: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        else:
            raise HTTPException(status_code=404, detail="Arquivo físico não existe mais no disco.")

@app.get("/api/settings")
async def get_settings():
    return load_settings()

@app.post("/api/settings")
async def update_settings(payload: Dict[str, Any] = Body(...)):
    updated = save_settings(payload)
    return updated

@app.post("/api/select-folder")
async def select_folder_dialog(save_as_default: bool = Query(True)):
    """Abre diálogo nativo de pasta com trava para impedir instâncias duplicadas (B8) e respeita save_as_default (M10)."""
    if _folder_dialog_lock.locked():
        raise HTTPException(status_code=409, detail="Seletor de pasta já está aberto.")

    def _open_dialog():
        with _folder_dialog_lock:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            settings = load_settings()
            current_dir = settings.get("download_dir", "")
            selected = filedialog.askdirectory(
                initialdir=current_dir if (current_dir and os.path.exists(current_dir)) else None,
                title="Selecione a Pasta para Salvar os Downloads"
            )
            root.destroy()
            return selected

    try:
        chosen_dir = await asyncio.to_thread(_open_dialog)
        if chosen_dir:
            normalized = os.path.normpath(chosen_dir)
            if save_as_default:
                save_settings({"download_dir": normalized})
            return {"download_dir": normalized, "selected": True, "saved_as_default": save_as_default}
        return {"selected": False}
    except Exception as e:
        logger.error(f"Erro no seletor de pasta: {e}")
        return {"selected": False, "error": str(e)}

# Servir Frontend
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
