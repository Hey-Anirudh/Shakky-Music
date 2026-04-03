import os
import time
import json
import logging

LOGGER = logging.getLogger("shakky.sync")
SIO_INSTANCE = None # To be injected by server.py

# Determine project root
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) # shakky/utils
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR)) # shakky/
DB_PATH = os.path.join(PROJECT_ROOT, "webapp_db.json")

def load_rooms():
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

live_rooms = load_rooms()

def save_rooms():
    try:
        to_save = {}
        for k, v in live_rooms.items():
            to_save[k] = {
                "state": v.get("state"),
                "users": {}  
            }
        with open(DB_PATH, "w") as f:
            json.dump(to_save, f)
    except Exception as e:
        LOGGER.warning(f"[DB] Save failed: {e}")

def normalize_id(raw_id) -> str:
    """Standardizes IDs to 'c' prefixed strings for negative IDs."""
    s = str(raw_id).strip()
    if s.startswith("-"):
        return "c" + s[1:]
    if s.startswith("c"):
        return s
    if s.startswith("100") and len(s) >= 11:
        return "c" + s
    return s

async def broadcast_state(chat_id, is_playing: bool = True, action: str = "update"):
    """
    Central state broadcaster. 
    Pulls current state from db and pushes to all WebApp clients via Socket.io.
    """
    from shakky.misc import db
    
    chat_key = normalize_id(chat_id)
    
    try:
        if chat_key.startswith("c"):
            bot_id = int(chat_key[1:]) * -1
        else:
            bot_id = int(chat_key)
    except:
        bot_id = chat_id

    check = db.get(bot_id, [])

    if not check:
        state = {
            "chat_id": chat_key,
            "action": "stop",
            "current": None,
            "queue": [],
            "is_playing": False,
            "elapsed": 0.0,
            "start_time": 0.0,
            "server_time": time.time(),
        }
    else:
        current = check[0]
        start_t = current.get("start_time", time.time())

        if is_playing and start_t > 0:
            elapsed = time.time() - start_t
        else:
            elapsed = current.get("pause_elapsed", 0)

        def build_song(s):
            vidid = s.get("vidid", "")
            thumb = s.get("thumb", "")
            if not (thumb and str(thumb).startswith("http")) and vidid and vidid not in ("telegram", "soundcloud", "index"):
                thumb = f"https://img.youtube.com/vi/{vidid}/hqdefault.jpg"
            if not thumb:
                thumb = "https://files.catbox.moe/5ni0on.jpg"

            file_path = s.get("file", "")
            media_url = None
            if file_path:
                file_path = str(file_path)
                if os.path.isfile(file_path):
                    media_url = f"/media/{os.path.basename(file_path)}"
                else:
                    alt_path = os.path.join(PROJECT_ROOT, "downloads", os.path.basename(file_path))
                    if os.path.isfile(alt_path):
                        media_url = f"/media/{os.path.basename(alt_path)}"
            
            if not media_url and vidid and vidid not in ("telegram", "soundcloud", "index", ""):
                for ext in ["mp3", "m4a", "webm", "ogg", "opus"]:
                    candidate = os.path.join(PROJECT_ROOT, "downloads", f"{vidid}.{ext}")
                    if os.path.exists(candidate):
                        media_url = f"/media/{vidid}.{ext}"
                        break
            
            return {
                "title": s.get("title", "Unknown"),
                "duration": s.get("dur", "0:00"),
                "thumbnail": thumb,
                "by": s.get("by", "User"),
                "vidid": vidid,
                "streamtype": s.get("streamtype", "audio"),
                "media_url": media_url,
                "file": file_path,
            }

        state = {
            "chat_id": chat_key,
            "action": action,
            "current": build_song(current),
            "queue": [build_song(x) for x in check[1:6]],
            "is_playing": is_playing,
            "elapsed": float(max(0, elapsed)),
            "start_time": start_t,
            "server_time": time.time(),
        }

    if chat_key not in live_rooms:
        live_rooms[chat_key] = {"state": None, "users": {}}
    
    live_rooms[chat_key]["state"] = state
    save_rooms()

    if SIO_INSTANCE:
        await SIO_INSTANCE.emit("room_update", state, room=f"room_{chat_key}")
