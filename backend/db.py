# Downloader5K - Configurações e Modelos de Dados
import os
import shutil
import sqlite3
import json
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List
from contextlib import contextmanager

# Diretório de dados seguro fora do OneDrive (%LOCALAPPDATA%\Downloader5K\data)
APP_DATA_DIR = Path(os.getenv("LOCALAPPDATA", Path.home())) / "Downloader5K" / "data"
LEGACY_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = APP_DATA_DIR / "downloads.db"
SETTINGS_PATH = APP_DATA_DIR / "settings.json"
SETTINGS_FILE = SETTINGS_PATH  # compatibilidade com código existente

# Diretório padrão no Windows: C:\Users\<usuario>\Videos\Downloader5k
DEFAULT_DOWNLOAD_DIR = str(Path.home() / "Videos" / "Downloader5k")

_db_write_lock = threading.Lock()

def ensure_dirs():
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    os.makedirs(DEFAULT_DOWNLOAD_DIR, exist_ok=True)

@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def execute_write(query: str, params: tuple = ()):
    """Executa escritas de forma segura com lock para evitar database is locked em concorrência."""
    with _db_write_lock:
        with get_db_connection() as conn:
            conn.execute(query, params)

def create_downloads_batch(items: List[Dict[str, Any]]):
    """Insere múltiplos registros em lote usando executemany para evitar bloqueio do banco."""
    if not items:
        return
    query = """
        INSERT INTO downloads (
            id, url, title, author, thumbnail, duration, type, format_note,
            file_path, file_size, status, progress, speed, eta, error_message, created_at
        ) VALUES (
            :id, :url, :title, :author, :thumbnail, :duration, :type, :format_note,
            :file_path, :file_size, :status, :progress, :speed, :eta, :error_message, CURRENT_TIMESTAMP
        )
    """
    with _db_write_lock:
        with get_db_connection() as conn:
            conn.executemany(query, items)

def get_all_downloads(limit: int = 500) -> List[Dict[str, Any]]:
    """Retorna o histórico limitado para evitar sobrecarga."""
    with get_db_connection() as conn:
        rows = conn.execute("SELECT * FROM downloads ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

def reconcile_zombie_downloads():
    """Reconcilia registros interrompidos após queda/encerramento do servidor."""
    with _db_write_lock:
        with get_db_connection() as conn:
            conn.execute("""
                UPDATE downloads 
                SET status = 'error', 
                    error_message = 'Interrompido pelo encerramento inesperado do servidor'
                WHERE status IN ('pending', 'downloading', 'processing')
            """)

def init_db():
    ensure_dirs()

    # Migração automática única da pasta legada (OneDrive) para APP_DATA_DIR
    if not DB_PATH.exists():
        for old_db_name in ("downloader.db", "downloads.db"):
            old_db = LEGACY_DATA_DIR / old_db_name
            if old_db.exists():
                try:
                    shutil.copy2(old_db, DB_PATH)
                    break
                except Exception as e:
                    print(f"Erro ao migrar base legada {old_db}: {e}")

        old_settings = LEGACY_DATA_DIR / "settings.json"
        if old_settings.exists() and not SETTINGS_PATH.exists():
            try:
                shutil.copy2(old_settings, SETTINGS_PATH)
            except Exception as e:
                print(f"Erro ao migrar settings legado: {e}")

    # Inicialização da estrutura e PRAGMAs apenas no startup
    with get_db_connection() as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS downloads (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                title TEXT,
                author TEXT,
                thumbnail TEXT,
                duration INTEGER DEFAULT 0,
                type TEXT DEFAULT 'video',  -- 'video' ou 'audio'
                format_note TEXT,          -- ex: '1080p 60fps', 'MP3 320k'
                file_path TEXT,
                file_size INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending', -- 'pending', 'downloading', 'processing', 'completed', 'cancelled', 'error'
                progress REAL DEFAULT 0.0,
                speed TEXT DEFAULT '',
                eta TEXT DEFAULT '',
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)

    # Reconciliação de zumbis no startup
    reconcile_zombie_downloads()

DEFAULT_SETTINGS = {
    "smart_mode": False,
    "download_dir": DEFAULT_DOWNLOAD_DIR,
    "organize_by_genre": True,        # Organização inteligente em subpastas por gênero musical / categoria
    "default_type": "video",          # 'video' ou 'audio'
    "default_quality": "1080",        # '2160', '1440', '1080', '720', '480', 'best'
    "default_video_format": "mp4",    # 'mp4', 'mkv', 'webm'
    "default_audio_format": "mp3",    # 'mp3', 'm4a', 'flac', 'wav'
    "default_audio_bitrate": "320",   # '320', '256', '192', '128'
    "embed_subtitles": True,
    "subtitles_langs": "pt,en",
    "browser_cookies": "none"         # 'none', 'edge', 'chrome', 'brave', 'firefox'
}

def load_settings() -> Dict[str, Any]:
    ensure_dirs()
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                settings = dict(DEFAULT_SETTINGS)
                settings.update(saved)
                return settings
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)

def save_settings(new_settings: Dict[str, Any]) -> Dict[str, Any]:
    ensure_dirs()
    current = load_settings()
    current.update(new_settings)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2, ensure_ascii=False)
    return current
