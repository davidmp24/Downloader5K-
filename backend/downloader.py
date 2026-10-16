# Downloader5K - Mecanismo de Extração e Download com yt-dlp e FFmpeg
import os
import sys
import uuid
import time
import math
import shutil
import logging
import threading
import sqlite3
from typing import Dict, Any, List, Optional, Callable
import yt_dlp

from backend.db import get_db_connection, load_settings, execute_write

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DownloaderCore")

def format_bytes(size: Optional[float]) -> str:
    if not size or size <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = int(math.floor(math.log(size, 1024)))
    p = math.pow(1024, i)
    s = round(size / p, 2)
    return f"{s} {units[i]}"

def format_seconds(seconds: Optional[float]) -> str:
    if not seconds or seconds < 0:
        return "--:--"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def get_base_ydl_opts(extra_opts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Retorna opções base do yt-dlp com bypass de bot (player_client) e cookies de navegador opcionais."""
    settings = load_settings()
    browser_cookies = settings.get("browser_cookies", "none")

    opts: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "web_creator", "mweb"]
            }
        }
    }

    if browser_cookies and browser_cookies != "none":
        try:
            opts["cookiesfrombrowser"] = (browser_cookies,)
        except Exception:
            pass

    if extra_opts:
        opts.update(extra_opts)
    return opts

class MediaInspector:
    """Extrai informações e formatos de URLs com alta precisão."""

    @staticmethod
    def inspect(url: str) -> Dict[str, Any]:
        # Verifica se o link contém parâmetro de playlist (ex: watch?v=...&list=PL... ou /playlist?list=PL...)
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        list_param = query.get("list", [None])[0]

        target_url = url
        # Se for um link de vídeo dentro de uma playlist, prioriza a extração da playlist completa
        if list_param and list_param != "WL" and "playlist" not in parsed.path:
            target_url = f"https://www.youtube.com/playlist?list={list_param}"

        ydl_opts = get_base_ydl_opts({
            "skip_download": True,
            "extract_flat": True,
            "noplaylist": False,
        })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(target_url, download=False)
            except Exception as e:
                # Se falhou ao buscar como playlist, tenta como vídeo único
                logger.warning(f"Tentativa de playlist falhou ({e}), tentando URL original: {url}")
                try:
                    info = ydl.extract_info(url, download=False)
                except Exception as inner_e:
                    logger.error(f"Erro ao inspecionar URL {url}: {inner_e}")
                    raise ValueError(f"Não foi possível processar o link: {str(inner_e)}")

        if not info:
            raise ValueError("Nenhuma informação encontrada para este link.")

        is_playlist = info.get("_type") == "playlist" or "entries" in info

        if is_playlist:
            raw_entries = info.get("entries") or []
            formatted_entries = []
            for idx, e in enumerate(raw_entries):
                if not e:
                    continue
                entry_id = e.get("id")
                entry_url = e.get("url") or (f"https://www.youtube.com/watch?v={entry_id}" if entry_id else "")
                entry_thumb = e.get("thumbnail")
                if not entry_thumb and entry_id:
                    entry_thumb = f"https://i.ytimg.com/vi/{entry_id}/hqdefault.jpg"

                formatted_entries.append({
                    "index": idx + 1,
                    "id": entry_id,
                    "title": e.get("title") or f"Vídeo #{idx + 1}",
                    "uploader": e.get("uploader") or info.get("uploader") or info.get("channel") or "YouTube",
                    "duration": e.get("duration", 0),
                    "duration_formatted": format_seconds(e.get("duration", 0)),
                    "thumbnail": entry_thumb,
                    "url": entry_url,
                })

            playlist_thumb = info.get("thumbnail")
            if not playlist_thumb and formatted_entries:
                playlist_thumb = formatted_entries[0]["thumbnail"]

            return {
                "is_playlist": True,
                "id": info.get("id") or list_param or "playlist",
                "title": info.get("title", "Playlist do YouTube"),
                "uploader": info.get("uploader") or info.get("channel") or "YouTube",
                "count": len(formatted_entries),
                "url": url,
                "thumbnail": playlist_thumb,
                "entries": formatted_entries,
            }

        # Extração de Formatos de Vídeo e Áudio
        formats = info.get("formats") or []
        video_resolutions = {}
        has_audio_stream = False

        for f in formats:
            # Verifica áudio
            if f.get("vcodec") == "none" and f.get("acodec") != "none":
                has_audio_stream = True

            height = f.get("height")
            if height and f.get("vcodec") != "none":
                fps = f.get("fps") or 30
                ext = f.get("ext") or "mp4"
                filesize = f.get("filesize") or f.get("filesize_approx") or 0

                # Normalização de rotulagem
                label = f"{height}p"
                if height >= 4320:
                    label = "4320p (8K Ultra HD)"
                elif height >= 2160:
                    label = "2160p (4K Ultra HD)"
                elif height >= 1440:
                    label = "1440p (2K QHD)"
                elif height >= 1080:
                    label = "1080p (Full HD)"
                elif height >= 720:
                    label = "720p (HD)"
                elif height >= 480:
                    label = "480p (SD)"
                elif height >= 360:
                    label = "360p"

                if fps and fps >= 50:
                    label += f" {int(fps)}fps"

                # Mantém a melhor taxa de bits por altura
                if height not in video_resolutions or (f.get("tbr") or 0) > video_resolutions[height].get("tbr", 0):
                    video_resolutions[height] = {
                        "height": height,
                        "label": label,
                        "fps": fps,
                        "ext": ext,
                        "filesize": filesize,
                        "filesize_formatted": format_bytes(filesize) if filesize else "Estimando...",
                        "tbr": f.get("tbr") or 0,
                        "vcodec": f.get("vcodec"),
                    }

        # Ordena resoluções do maior para o menor
        sorted_resolutions = sorted(video_resolutions.values(), key=lambda x: x["height"], reverse=True)

        # Formatos de áudio disponíveis para extração
        audio_options = [
            {"format": "mp3", "quality": "320", "label": "MP3 - Alta Fidelidade (320 kbps)", "lossless": False},
            {"format": "mp3", "quality": "256", "label": "MP3 - Muito Boa (256 kbps)", "lossless": False},
            {"format": "mp3", "quality": "192", "label": "MP3 - Padrão (192 kbps)", "lossless": False},
            {"format": "mp3", "quality": "128", "label": "MP3 - Compacta (128 kbps)", "lossless": False},
            {"format": "m4a", "quality": "0", "label": "M4A / AAC - Original do YouTube", "lossless": False},
            {"format": "flac", "quality": "0", "label": "FLAC - Lossless Studio Master", "lossless": True},
            {"format": "wav", "quality": "0", "label": "WAV - Sem Compressão", "lossless": True},
            {"format": "opus", "quality": "0", "label": "OPUS - Áudio Web de Alta Eficiência", "lossless": False},
        ]

        # Legendas
        subtitles = []
        raw_subs = info.get("subtitles") or {}
        raw_auto = info.get("automatic_captions") or {}

        for code in raw_subs.keys():
            subtitles.append({"lang": code, "type": "manual", "label": code.upper()})
        for code in raw_auto.keys():
            if not any(s["lang"] == code for s in subtitles):
                subtitles.append({"lang": code, "type": "auto", "label": f"{code.upper()} (Automática)"})

        return {
            "is_playlist": False,
            "id": info.get("id"),
            "title": info.get("title"),
            "uploader": info.get("uploader") or info.get("channel") or "Desconhecido",
            "duration": info.get("duration", 0),
            "duration_formatted": format_seconds(info.get("duration", 0)),
            "thumbnail": info.get("thumbnail"),
            "view_count": info.get("view_count", 0),
            "url": info.get("webpage_url") or url,
            "video_resolutions": sorted_resolutions,
            "audio_options": audio_options,
            "subtitles": subtitles[:20],  # Primeiras 20 línguas mais comuns
        }


class DownloadTask:
    """Representa e executa um download ativo com cancelamento e relatório em tempo real."""

    def __init__(
        self,
        task_id: str,
        url: str,
        title: str,
        thumbnail: str,
        download_type: str,  # 'video' ou 'audio'
        format_note: str,
        options: Dict[str, Any],
        broadcast_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.task_id = task_id
        self.url = url
        self.title = title
        self.thumbnail = thumbnail
        self.download_type = download_type
        self.format_note = format_note
        self.options = options
        self.broadcast_callback = broadcast_callback
        self.cancel_requested = False
        self.final_filepath = None
        self.final_size = 0
        self.thread: Optional[threading.Thread] = None
        self.last_db_time: float = 0.0
        self.semaphore: Optional[threading.Semaphore] = None

    def cancel(self):
        self.cancel_requested = True

    def _progress_hook(self, d: Dict[str, Any]):
        if self.cancel_requested:
            raise Exception("Download cancelado pelo usuário.")

        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            speed = d.get("speed") or 0
            eta = d.get("eta") or 0

            percent = 0.0
            if total > 0:
                percent = round((downloaded / total) * 100, 1)

            speed_str = f"{format_bytes(speed)}/s" if speed else ""
            eta_str = format_seconds(eta) if eta else ""

            self._update_state(
                status="downloading",
                progress=percent,
                speed=speed_str,
                eta=eta_str,
                file_size=total or downloaded,
            )
        elif status == "finished":
            self._update_state(
                status="processing",
                progress=99.0,
                speed="Multiplexando...",
                eta="Finalizando",
            )

    def _postprocessor_hook(self, d: Dict[str, Any]):
        if self.cancel_requested:
            raise Exception("Download cancelado pelo usuário.")

        pp = d.get("postprocessor", "")
        status = d.get("status", "")
        if status == "started":
            self._update_state(
                status="processing",
                progress=99.0,
                speed=f"FFmpeg ({pp})...",
                eta="Processando",
            )

    def _update_state(
        self,
        status: str,
        progress: float = 0.0,
        speed: str = "",
        eta: str = "",
        file_size: int = 0,
        error_message: Optional[str] = None,
    ):
        # 1. Notifica imediatamente o cliente Web via WebSocket
        if self.broadcast_callback:
            payload = {
                "type": "progress",
                "id": self.task_id,
                "status": status,
                "progress": progress,
                "speed": speed,
                "eta": eta,
                "file_size": file_size,
                "file_size_formatted": format_bytes(file_size),
                "file_path": self.final_filepath,
                "error_message": error_message,
            }
            self.broadcast_callback(payload)

        # 2. Atualiza o banco SQLite de forma controlada (apenas em eventos de estado ou a cada 1.5s)
        now = time.time()
        is_state_transition = status in ["completed", "cancelled", "error", "processing", "pending"]
        if is_state_transition or (now - self.last_db_time >= 1.5):
            self.last_db_time = now
            try:
                execute_write(
                    """
                    UPDATE downloads 
                    SET status = ?, progress = ?, speed = ?, eta = ?, 
                        file_size = CASE WHEN ? > 0 THEN ? ELSE file_size END,
                        file_path = COALESCE(?, file_path),
                        error_message = ?,
                        completed_at = CASE WHEN ? = 'completed' THEN CURRENT_TIMESTAMP ELSE completed_at END
                    WHERE id = ?
                    """,
                    (
                        status,
                        progress,
                        speed,
                        eta,
                        file_size,
                        file_size,
                        self.final_filepath,
                        error_message,
                        status,
                        self.task_id,
                    ),
                )
            except Exception as e:
                logger.warning(f"Aviso ao persistir status no SQLite ({self.task_id[:8]}): {e}")

    def run(self):
        """Executa a tarefa respeitando o limite de concorrência da fila semafórica."""
        if self.semaphore:
            self._update_state(status="pending", progress=0.0, speed="Aguardando vez na fila...", eta="--:--")
            with self.semaphore:
                if self.cancel_requested:
                    self._update_state(status="cancelled", progress=0.0, speed="Cancelado", eta="")
                    return
                self._execute_download()
        else:
            self._execute_download()

    def _execute_download(self):
        settings = load_settings()
        dest_dir = self.options.get("dest_dir") or settings.get("download_dir")
        os.makedirs(dest_dir, exist_ok=True)

        outtmpl = os.path.join(dest_dir, "%(title)s.%(ext)s")

        ydl_opts = get_base_ydl_opts({
            "outtmpl": outtmpl,
            "progress_hooks": [self._progress_hook],
            "postprocessor_hooks": [self._postprocessor_hook],
        })

        # Configuração do modo
        if self.download_type == "audio":
            audio_format = self.options.get("audio_format", "mp3")
            audio_quality = self.options.get("audio_quality", "320")

            postprocessors = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": audio_format,
                    "preferredquality": audio_quality,
                },
                {"key": "FFmpegMetadata", "add_metadata": True},
            ]

            # Incorporar thumbnail como capa de álbum para MP3 / M4A
            if audio_format in ["mp3", "m4a"]:
                ydl_opts["writethumbnail"] = True
                postprocessors.append({"key": "EmbedThumbnail"})

            ydl_opts.update(
                {
                    "format": "bestaudio/best",
                    "postprocessors": postprocessors,
                }
            )
        else:
            # Modo Vídeo (Smart Selection de faixas DASH 4K/1080p/720p com multiplexação)
            resolution = self.options.get("resolution", "1080")
            container = self.options.get("container", "mp4")
            embed_subs = self.options.get("embed_subtitles", True)

            # Formata regra de formato para melhor vídeo + melhor áudio
            if resolution and resolution != "best":
                format_rule = f"bestvideo[height<={resolution}]+bestaudio/best[height<={resolution}]/best"
            else:
                format_rule = "bestvideo+bestaudio/best"

            postprocessors = [
                {"key": "FFmpegMetadata", "add_metadata": True},
            ]

            # Inserção de capa no arquivo de vídeo se suportado
            ydl_opts["writethumbnail"] = True
            postprocessors.append({"key": "EmbedThumbnail"})

            ydl_opts.update(
                {
                    "format": format_rule,
                    "merge_output_format": container,
                    "postprocessors": postprocessors,
                }
            )

            if embed_subs:
                ydl_opts.update(
                    {
                        "writesubtitles": True,
                        "writeautomaticsub": True,
                        "subtitleslangs": ["pt", "en"],
                    }
                )
                postprocessors.append({"key": "FFmpegEmbedSubtitle"})

        self._update_state(status="downloading", progress=0.0, speed="Iniciando...", eta="--:--")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=True)
                if not info:
                    raise Exception("Falha ao baixar mídia.")

                # Determina o arquivo final gerado
                filename = ydl.prepare_filename(info)
                if self.download_type == "audio":
                    audio_fmt = self.options.get("audio_format", "mp3")
                    base, _ = os.path.splitext(filename)
                    filename = f"{base}.{audio_fmt}"
                else:
                    container = self.options.get("container", "mp4")
                    base, _ = os.path.splitext(filename)
                    filename = f"{base}.{container}"

                self.final_filepath = filename
                if os.path.exists(filename):
                    self.final_size = os.path.getsize(filename)

                self._update_state(
                    status="completed",
                    progress=100.0,
                    speed="Concluído",
                    eta="00:00",
                    file_size=self.final_size,
                )
                logger.info(f"Download {self.task_id} finalizado com sucesso: {filename}")

        except Exception as e:
            if self.cancel_requested:
                logger.info(f"Download {self.task_id} cancelado pelo usuário.")
                self._update_state(status="cancelled", progress=0.0, speed="Cancelado", eta="")
            else:
                err_msg = str(e)
                logger.error(f"Erro no download {self.task_id}: {err_msg}")
                self._update_state(
                    status="error",
                    progress=0.0,
                    speed="Falha",
                    eta="",
                    error_message=err_msg[:200],
                )


class DownloadManager:
    """Gerenciador de fila e orquestração de tarefas de download em segundo plano com limite de concorrência."""

    def __init__(self, max_concurrent_downloads: int = 3):
        self.active_tasks: Dict[str, DownloadTask] = {}
        self.broadcast_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self.semaphore = threading.Semaphore(max_concurrent_downloads)

    def set_broadcast_callback(self, callback: Callable[[Dict[str, Any]], None]):
        self.broadcast_callback = callback

    def create_download(
        self,
        url: str,
        title: str,
        author: str,
        thumbnail: str,
        duration: int,
        download_type: str,
        format_note: str,
        options: Dict[str, Any],
    ) -> str:
        task_id = str(uuid.uuid4())

        # Salva registro inicial no banco de dados SQLite com trava segura
        execute_write(
            """
            INSERT INTO downloads 
            (id, url, title, author, thumbnail, duration, type, format_note, status, progress)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', 0.0)
            """,
            (task_id, url, title, author, thumbnail, duration, download_type, format_note),
        )

        task = DownloadTask(
            task_id=task_id,
            url=url,
            title=title,
            thumbnail=thumbnail,
            download_type=download_type,
            format_note=format_note,
            options=options,
            broadcast_callback=self.broadcast_callback,
        )
        task.semaphore = self.semaphore

        self.active_tasks[task_id] = task

        thread = threading.Thread(target=task.run, daemon=True, name=f"Downloader-{task_id[:8]}")
        task.thread = thread
        thread.start()

        return task_id

    def cancel_download(self, task_id: str) -> bool:
        task = self.active_tasks.get(task_id)
        if task:
            task.cancel()
            return True
        return False

    def get_all_downloads(self) -> List[Dict[str, Any]]:
        with get_db_connection() as conn:
            rows = conn.execute("SELECT * FROM downloads ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]

    def delete_download(self, task_id: str, delete_file: bool = False) -> bool:
        with get_db_connection() as conn:
            row = conn.execute("SELECT file_path FROM downloads WHERE id = ?", (task_id,)).fetchone()
            if row and delete_file and row["file_path"]:
                try:
                    if os.path.exists(row["file_path"]):
                        os.remove(row["file_path"])
                except Exception as e:
                    logger.warning(f"Não foi possível remover arquivo {row['file_path']}: {e}")

        execute_write("DELETE FROM downloads WHERE id = ?", (task_id,))

        if task_id in self.active_tasks:
            del self.active_tasks[task_id]
        return True


download_manager = DownloadManager()
