# Ani/utils/webapp.py
# Sends playback state to the FastAPI/Socket.io server.
# The server then broadcasts to all connected Mini App clients.

import aiohttp
import os
import time
import logging
from shakky.misc import db

LOGGER = logging.getLogger(__name__)


def _normalize_id(chat_id) -> str:
    """Normalize chat ID for WebApp room. Use absolute value as string."""
    try:
        return str(abs(int(chat_id)))
    except:
        return str(chat_id).replace("-", "")


def _get_media_url(current_song: dict) -> str | None:
    """Resolve file path to a /media/ URL the browser can fetch."""
    if not current_song:
        return None
    file_path = str(current_song.get("file", ""))
    vidid = str(current_song.get("vidid", ""))

    # If actual file exists on disk
    if file_path and os.path.isfile(file_path):
        return f"/media/{os.path.basename(file_path)}"

    # Try to find by vidid in downloads/
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
    """POST state to the local FastAPI server for Socket.io broadcast."""
    try:
        import config
        port = getattr(config, "WEBAPP_PORT", 8100)
    except Exception:
        port = 8100

    url = f"http://localhost:{port}/api/update_state"

    # Determine start_time
    db_song = db.get(chat_id, [{}])[0] if db.get(chat_id) else {}
    db_start = db_song.get("start_time", 0)
    final_start = start_time if start_time is not None else db_start

    # Calculate elapsed
    elapsed = (time.time() - final_start) if (is_playing and final_start > 0) else 0
    elapsed = float(max(0, elapsed))
    safe_chat_id = _normalize_id(chat_id)

    payload = {
        "chat_id": safe_chat_id,
        "is_playing": is_playing,
        "action": action,
        "seek_to": seek_to,
        "loop": loop,
        "start_time": final_start,
        "elapsed": elapsed,
        "current": {
            "title": current_song.get("title", "Unknown"),
            "duration": current_song.get("dur", "0:00"),
            "thumbnail": _get_thumbnail(current_song),
            "by": current_song.get("by", "Unknown"),
            "vidid": current_song.get("vidid", ""),
            "streamtype": current_song.get("streamtype", "audio"),
            "media_url": _get_media_url(current_song),
            "file": current_song.get("file", ""),
        } if current_song else None,
        "queue": [
            {
                "title": q.get("title", "Unknown"),
                "duration": q.get("dur", "0:00"),
                "thumbnail": _get_thumbnail(q),
                "by": q.get("by", "Unknown"),
                "vidid": q.get("vidid", ""),
                "streamtype": q.get("streamtype", "audio"),
                "media_url": None,
            }
            for q in (queue or [])
        ],
    }

    LOGGER.info(f"[webapp] notify room={safe_chat_id} action={action} playing={is_playing}")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status != 200:
                    LOGGER.warning(f"[webapp] Server {resp.status}: {await resp.text()}")
    except aiohttp.ClientConnectorError:
        LOGGER.warning("[webapp] Cannot connect to webapp server — is it running?")
    except Exception as e:
        LOGGER.error(f"[webapp] Error: {e}")
