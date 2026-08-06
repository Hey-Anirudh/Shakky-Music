# api/ytdlp.py
# yt-dlp wrapper: search, metadata, direct-stream URL resolution, downloads,
# and playlists. Blocking YoutubeDL calls are pushed onto a thread pool so a
# slow extract never blocks FastAPI's event loop.

import asyncio
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

import yt_dlp

from . import config

LOGGER = logging.getLogger("api.ytdlp")

_executor = ThreadPoolExecutor(
    max_workers=config.YTDLP_CONCURRENCY, thread_name_prefix="ytdlp"
)

_meta_cache = {}    # vidid -> {ts, data}
_stream_cache = {}  # vidid -> {ts, data}


# ---------------------------------------------------------------------------
def _base_opts(**overrides):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "no_color": True,
        "noplaylist": False,
        "nocheckcertificate": True,
        "socket_timeout": config.YTDLP_TIMEOUT,
        "retries": config.YTDLP_RETRIES,
        "fragment_retries": config.YTDLP_RETRIES,
        "logger": LOGGER,
        "format": "bestaudio/best",
    }
    if config.COOKIES_FILE:
        opts["cookiefile"] = config.COOKIES_FILE
    elif os.getenv("YTDLP_BROWSER_COOKIES"):
        opts["cookiesfrombrowser"] = os.getenv("YTDLP_BROWSER_COOKIES")
    opts.update(overrides)
    return opts


def _seconds_to_minsec(sec):
    try:
        sec = int(float(sec))
    except (TypeError, ValueError):
        return "0:00"
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _extract_id(url_or_id):
    if not url_or_id:
        return ""
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})", str(url_or_id))
    if m:
        return m.group(1)
    return str(url_or_id).strip()


def _thumb(entry, vid):
    for t in entry.get("thumbnails") or []:
        if t.get("url"):
            return t["url"]
    return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"


def _run(call, *a, **k):
    loop = asyncio.get_running_loop()
    return loop.run_in_executor(_executor, call, *a, **k)


def _extract_info(url):
    """Blocking extract (slimmed) — always call via _run() from async code."""
    with yt_dlp.YoutubeDL(_base_opts()) as ydl:
        return ydl.extract_info(url, download=False) or {}


def _slim(fmt):
    return {
        "format_id": fmt.get("format_id"),
        "ext": fmt.get("ext"),
        "vcodec": fmt.get("vcodec"),
        "acodec": fmt.get("acodec"),
        "height": fmt.get("height"),
        "width": fmt.get("width"),
        "fps": fmt.get("fps"),
        "abr": fmt.get("abr"),
        "filesize": fmt.get("filesize"),
        "filesize_approx": fmt.get("filesize_approx"),
        "url": fmt.get("url"),
    }


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
def _do_search(query, limit):
    limit = max(1, min(int(limit or 12), 50))
    opts = _base_opts(extract_flat="in_playlist")
    with yt_dlp.YoutubeDL(opts) as ydl:
        data = ydl.extract_info(f"ytsearch{limit}:{query}", download=False) or {}

    results = []
    for e in data.get("entries") or []:
        if not e or not e.get("id"):
            continue
        results.append({
            "vidid": e["id"],
            "title": e.get("title", "Unknown"),
            "url": e.get("url", f"https://youtu.be/{e['id']}"),
            "duration": _seconds_to_minsec(e.get("duration")),
            "duration_sec": int(e.get("duration") or 0),
            "thumbnail": _thumb(e, e["id"]),
            "uploader": e.get("channel") or e.get("uploader") or "Unknown",
            "views": e.get("view_count") or 0,
        })
    return results


async def search(query, limit=12):
    return await _run(_do_search, query, limit)


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------
def _do_metadata(url_or_id):
    vid = _extract_id(url_or_id)
    cached = _meta_cache.get(vid)
    if cached and (time.time() - cached["ts"]) < config.METADATA_TTL:
        return cached["data"]

    info = _extract_info(url_or_id)
    data = {
        "vid": info.get("id") or vid,
        "title": info.get("title", "Unknown"),
        "url": f"https://youtu.be/{info.get('id') or vid}",
        "duration": _seconds_to_minsec(info.get("duration")),
        "duration_sec": int(info.get("duration") or 0),
        "thumbnail": _thumb(info, vid),
        "thumbs": [t.get("url") for t in (info.get("thumbnails") or []) if t.get("url")][:5],
        "uploader": info.get("channel") or info.get("uploader") or "Unknown",
        "views": info.get("view_count") or 0,
        "live": bool(info.get("is_live") or False),
        "formats": [_slim(f) for f in (info.get("formats") or [])],
    }
    _meta_cache[vid] = {"ts": time.time(), "data": data}
    return data


