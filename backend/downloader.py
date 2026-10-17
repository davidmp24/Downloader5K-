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

from backend.db import get_db_connection, load_settings, execute_write, get_all_downloads as db_get_all_downloads, create_downloads_batch

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DownloaderCore")

def format_bytes(size: Optional[float]) -> str:
    if not size or size <= 0:
        return "0 B"
    if size < 1:
        return f"{size:.2f} B"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    i = int(math.floor(math.log(size, 1024)))
    if i < 0:
        i = 0
    elif i >= len(units):
        i = len(units) - 1
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

import re

def sanitize_folder_name(name: str) -> str:
    r"""Remove caracteres inválidos para nomes de pastas no Windows (< > : " / \ | ? *)."""
    clean = re.sub(r'[<>:"/\\|?*]', '', name).strip()
    return clean or "Geral"

def classify_media_genre(info: Dict[str, Any]) -> str:
    """
    Identifica o gênero musical da banda ou categoria do vídeo com base em metadados ricos:
    - genre
    - tags
    - categories
    - artist / creator / channel
    - title e description
    """
    if not info:
        return "Geral"

    # 1. Verifica se já existe um gênero explícito de alta fidelidade
    raw_genre = info.get("genre")
    if raw_genre and isinstance(raw_genre, str) and len(raw_genre.strip()) > 1:
        return sanitize_folder_name(raw_genre.title())

    # Agrega apenas metadados de alta relevância (título, canal, artista e tags) evitando poluição de descrições (M1)
    title = (info.get("title") or "").lower()
    uploader = (info.get("uploader") or info.get("channel") or info.get("creator") or "").lower()
    artist = (info.get("artist") or "").lower()
    tags = [t.lower() for t in (info.get("tags") or []) if isinstance(t, str)]
    categories = [c.lower() for c in (info.get("categories") or []) if isinstance(c, str)]

    primary_text = f"{title} {uploader} {artist} {' '.join(tags)}"

    GENRE_RULES = [
        # Gêneros Musicais
        (
            "Rock & Metal",
            [
                "heavy metal", "thrash metal", "death metal", "black metal", "power metal",
                "hard rock", "punk rock", "pop punk", "grunge", "indie rock", "alt rock",
                "classic rock", "rock and roll", "rock nacional", "metallica", "iron maiden",
                "ac/dc", "acdc", "guns n roses", "guns n' roses", "queen", "pink floyd",
                "led zeppelin", "black sabbath", "deep purple", "scorpions", "bon jovi",
                "aerosmith", "nirvana", "pearl jam", "soundgarden", "alice in chains",
                "linkin park", "slipknot", "system of a down", "rammstein", "foo fighters",
                "red hot chili peppers", "green day", "blink-182", "offspring", "banda kiss", "kiss band",
                "judas priest", "megadeth", "slayer", "pantera", "motörhead", "motorhead",
                "sepultura", "angra", "shaman", "legião urbana", "capital inicial", "titãs",
                "charlie brown jr", "cazuza", "barão vermelho", "paralamas", "engenheiros do hawaii",
                "skank", "pitty", "cpm 22", "raimundos", "detonautas", "ira!", "biquini cavadão",
                "rock clássico", "rock nacional"
            ]
        ),
        (
            "Sertanejo",
            [
                "sertanejo", "sertanejo universitario", "modão", "sofrência",
                "marília mendonça", "marilia mendonca", "jorge & mateus", "jorge e mateus",
                "henrique & juliano", "henrique e juliano", "gusttavo lima", "zé neto e cristiano",
                "ze neto e cristiano", "maiara e maraisa", "luan santana", "ana castela",
                "hugo e guilherme", "matheus e kauan", "guilherme e benuto", "clayton e romário",
                "israel e rodolffo", "diego e victor hugo", "chitãozinho e xororó", "chitaozinho",
                "bruno e marrone", "zeze di camargo", "leandro e leonardo", "leandro & leonardo",
                "cantor leonardo", "eduardo costa", "joão mineiro", "tião carreiro", "tiao carreiro",
                "simone mendes", "lauana prado", "murilo huff", "felipe araújo", "trio parada dura"
            ]
        ),
        (
            "Pagode & Samba",
            [
                "pagode", "samba", "partido alto", "roda de samba", "pagodão",
                "thiaguinho", "ferrugem", "sorriso maroto", "menos é mais", "dilsinho",
                "turma do pagode", "mumuzinho", "péricles", "pericles", "zeca pagodinho",
                "alcione", "beth carvalho", "revelação", "exaltasamba", "belo", "pixote",
                "fundo de quintal", "jorge aragão", "diogo nogueira", "art popular",
                "molejo", "soweto", "raça negra", "grupomenosémais", "kamisa 10"
            ]
        ),
        (
            "Hip-Hop & Rap",
            [
                "hip hop", "hip-hop", "rap", "trap", "boom bap", "drill", "r&b", "rnb",
                "eminem", "2pac", "tupac", "notorious b.i.g.", "snoop dogg", "50 cent",
                "dr. dre", "kendrick lamar", "drake", "travis scott", "kanye west",
                "post malone", "j. cole", "future", "lil wayne", "jay-z",
                "racionais", "racionais mc's", "sabotage", "emicida", "criolo", "djonga",
                "filipe ret", "matuê", "matue", "tz da coronel", "kayblack", "veigh",
                "bk'", "orochi", "l7nnon", "poze do rodo", "major rd", "teto", "wiu",
                "cabelinho", "conecrew", "tribo da periferia", "hungria hip hop"
            ]
        ),
        (
            "Eletrônica & Dance",
            [
                "electronic", "eletrônica", "eletronica", "edm", "house music", "deep house",
                "techno", "trance", "dubstep", "drum and bass", "dnb", "synthwave", "psytrance",
                "alok", "vintage culture", "david guetta", "avicii", "tiësto", "tiesto",
                "calvin harris", "martin garrix", "daft punk", "marshmello", "swedish house mafia",
                "armin van buuren", "deadmau5", "skrillex", "cat dealers", "dubdogz",
                "hardstyle", "electro", "future bass"
            ]
        ),
        (
            "Funk",
            [
                "funk", "funk rj", "funk sp", "mandelão", "funk consciente", "brega funk",
                "funk melody", "mc ryan", "mc hariel", "mc daniel", "mc paiva", "mc ig",
                "dennis dj", "kondzilla", "gr6", "mc livinho", "mc pedrinho", "mc kevin",
                "mc poze", "mc pipokinha", "mc cabelinho", "dj gbr", "dj arana"
            ]
        ),
        (
            "Pop",
            [
                "pop music", "dance pop", "synthpop", "electropop", "k-pop", "kpop", "j-pop",
                "taylor swift", "michael jackson", "bruno mars", "dua lipa", "madonna",
                "katy perry", "rihanna", "ariana grande", "lady gaga", "billie eilish",
                "justin bieber", "ed sheeran", "shakira", "beyoncé", "beyonce", "britney spears",
                "selena gomez", "miley cyrus", "the weeknd", "harry styles", "olivia rodrigo",
                "anitta", "ludmilla", "luísa sonza", "gloria groove", "pabllo vittar", "iza",
                "jão", "vitão", "melim", "tiago iorc", "maroon 5", "coldplay", "imagine dragons",
                "bts", "blackpink", "twice", "pop"
            ]
        ),
        (
            "Forró & Piseiro",
            [
                "forró", "forro", "piseiro", "pisadinha", "baião", "xote", "arrasta-pé",
                "joão gomes", "joao gomes", "tarcísio do acordeon", "wesley safadão",
                "barões da pisadinha", "baroes da pisadinha", "mari fernandez", "xand avião",
                "calcinha preta", "mastruz com leite", "luiz gonzaga", "dominguinhos",
                "dorgival dantas", "flávio josé", "limão com mel", "magníficos"
            ]
        ),
        (
            "MPB & Bossa Nova",
            [
                "mpb", "bossa nova", "tropicália", "caetano veloso", "gilberto gil",
                "chico buarque", "tom jobim", "vinicius de moraes", "joão gilberto",
                "elis regina", "gal costa", "milton nascimento", "djavan", "maria bethânia",
                "marisa monte", "seu jorge", "tim maia", "jorge ben jor", "alceu valença",
                "geraldo azevedo", "zé ramalho", "belchior", "lenine", "maria gadú"
            ]
        ),
        (
            "Gospel & Religioso",
            [
                "gospel", "louvor", "adoração", "worship", "cristã", "cristão", "evangélica",
                "aline barros", "fernandinho", "gabriela rocha", "isadora pompeo", "midian lima",
                "anderson freire", "damares", "bruna karla", "padre marcelo", "padre fábio",
                "morada", "preto no branco", "diante do trono", "hillsong", "bethel music",
                "elevation worship", "thalles roberto", "cassiane", "eyshila"
            ]
        ),
        (
            "Reggae",
            [
                "reggae", "dub", "ska", "roots reggae", "dancehall", "bob marley",
                "soja", "natiruts", "maneva", "planta e raiz", "armandinho", "tribo de jah",
                "ziggy marley", "peter tosh", "ub40", "damian marley", "ponto de equilíbrio"
            ]
        ),
        (
            "Jazz & Blues",
            [
                "jazz", "blues", "smooth jazz", "miles davis", "john coltrane",
                "louis armstrong", "b.b. king", "bb king", "eric clapton", "stevie wonder",
                "ray charles", "aretha franklin", "amy winehouse", "norah jones", "nina simone",
                "ella fitzgerald", "chet baker", "billie holiday", "muddy waters"
            ]
        ),
        (
            "Clássica & Instrumental",
            [
                "classical", "clássica", "classica", "orchestra", "orquestra", "symphony",
                "sinfonia", "piano solo", "violin", "acoustic instrumental", "soundtrack",
                "trilha sonora", "ost", "beethoven", "mozart", "bach", "chopin", "vivaldi",
                "tchaikovsky", "hans zimmer", "john williams", "ennio morricone", "ludovico einaudi",
                "instrumental"
            ]
        ),
        (
            "Lo-Fi & Relax",
            [
                "lofi", "lo-fi", "chillhop", "chill beats", "study beats", "relaxing beats",
                "ambient music", "sleep beats", "lo-fi hip hop"
            ]
        ),
        # Categorias de Vídeos Gerais
        (
            "Podcasts & Entrevistas",
            [
                "podcast", "podcasts", "entrevista", "talk show", "cortes podcast",
                "flow podcast", "podpah", "inteligencia ltda", "venus podcast", "ironberg podcast",
                "ticaracaticast", "monark", "poddelas", "cortes do flow"
            ]
        ),
        (
            "Games",
            [
                "gameplay", "gaming", "games", "jogos", "walkthrough", "playthrough",
                "minecraft", "roblox", "gta", "fortnite", "league of legends", "valorant",
                "free fire", "counter-strike", "cs:go", "cs2", "playstation", "xbox", "nintendo"
            ]
        ),
        (
            "Tutoriais & Educação",
            [
                "tutorial", "curso", "aula", "education", "como fazer", "passo a passo",
                "dicas de", "aprenda a", "programação", "desenvolvimento web", "python tutorial"
            ]
        ),
        (
            "Tecnologia",
            [
                "tecnologia", "tecnologia e ciência", "smartphone", "unboxing", "review tech",
                "hardware", "apple", "samsung", "xiaomi", "computador gamer", "inteligência artificial"
            ]
        ),
        (
            "Filmes & Trailers",
            [
                "trailer", "teaser oficial", "filme completo", "cena de filme", "cinema",
                "movie trailer", "curta metragem"
            ]
        ),
        (
            "Esportes",
            [
                "futebol", "gols da rodada", "melhores momentos", "brasileirão", "champions league",
                "ufc", "combate", "basquete", "nba", "fórmula 1", "f1", "esportes"
            ]
        ),
        (
            "Comédia & Humor",
            [
                "comédia", "stand up", "stand-up comedy", "humor", "pegadinha",
                "comediante", "piadas", "esquetes"
            ]
        )
    ]

    for genre_name, keywords in GENRE_RULES:
        for kw in keywords:
            # (?<!\w) e (?!\w) garantem limites de palavra mesmo com símbolos como ' ou ! (M2)
            pattern = rf"(?<!\w){re.escape(kw)}(?!\w)"
            if re.search(pattern, primary_text):
                return sanitize_folder_name(genre_name)

    # 3. Categorias padrão da plataforma
    for cat in categories:
        if "music" in cat:
            return "Músicas"
        elif "gaming" in cat or "jogos" in cat:
            return "Games"
        elif "education" in cat or "educação" in cat:
            return "Educação"
        elif "tech" in cat or "tecnologia" in cat:
            return "Tecnologia"
        elif "comedy" in cat or "comédia" in cat:
            return "Comédia"
        elif "sports" in cat or "esportes" in cat:
            return "Esportes"
        elif "film" in cat or "animation" in cat:
            return "Filmes & Animação"
        elif "news" in cat or "notícias" in cat:
            return "Notícias"

    return "Geral"

