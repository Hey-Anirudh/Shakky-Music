# shakky/utils/webapp.py
# Sends playback state to the FastAPI/Socket.io server.
# The server then broadcasts to all connected Mini App clients.

import aiohttp
import os
import time
import logging
from shakky.misc import db

LOGGER = logging.getLogger(__name__)


def _normalize_id(raw_id) -> str:
    """Standardizes IDs to 'c' prefixed strings for negative IDs, matching sync.py."""
    s = str(raw_id).strip()
    if s.startswith("-"):
        return "c" + s[1:]
    if s.startswith("c"):
        return s
    if s.startswith("100") and len(s) >= 11:
        return "c" + s
    return s


def _get_media_url(current_song: dict) -> str | None:
    """Resolve file path to a /media/ URL the browser can fetch."""
    if not current_song:
        return None
    file_path = str(current_song.get("file", ""))

    # Stream-first: pass through direct audio URLs (googlevideo etc.) as-is
    if file_path.startswith(("http://", "https://")):
        return file_path

    # If actual file exists on disk
    if file_path and os.path.isfile(file_path):
        return f"/media/{os.path.basename(file_path)}"

    # Try to find by vidid in downloads/
    vidid = str(current_song.get("vidid", ""))
    if vidid and vidid not in ("telegram", "soundcloud", "index", ""):
        downloads_dir = "downloads"
        for ext in ["mp3", "m4a", "webm", "opus", "ogg", "wav"]:
            candidate = os.path.join(downloads_dir, f"{vidid}.{ext}")
            if os.path.isfile(candidate):
                return f"/media/{vidid}.{ext}"
        # Optimistic fallback
        return f"/media/{vidid}.mp3"

    # Last resort: use basename of whatever file path we have
    if file_path:
        return f"/media/{os.path.basename(file_path)}"
    return None


def _get_thumbnail(current_song: dict) -> str:
    """Always prefer YouTube thumbnail URL. Fallback to default."""
    if not current_song:
        return "https://files.catbox.moe/5ni0on.jpg"
    vidid = current_song.get("vidid", "")
    thumb = current_song.get("thumb", "")
    if thumb and str(thumb).startswith("http"):
        return thumb
    if vidid and vidid not in ("telegram", "soundcloud", "index", ""):
        return f"https://img.youtube.com/vi/{vidid}/hqdefault.jpg"
    return "https://files.catbox.moe/5ni0on.jpg"


async def notify_webapp(
    chat_id,
    current_song: dict = None,
    queue: list = None,
    is_playing: bool = True,
    action: str = "update",
    seek_to: int = None,
    loop: int = 0,
    start_time: float = None,
):
    """Webapp has been disabled entirely. All notifications are no-ops."""
    return