async def metadata(url_or_id):
    return await _run(_do_metadata, url_or_id)


# ---------------------------------------------------------------------------
# Stream-first direct URL
# ---------------------------------------------------------------------------
def _pick_stream(fmts):
    auds = [
        f for f in fmts
        if (f.get("acodec") and f.get("acodec") != "none")
        and (not f.get("vcodec") or f.get("vcodec") == "none")
    ]
    if not auds:
        return None
    return max(auds, key=lambda f: (f.get("ext") == "m4a", f.get("abr") or 0))


def _do_stream(url_or_id):
    vid = _extract_id(url_or_id)
    cached = _stream_cache.get(vid)
    if cached and (time.time() - cached["ts"]) < config.STREAM_URL_TTL:
        return cached["data"]

    info = _extract_info(url_or_id)
    chosen = _pick_stream(info.get("formats") or [])
    if chosen and chosen.get("url"):
        url, ext = chosen["url"], chosen.get("ext") or "m4a"
    else:
        url, ext = info.get("url"), info.get("ext") or "m4a"

    data = {
        "vid": info.get("id") or vid,
        "url": url,
        "ext": ext,
        "headers": dict(info.get("http_headers") or {}),
    }
    _stream_cache[data["vid"]] = {"ts": time.time(), "data": data}
    return data


async def stream(url_or_id):
    return await _run(_do_stream, url_or_id)


# ---------------------------------------------------------------------------
# Download to disk
# ---------------------------------------------------------------------------
def _do_download(url_or_id, outformat="m4a", video=False, quality=None, maxsize_mb=None):
    vid = _extract_id(url_or_id)
    if not vid:
        raise ValueError("Could not parse a video id from the input.")

    opts = _base_opts(
        outtmpl=os.path.join(config.DOWNLOADS_DIR, "%(id)s.%(ext)s"),
        noplaylist=True,
        format="bestaudio/best" if not video else "bestvideo+bestaudio/best",
    )
    if video and quality:
        opts["format"] = f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best"

    post = [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": outformat,
        "preferredquality": "192",
    }]
    if outformat in ("native", "auto", ""):
        post = None
    opts["postprocessors"] = post

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url_or_id, download=True) or {}
        title = info.get("title", vid)

    path = _find_output(vid, outformat)
    return path, _ext_of(path), title


def _find_output(vid, outformat):
    """Locate the produced file under DOWNLOADS_DIR (handles postprocessor renames)."""
    from fnmatch import fnmatch
    if os.path.isdir(config.DOWNLOADS_DIR):
        for f in os.listdir(config.DOWNLOADS_DIR):
            if f.startswith(vid + "."):
                base, ext = os.path.splitext(f)
                if ext and base == vid:
                    return os.path.join(config.DOWNLOADS_DIR, f)
    # fallback guesses
    for ext in (outformat, "m4a", "mp3", "webm", "opus"):
        p = os.path.join(config.DOWNLOADS_DIR, f"{vid}.{ext}")
        if os.path.isfile(p):
            return p
    return None


async def download(url_or_id, outformat="m4a", video=False, quality=None, max_=None):
    return await _run(_do_download, url_or_id, outformat, bool(video), quality, max_)


# ---------------------------------------------------------------------------
# Playlist
# ---------------------------------------------------------------------------
def _do_playlist(url, limit=None):
    limit = limit or config.MAX_PLAYLIST_ITEMS
    limit = max(1, min(int(limit), config.MAX_PLAYLIST_ITEMS))
    opts = _base_opts(extract_flat="in_playlist", playlist_items=f"1-{limit}")
    with yt_dlp.YoutubeDL(opts) as ydl:
        data = ydl.extract_info(url, download=False) or {}

    tracks = []
    for e in data.get("entries") or []:
        if not e or not e.get("id"):
            continue
        tracks.append({
            "vid": e["id"],
            "title": e.get("title", "Unknown"),
            "url": e.get("url", f"https://youtu.be/{e['id']}"),
            "duration": _fmt_sec(e.get("duration")),
            "duration_sec": int(e.get("duration") or 0),
            "thumbnail": _thumb(e, e["id"]),
            "uploader": e.get("channel") or e.get("uploader") or "Unknown",
        })
    return {
        "title": data.get("title", "Playlist"),
        "channel": data.get("channel") or data.get("uploader"),
        "count": len(tracks),
        "tracks": tracks,
    }


async def playlist(url, limit=None):
    return await _run(_do_playlist, url, limit)


# interned helpers
_fmtsec = _seconds_to_minsec


def _fmt_sec(sec):
    return _fmtsec(sec)


def _ext_of(path):
    if not path:
        return ""
    return os.path.splitext(path)[1][1:] or ""