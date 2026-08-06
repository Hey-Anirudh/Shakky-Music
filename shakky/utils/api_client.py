# shakky/utils/api_client.py
# Thin async client for the Shakky Music fetch API. When the API is running,
# the bot pulls super-fast resolved URLs / on-disk files from it instead of
# doing its own yt-dlp extraction. Every call is optional: if the API is
# unreachable or the env var is not set, the bot silently falls back to its
# internal yt-dlp pipeline. Never raises.

import asyncio
import logging
import os
from typing import Optional

import aiohttp

LOGGER = logging.getLogger(__name__)

API_BASE = os.getenv("SHAKKY_API_BASE", "").rstrip("/")
API_TIMEOUT = float(os.getenv("SHAKKY_API_TIMEOUT", "12"))

# Shared-location fallback: the same data dir the API writes to, so the bot
# can play files without any byte transfer when both run on this machine.
_SHARED_DIR = os.getenv("API_DATA_DIR")

_enabled = bool(API_BASE)
_health_known = False
_health_ok = False

# Shared aiohttp session reused across calls (much faster than creating a new
# session + TLS handshake on every request)
_session = None


def reset():
    global _health_known, _health_ok
    _health_known = False
    _health_ok = False


def enabled() -> bool:
    return _enabled


async def _get(path, params=None):
    global _session
    timeout = aiohttp.ClientTimeout(total=API_TIMEOUT)
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(timeout=timeout)
    async with _session.get(f"{API_BASE}{path}", params=params) as resp:
        if resp.status != 200:
            raise RuntimeError(f"api {path} -> {resp.status}")
        return await resp.json()


async def api_available() -> bool:
    """Fast health probe (results cached for the session)."""
    global _health_known, _health_ok
    if not _enabled:
        return False
    if _health_known:
        return _health_ok
    try:
        _health_ok = (await _get("/health")).get("status") == "ok"
    except Exception:
        _health_ok = False
    _health_known = True
    if not _health_ok:
        LOGGER.info("Shakky API not reachable; using internal fetch pipeline.")
    return _health_ok


async def api_search(query, limit=12):
    """Best-effort YouTube search via the fetch API (yt-dlp, no fragile
    youtube-search-parsing). Returns a dict compatible with search()'s result
    or None. Never raises when the API is down."""
    if not _enabled:
        return None
    try:
        data = await _get("/api/search", {"q": query, "limit": limit})
        results = data.get("results") or []
        if not results:
            return None
        top = results[0]
        return {
            "title": top.get("title", "Unknown"),
            "duration": top.get("duration", "0:00"),
            "vidid": top.get("vidid"),
            "thumbnail_url": top.get("thumbnail", "https://via.placeholder.com/360x202?text=No+Thumbnail"),
        }
    except Exception as e:
        LOGGER.debug(f"api_search failed for {query!r}: {e}")
    return None


async def api_stream_url(video_id):
    """Resolve a direct bestaudio URL + headers via the API. Returns
    (url, headers) or (None, None)."""
    if not _enabled:
        return None, None
    try:
        data = await _get(f"/api/url/{video_id}")
        if data.get("url"):
            return data["url"], data.get("headers") or {}
    except Exception as e:
        LOGGER.debug(f"api_stream_url failed for {video_id}: {e}")
    return None, None


async def api_file_path(video_id, ext="m4a"):
    """Ensure the track exists on disk via the API and return its path.
    Returns None if the API is down or the file isn't produced."""
    if not _enabled:
        return None
    try:
        data = await _get(f"/api/locate/{video_id}?format={ext}")
        path = data.get("path")
        if path and os.path.isfile(path):
            return path
        return path
    except Exception as e:
        LOGGER.debug(f"api_file_path failed for {video_id}: {e}")
    # Shared-folder fallback if the API was never hit / best-effort
    if _SHARED_DIR:
        p = os.path.join(_SHARED_DIR, "downloads", f"{video_id}.{ext}")
        if os.path.isfile(p):
            return p
    return None


async def api_download_media(video_id, format="m4a", video=False, dest_dir="downloads"):
    """DOWNLOAD-FIRST: Get a real file on disk via the API and return its
    path. Tries the shared-filesystem locate first, then pulls the file bytes
    over the network and saves them locally. Returns None if the API cannot
    produce a file. Returns (path, ext) so callers know the real extension."""
    if not _enabled:
        return None, None
    try:
        # 1. Shared filesystem: the API already downloaded it to a path we can read
        path = await api_file_path(video_id, format)
        if path and os.path.isfile(path):
            return path, os.path.splitext(path)[1].lstrip(".") or format

        # 2. Network fetch: stream the bytes from the API into our downloads
        os.makedirs(dest, exist_ok=True)
        local_path = os.path.join(os.path.abspath(dest), f"{video_id}.{format}")
        timeout = aiohttp.ClientTimeout(total=300)  # long: full-file download
        async with aiohttp.ClientSession(timeout=timeout) as sess:
            async with sess.get(
                f"{API_BASE}/api/download/{video_id}",
                params={"format": format},
            ) as resp:
                if resp.status != 200:
                    LOGGER.debug(f"api_download_media {video_id} -> {resp.status}")
                    return None, None
                with open(local_path, "wb") as fh:
                    async for chunk in resp.content.iter_chunked(256 * 1024):
                        fh.write(chunk)
        if os.path.isfile(local_path) and os.path.getsize(local_path) > 0:
            LOGGER.info(f"Downloaded via API: {local_path}")
            return local_path, format
    except Exception as e:
        LOGGER.debug(f"api_download_media failed for {video_id}: {e}")
    return None, None


async def api_download_video(video_id, dest="downloads") -> Optional[str]:
    """DOWNLOAD THE FILE (video) via the API and cache locally."""
    if not _enabled:
        return None
    try:
        path = await api_file_path(video_id, "mp4")
        if path and os.path.isfile(path):
            return path
        os.makedirs(dest, exist_ok=True)
        local_path = os.path.join(os.path.abspath(dest), f"{video_id}.mp4")
        timeout = aiohttp.ClientTimeout(total=300)
        async with aiohttp.ClientSession(timeout=timeout) as sess:
            async with sess.get(
                f"{API_BASE}/api/download/{video_id}",
                params={"format": "mp4", "video": "true"},
            ) as resp:
                if resp.status != 200:
                    return None
                with open(local_path, "wb") as fh:
                    async for chunk in resp.content.iter_chunked(256 * 1024):
                        fh.write(chunk)
        if os.path.isfile(local_path) and os.path.getsize(local_path) > 0:
            return local_path
    except Exception as e:
        LOGGER.debug(f"api_download_video failed for {video_id}: {e}")
    return None