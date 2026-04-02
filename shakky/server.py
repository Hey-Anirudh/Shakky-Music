import os
import time
import socketio

# Robust imports
try:
    from socketio import AsyncServer, ASGIApp
except ImportError:
    try:
        from socketio.asyncio_server import AsyncServer
        from socketio.asgi import ASGIApp
    except ImportError:
        AsyncServer = getattr(socketio, 'AsyncServer', None)
        ASGIApp = getattr(socketio, 'ASGIApp', None)

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Any
import logging

LOGGER = logging.getLogger("shakky.server")

try:
    import config
    DEFAULT_PORT = getattr(config, 'WEBAPP_PORT', 8100)
except ImportError:
    DEFAULT_PORT = 8100

PORT = int(os.getenv("WEBAPP_PORT", DEFAULT_PORT))

app = FastAPI(title="Smash Music WebApp")
sio = AsyncServer(async_mode='asgi', cors_allowed_origins='*')
socket_app = ASGIApp(sio, app)
import shakky.utils.sync as sync
sync.SIO_INSTANCE = sio

# Dynamic path resolution
BASE_DIR = os.path.dirname(os.path.abspath(__file__))   # Ani/
PROJECT_ROOT = os.path.dirname(BASE_DIR)                # smashmusic/
STATIC_DIR = os.path.join(PROJECT_ROOT, "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Mount media directories
def get_dir(name):
    candidates = [
        os.path.join(PROJECT_ROOT, name),
        os.path.join(os.path.dirname(PROJECT_ROOT), "smashmusic", name),
        os.path.join(os.getcwd(), name),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    path = os.path.join(PROJECT_ROOT, name)
    os.makedirs(path, exist_ok=True)
    return path

DOWNLOADS_DIR = get_dir("downloads")
PLAYBACK_DIR = get_dir("playback")

app.mount("/media", StaticFiles(directory=DOWNLOADS_DIR), name="media")
app.mount("/speed", StaticFiles(directory=PLAYBACK_DIR), name="speed")

# ============================================================
# MODELS
# ============================================================
class SongInfo(BaseModel):
    title: str
    duration: str
    thumbnail: str
    by: str
    vidid: Optional[str] = None
    streamtype: str
    media_url: Optional[str] = None

class QueueState(BaseModel):
    chat_id: str
    action: Optional[str] = "update"
    current: Optional[SongInfo] = None
    queue: List[Any] = []
    is_playing: bool = True
    start_time: float = 0.0
    elapsed: float = 0.0
    server_time: float = 0.0
    seek_to: Optional[int] = None
    loop: Optional[int] = 0

from shakky.utils.sync import live_rooms, save_rooms, normalize_id, DB_PATH
LOGGER.info(f"[DB] Loaded {len(live_rooms)} room states from disk.")

# ============================================================
# Socket.io Events
# ============================================================
@sio.event
async def connect(sid, environ):
    LOGGER.info(f"[WS] Connected: {sid}")

sid_to_user = {}

@sio.event
async def join_room(sid, data):
    raw_id = data.get('chat_id')
    user_info = data.get('user', {})
    user_id = user_info.get('id', f"anon_{sid[:4]}")
    name = user_info.get('name', f"User_{sid[:4]}")
    photo = user_info.get('photo')

    if not raw_id:
        LOGGER.warning(f"[WS] join_room called without chat_id from {sid}")
        return

    chat_key = normalize_id(raw_id)
    LOGGER.info(f"[WS] {sid} joining room: raw={raw_id} -> key={chat_key}")

    if chat_key not in live_rooms:
        live_rooms[chat_key] = {"state": None, "users": {}}

    if user_id not in live_rooms[chat_key]["users"]:
        live_rooms[chat_key]["users"][user_id] = {
            "info": {"id": user_id, "name": name, "photo": photo},
            "ref_count": 0
        }

    live_rooms[chat_key]["users"][user_id]["ref_count"] += 1
    sid_to_user[sid] = (chat_key, user_id)

    room_name = f"room_{chat_key}"
    await sio.enter_room(sid, room_name)

    unique_users = [u["info"] for u in live_rooms[chat_key]["users"].values()]
    await sio.emit('room_users', {"users": unique_users}, room=room_name)

    await sio.emit('session_init', {"sid": sid, "chat_key": chat_key}, room=sid)
    if live_rooms[chat_key]["state"]:
        state = dict(live_rooms[chat_key]["state"])
        state["server_time"] = time.time()
        await sio.emit('room_update', state, room=sid)
    else:
        LOGGER.info(f"[WS] No state yet for room {chat_key}")

@sio.event
async def disconnect(sid):
    LOGGER.info(f"[WS] Disconnected: {sid}")
    if sid in sid_to_user:
        chat_key, user_id = sid_to_user.pop(sid)
        if chat_key in live_rooms and user_id in live_rooms[chat_key]["users"]:
            live_rooms[chat_key]["users"][user_id]["ref_count"] -= 1
            if live_rooms[chat_key]["users"][user_id]["ref_count"] <= 0:
                del live_rooms[chat_key]["users"][user_id]
                unique_users = [u["info"] for u in live_rooms[chat_key]["users"].values()]
                await sio.emit('room_users', {"users": unique_users}, room=f"room_{chat_key}")
                LOGGER.info(f"[WS] User {user_id} fully left room {chat_key}")


@sio.event
async def client_command(sid, data):
    """
    Handles commands FROM the WebApp browser:
    pause, resume, skip, seek — applied to in-memory db then re-broadcast.
    No VC calls. Pure db manipulation + re-broadcast.
    """
    from shakky.misc import db
    from shakky.utils.stream.autoclear import auto_clean

    command = data.get('command')
    value = data.get('value')

    if sid not in sid_to_user or not command:
        return

    chat_key, user_id = sid_to_user[sid]

    try:
        # Robust Telegram ID mapping (fixes prefixed keys like 'c100...')
        temp_id = chat_key[1:] if chat_key.startswith("c") else chat_key
        str_id = str(abs(int(temp_id)))
        if str_id.startswith("100"):
            bot_chat_id = int("-" + str_id)
        else:
            bot_chat_id = int("-100" + str_id)
    except Exception as e:
        LOGGER.error(f"[WS] ID Normalization failed for {chat_key}: {e}")
        return

    LOGGER.info(f"[WS] Command from {sid} (user={user_id}): {command} (chat={bot_chat_id}, value={value})")

    # --- ADMIN CHECK ---
    try:
        from shakky import app as tg_app
        from pyrogram.enums import ChatMemberStatus
        import config as cfg

        is_owner = str(user_id) == str(getattr(cfg, 'OWNER_ID', ''))

        if not is_owner:
            try:
                member = await tg_app.get_chat_member(bot_chat_id, user_id)
                if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
                    LOGGER.warning(f"[WS] Perms Denied for user {user_id} in {bot_chat_id}")
                    await sio.emit('toast', {"msg": "❌ Admin permissions required!", "type": "error"}, room=sid)
                    return
            except Exception as e:
                LOGGER.error(f"[WS] Permission lookup failed: {e}")
                await sio.emit('toast', {"msg": "❌ Security check failed.", "type": "error"}, room=sid)
                return
    except Exception as e:
        LOGGER.error(f"[WS] Error checking permissions: {e}")
        return

    # --- EXECUTE COMMAND (pure db manipulation, no VC) ---
    try:
        from shakky.utils.sync import broadcast_state
        check = db.get(bot_chat_id, [])

        if command in ["skip", "end_skip"]:
            if check:
                from shakky.utils.stream.stream import skip_and_play
                await skip_and_play(bot_chat_id)
                await sio.emit('toast', {"msg": "⏭ Skipped", "type": "success"}, room=sid)
            else:
                await sio.emit('toast', {"msg": "❌ Queue is empty!", "type": "error"}, room=sid)

        elif command == "pause" and check:
            start_t = check[0].get("start_time", time.time())
            check[0]["paused"] = True
            check[0]["pause_time"] = time.time()
            check[0]["pause_elapsed"] = time.time() - start_t
            await broadcast_state(bot_chat_id, is_playing=False, action="pause")
            await sio.emit('toast', {"msg": "⏸ Paused", "type": "success"}, room=sid)

        elif command == "resume" and check:
            paused_elapsed = check[0].get("pause_elapsed", 0)
            check[0]["start_time"] = time.time() - paused_elapsed
            check[0]["paused"] = False
            await broadcast_state(bot_chat_id, is_playing=True, action="resume")
            await sio.emit('toast', {"msg": "▶️ Resumed", "type": "success"}, room=sid)

        elif command == "seek" and check and value is not None:
            seek_to = int(value)
            check[0]["start_time"] = time.time() - seek_to
            check[0]["played"] = seek_to
            await broadcast_state(bot_chat_id, is_playing=True, action="seek")
            await sio.emit('toast', {"msg": f"⏩ Seeked to {seek_to}s", "type": "success"}, room=sid)

        else:
            await sio.emit('toast', {"msg": f"❓ Unknown command: {command}", "type": "error"}, room=sid)

    except Exception as e:
        LOGGER.error(f"[WS] Error executing command {command}: {e}")
        await sio.emit('toast', {"msg": f"❌ Error: {str(e)[:50]}", "type": "error"}, room=sid)


# ============================================================
# REST API - Bot posts here to update webapp state
# ============================================================
@app.post("/api/update_state")
async def update_state(state: QueueState):
    state_dict = state.dict()
    return await finalize_and_broadcast(state_dict)

async def finalize_and_broadcast(state_dict):
    """Processes state data, maps media URLs, and emits to Socket.io."""
    chat_id = state_dict.get("chat_id")
    chat_key = normalize_id(chat_id)
    current_server_time = time.time()

    if chat_key not in live_rooms:
        live_rooms[chat_key] = {"state": None, "users": {}}

    room = live_rooms.get(chat_key)
    old_state = room.get("state") if room else None

    # Resolve filename to /media/ URL for the browser
    if state_dict.get("current") and "file" in state_dict["current"]:
        file_val = state_dict["current"]["file"]
        if file_val and not str(file_val).startswith("http"):
            filename = os.path.basename(file_val)
            state_dict["current"]["media_url"] = f"/media/{filename}"
            LOGGER.info(f"[URL] {filename} -> /media/{filename}")

    # Restore missing metadata from previous state
    if not state_dict.get("current") and old_state and old_state.get("current"):
        state_dict["current"] = old_state["current"]
    if state_dict.get("current") and old_state and old_state.get("current"):
        if not state_dict["current"].get("media_url") and old_state["current"].get("media_url"):
            state_dict["current"]["media_url"] = old_state["current"]["media_url"]

    action = state_dict.get("action", "update")
    is_playing = state_dict.get("is_playing", True)
    elapsed = float(state_dict.get("elapsed", 0.0))

    # Sync Fingerprinting
    is_new_song = False
    new_media = state_dict.get("current", {}).get("media_url") if state_dict.get("current") else None
    old_media = old_state.get("current", {}).get("media_url") if old_state and old_state.get("current") else None
    if new_media and old_media and new_media != old_media:
        is_new_song = True

    if action in ["play", "seek", "skip"] or is_new_song:
        state_dict["start_time"] = current_server_time - elapsed
    elif old_state:
        state_dict["start_time"] = old_state.get("start_time", current_server_time - elapsed)
        if is_playing and not old_state.get("is_playing"):
            state_dict["start_time"] = current_server_time - elapsed
    else:
        state_dict["start_time"] = current_server_time - elapsed

    state_dict["server_time"] = current_server_time
    live_rooms[chat_key]["state"] = state_dict
    save_rooms()

    # Corrected: Handle None current song gracefully
    current_song = state_dict.get("current")
    has_media = bool(current_song.get("media_url")) if current_song else False
    
    # CRITICAL: Broadcast to all connected clients!
    await sio.emit('room_update', state_dict, room=f"room_{chat_key}")
    
    return {"status": "ok", "chat_key": chat_key, "has_media": has_media}


async def broadcast_state(chat_id, is_playing: bool = True, action: str = "update"):
    """Thin wrapper to avoid circularity - calls the utility function."""
    # SIO_INSTANCE is set at module load time above
    return await sync.broadcast_state(chat_id, is_playing, action)


@app.get("/api/state/{raw_id}")
async def get_state(raw_id: str):
    """Frontend can poll this at page load for current state."""
    chat_key = normalize_id(raw_id)
    room = live_rooms.get(chat_key)
    if room and room.get("state"):
        state = dict(room["state"])
        state["server_time"] = time.time()
        return {"status": "ok", "state": state}
    return {"status": "empty", "state": None}

@app.get("/room/{chat_id}", response_class=HTMLResponse)
@app.get("/", response_class=HTMLResponse)
async def get_room(chat_id: Optional[str] = None):
    room_file = os.path.join(STATIC_DIR, "room.html")
    if os.path.exists(room_file):
        with open(room_file, "r", encoding="utf-8") as f:
            content = f.read()
            return HTMLResponse(
                content=content,
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
    return f"room.html not found at {room_file}"

async def start_webapp_server():
    import uvicorn
    import socket

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("0.0.0.0", PORT))
        sock.close()
    except OSError as e:
        if e.errno in (98, 48, 10048):
            LOGGER.error(f"[!] WEBAPP STOPPED: Port {PORT} is already in use.")
            return
        else:
            LOGGER.error(f"[!] WebApp Port Check Failed: {e}")
            return

    LOGGER.info(f"Starting Smash Music WebApp on port {PORT}...")
    try:
        config_uv = uvicorn.Config(socket_app, host="0.0.0.0", port=PORT, log_level="error")
        server = uvicorn.Server(config_uv)
        await server.serve()
    except Exception as e:
        LOGGER.error(f"[!] WebApp Server Error: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(start_webapp_server())
