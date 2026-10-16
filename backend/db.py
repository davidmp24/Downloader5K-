# Downloader5K - Configurações e Modelos de Dados
import os
import sqlite3
import json
from pathlib import Path
from typing import Dict, Any, Optional

# Diretório padrão no Windows: C:\Users\<usuario>\Videos\Downloader5k
DEFAULT_DOWNLOAD_DIR = str(Path.home() / "Videos" / "Downloader5k")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "downloader.db")
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "settings.json")

import threading

_db_write_lock = threading.Lock()

def ensure_dirs():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(DEFAULT_DOWNLOAD_DIR, exist_ok=True)

def get_db_connection():
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH, timeout=60.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=60000;")
    return conn

def execute_write(query: str, params: tuple = ()):
    """Executa escritas de forma segura com lock para evitar database is locked em concorrência."""
    with _db_write_lock:
        with get_db_connection() as conn:
            conn.execute(query, params)
            conn.commit()

def init_db():
    ensure_dirs()
    with get_db_connection() as conn:
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
        conn.commit()

DEFAULT_SETTINGS = {
    "smart_mode": False,
    "download_dir": DEFAULT_DOWNLOAD_DIR,
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
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
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
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2, ensure_ascii=False)
    return current