def get_base_ydl_opts(extra_opts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Retorna opções base do yt-dlp sem cap de qualidade e com cookies de navegador opcionais."""
    settings = load_settings()
    browser_cookies = settings.get("browser_cookies", "none")

    opts: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
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
        # Verifica se o link contém parâmetro de playlist ou é canal/aba de vídeos
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        list_param = query.get("list", [None])[0]

        target_url = url
        is_channel_or_playlist = bool(list_param and list_param != "WL") or "playlist" in parsed.path or any(
            seg in parsed.path for seg in ["/@", "/channel/", "/c/", "/user/"]
        )

        # Se for um link de vídeo dentro de uma playlist, prioriza a extração da playlist completa
        if list_param and list_param != "WL" and "playlist" not in parsed.path:
            target_url = f"https://www.youtube.com/playlist?list={list_param}"

        ydl_opts = get_base_ydl_opts({
            "skip_download": True,
            "extract_flat": True if is_channel_or_playlist else False,
            "noplaylist": False if is_channel_or_playlist else True,
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

        # Rejeitar transmissões ao vivo em andamento
        if info.get("is_live") or info.get("live_status") == "is_live":
            raise ValueError("Transmissões ao vivo (live streams) em andamento não podem ser baixadas.")

        is_playlist = info.get("_type") == "playlist" or "entries" in info

        if is_playlist:
            raw_entries = info.get("entries") or []
            if not isinstance(raw_entries, list):
                raw_entries = list(raw_entries)

            formatted_entries = []
            for idx, e in enumerate(raw_entries):
                if not e:
                    continue
                entry_title = e.get("title") or ""
                # Filtrar vídeos excluídos, privados ou indisponíveis
                if entry_title in ("[Private video]", "[Deleted video]") or e.get("availability") in ("private", "needs_auth"):
                    continue

                entry_id = e.get("id")
                entry_url = e.get("url") or (f"https://www.youtube.com/watch?v={entry_id}" if entry_id else "")
                entry_thumb = e.get("thumbnail")
                if not entry_thumb and entry_id:
                    entry_thumb = f"https://i.ytimg.com/vi/{entry_id}/hqdefault.jpg"

                formatted_entries.append({
                    "index": len(formatted_entries) + 1,
                    "id": entry_id,
                    "title": entry_title or f"Vídeo #{len(formatted_entries) + 1}",
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
        manager: Optional["DownloadManager"] = None,
    ):
        self.task_id = task_id
        self.url = url
        self.title = title
        self.thumbnail = thumbnail
        self.download_type = download_type
        self.format_note = format_note
        self.options = options
        self.broadcast_callback = broadcast_callback
        self.manager = manager
        self.cancel_requested = False
        self.final_filepath: Optional[str] = None
        self.final_size: int = 0
        self.thread: Optional[threading.Thread] = None
        self.last_db_time: float = 0.0
        self.last_broadcast_time: float = 0.0
        self.current_progress: float = 0.0
        self.status: str = "pending"
        self.semaphore: Optional[threading.Semaphore] = None
        self.target_dir: Optional[str] = None

    def cancel(self):
        self.cancel_requested = True
        if self.target_dir:
            self._cleanup_temp_files(self.target_dir)

    def _cleanup_temp_files(self, directory: str):
        """Remove arquivos temporários .part ou .ytdl deixados por download cancelado."""
        try:
            if not directory or not os.path.exists(directory):
                return
            for fname in os.listdir(directory):
                if fname.endswith((".part", ".ytdl")) and (self.task_id[:8] in fname or (self.title and self.title[:20] in fname)):
                    try:
                        os.remove(os.path.join(directory, fname))
                    except Exception:
                        pass
        except Exception:
            pass

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

            # Evita recuo abrupto de progresso caso o áudio DASH esteja sendo baixado após o vídeo
            if percent > self.current_progress or self.current_progress >= 99.0:
                self.current_progress = percent

            speed_str = f"{format_bytes(speed)}/s" if speed else ""
            eta_str = format_seconds(eta) if eta else ""

            self._update_state(
                status="downloading",
                progress=self.current_progress,
                speed=speed_str,
                eta=eta_str,
                file_size=total or downloaded,
            )
        elif status == "finished":
            # Transição suave para processamento/multiplexação
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
        elif status == "finished":
            # Captura caminho pós-processado se fornecido
            info = d.get("info_dict")
            if info and "filepath" in info:
                self.final_filepath = info["filepath"]

    def _update_state(
        self,
        status: str,
        progress: float = 0.0,
        speed: str = "",
        eta: str = "",
        file_size: int = 0,
        error_message: Optional[str] = None,
    ):
        self.status = status
        now = time.time()
        is_state_transition = status in ["completed", "cancelled", "error", "processing", "pending"]

        # Throttle WebSocket (B7): no máximo 1 broadcast a cada 250ms por tarefa, salvo em transições de estado
        if self.broadcast_callback and (is_state_transition or (now - self.last_broadcast_time >= 0.25)):
            self.last_broadcast_time = now
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
            try:
                self.broadcast_callback(payload)
            except Exception as e:
                logger.warning(f"Erro no broadcast callback: {e}")

        # Atualiza o banco SQLite de forma controlada
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
        try:
            if self.cancel_requested:
                self._update_state(status="cancelled", progress=0.0, speed="Cancelado", eta="")
                return

            if self.semaphore:
                self._update_state(status="pending", progress=0.0, speed="Aguardando vez na fila...", eta="--:--")
                with self.semaphore:
                    if self.cancel_requested:
                        self._update_state(status="cancelled", progress=0.0, speed="Cancelado", eta="")
                        return
                    self._execute_download()
            else:
                self._execute_download()
        finally:
            if self.manager:
                self.manager.on_task_finished(self.task_id)

    def _execute_download(self):
        try:
            settings = load_settings()
            dest_dir = self.options.get("dest_dir") or settings.get("download_dir") or DEFAULT_DOWNLOAD_DIR
            dest_dir = os.path.normpath(dest_dir)
            self.target_dir = dest_dir

            organize_by_genre = self.options.get("organize_by_genre", settings.get("organize_by_genre", False))

            if organize_by_genre:
                try:
                    inspect_opts = get_base_ydl_opts({"skip_download": True})
                    with yt_dlp.YoutubeDL(inspect_opts) as meta_ydl:
                        meta_info = meta_ydl.extract_info(self.url, download=False)
                        if meta_info:
                            genre = classify_media_genre(meta_info)
                            dest_dir = os.path.join(dest_dir, genre)
                            self.target_dir = dest_dir
                            logger.info(f"Mídia '{self.title}' classificada no gênero/pasta: [{genre}]")
                except Exception as e:
                    logger.warning(f"Não foi possível classificar gênero previamente ({self.task_id[:8]}): {e}")

            os.makedirs(dest_dir, exist_ok=True)

            # Prevenção de colisão de nomes com ID do vídeo (M5)
            outtmpl = os.path.join(dest_dir, "%(title).150s [%(id)s].%(ext)s")

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

                embed_cover = self.options.get("embed_cover", True)
                if embed_cover and audio_format.lower() in ["mp3", "m4a", "flac"]:
                    ydl_opts["writethumbnail"] = True
                    postprocessors.append({"key": "EmbedThumbnail"})

                ydl_opts.update(
                    {
                        "format": "bestaudio/best",
                        "postprocessors": postprocessors,
                    }
                )
            else:
                resolution = self.options.get("resolution", "1080")
                container = self.options.get("container", "mp4").lower()
                embed_subs = self.options.get("embed_subtitles", True)
                subtitles_langs = self.options.get("subtitles_langs", settings.get("subtitles_langs", "pt,en"))
                embed_cover = self.options.get("embed_cover", True)

                if resolution and resolution != "best":
                    format_rule = f"bestvideo[height<={resolution}]+bestaudio/best[height<={resolution}]/best"
                else:
                    format_rule = "bestvideo+bestaudio/best"

                postprocessors = [
                    {"key": "FFmpegMetadata", "add_metadata": True},
                ]

                supported_video_cover_containers = {"mp4", "mkv", "mov", "m4v"}
                if embed_cover and container in supported_video_cover_containers:
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
                    langs_list = [lang.strip() for lang in subtitles_langs.split(",") if lang.strip()]
                    ydl_opts.update(
                        {
                            "writesubtitles": True,
                            "writeautomaticsub": True,
                            "subtitleslangs": langs_list or ["pt", "en"],
                        }
                    )
                    postprocessors.append({"key": "FFmpegEmbedSubtitle"})

            self._update_state(status="downloading", progress=0.0, speed="Iniciando...", eta="--:--")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=True)
                if not info:
                    raise Exception("Falha ao baixar mídia.")

                # Determina o arquivo final gerado com precisão (M4)
                real_filepath = None
                if "requested_downloads" in info and info["requested_downloads"]:
                    for req in info["requested_downloads"]:
                        fp = req.get("filepath")
                        if fp and os.path.exists(fp):
                            real_filepath = fp
                            break

                if not real_filepath:
                    # Fallback via prepare_filename
                    prep = ydl.prepare_filename(info)
                    base, _ = os.path.splitext(prep)
                    ext = self.options.get("audio_format", "mp3") if self.download_type == "audio" else self.options.get("container", "mp4")
                    candidate = f"{base}.{ext}"
                    if os.path.exists(candidate):
                        real_filepath = candidate
                    elif os.path.exists(prep):
                        real_filepath = prep

                if real_filepath and os.path.exists(real_filepath):
                    self.final_filepath = os.path.normpath(real_filepath)
                    self.final_size = os.path.getsize(self.final_filepath)
                else:
                    raise Exception("O arquivo não foi localizado no disco após a conclusão do download.")

                self._update_state(
                    status="completed",
                    progress=100.0,
                    speed="Concluído",
                    eta="00:00",
                    file_size=self.final_size,
                )
                logger.info(f"Download {self.task_id} finalizado com sucesso: {self.final_filepath}")

        except Exception as e:
            if self.cancel_requested:
                logger.info(f"Download {self.task_id} cancelado pelo usuário.")
                if self.target_dir:
                    self._cleanup_temp_files(self.target_dir)
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
        self._lock = threading.Lock()

    def set_broadcast_callback(self, callback: Callable[[Dict[str, Any]], None]):
        self.broadcast_callback = callback

    def on_task_finished(self, task_id: str):
        """Remove a tarefa concluída/falhada da memória para evitar vazamento (M8)."""
        with self._lock:
            self.active_tasks.pop(task_id, None)

    def get_active_tasks_summary(self) -> List[Dict[str, Any]]:
        """Retorna resumo das tarefas atualmente ativas para ressincronização no frontend (A7)."""
        with self._lock:
            tasks = list(self.active_tasks.values())
        return [
            {
                "id": t.task_id,
                "url": t.url,
                "title": t.title,
                "thumbnail": t.thumbnail,
                "type": t.download_type,
                "format_note": t.format_note,
                "status": t.status,
                "progress": t.current_progress,
            }
            for t in tasks
        ]

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
            manager=self,
        )
        task.semaphore = self.semaphore

        with self._lock:
            self.active_tasks[task_id] = task

        thread = threading.Thread(target=task.run, daemon=True, name=f"Downloader-{task_id[:8]}")
        task.thread = thread
        thread.start()

        return task_id

    def cancel_download(self, task_id: str) -> bool:
        with self._lock:
            task = self.active_tasks.get(task_id)
        if task:
            task.cancel()
            return True
        return False

    def cancel_all_downloads(self) -> int:
        """Cancela todos os downloads ativos e enfileirados de uma só vez."""
        with self._lock:
            tasks = list(self.active_tasks.values())
        count = 0
        for task in tasks:
            try:
                task.cancel()
                count += 1
            except Exception as e:
                logger.warning(f"Erro ao cancelar tarefa {task.task_id}: {e}")
        return count

    def get_all_downloads(self, limit: int = 500) -> List[Dict[str, Any]]:
        return db_get_all_downloads(limit=limit)

    def delete_download(self, task_id: str, delete_file: bool = False) -> bool:
        # Cancela tarefa se ainda estiver ativa (A6)
        with self._lock:
            task = self.active_tasks.get(task_id)
        if task:
            task.cancel()

        with get_db_connection() as conn:
            row = conn.execute("SELECT file_path FROM downloads WHERE id = ?", (task_id,)).fetchone()
            if row and delete_file and row["file_path"]:
                try:
                    if os.path.exists(row["file_path"]):
                        os.remove(row["file_path"])
                except Exception as e:
                    logger.warning(f"Não foi possível remover arquivo {row['file_path']}: {e}")

        execute_write("DELETE FROM downloads WHERE id = ?", (task_id,))

        with self._lock:
            self.active_tasks.pop(task_id, None)
        return True


download_manager = DownloadManager()
