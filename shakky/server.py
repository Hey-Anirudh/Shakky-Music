import os
import time
import socketio
import logging
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Any

LOGGER = logging.getLogger("shakky.server")

# Robust imports
try:
    from socketio import AsyncServer, ASGIApp
except ImportError:
    from socketio.asyncio_server import AsyncServer
    from socketio.asgi import ASGIApp

try:
    import config
    DEFAULT_PORT = getattr(config, 'WEBAPP_PORT', 8100)
except ImportError:
    DEFAULT_PORT = 8100

PORT = int(os.getenv("WEBAPP_PORT", DEFAULT_PORT))

app = FastAPI(title="Shakky Music WebApp")
sio = AsyncServer(async_mode='asgi', cors_allowed_origins='*')
socket_app = ASGIApp(sio, app)

# Inject SIO instance into sync utility
import shakky.utils.sync as sync
sync.SIO_INSTANCE = sio

BASE_DIR = os.path.dirname(os.path.abspath(__file__)) # shakky/
PROJECT_ROOT = os.path.dirname(BASE_DIR)              # root/
STATIC_DIR = os.path.join(PROJECT_ROOT, "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

def get_dir(name):
    path = os.path.join(PROJECT_ROOT, name)
    os.makedirs(path, exist_ok=True)
    return path

PLAYBACK_DIR = get_dir("playback")
DOWNLOADS_DIR = get_dir("downloads")

app.mount("/media", StaticFiles(directory=DOWNLOADS_DIR), name="media")
app.mount("/speed", StaticFiles(directory=PLAYBACK_DIR), name="speed")

THUMBS_DIR = get_dir("downloads/thumbs")
app.mount("/thumbs", StaticFiles(directory=THUMBS_DIR), name="thumbs")

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

from shakky.utils.sync import live_rooms, save_rooms, normalize_id

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
        return

    chat_key = normalize_id(raw_id)
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

@sio.event
async def disconnect(sid):
    if sid in sid_to_user:
        chat_key, user_id = sid_to_user.pop(sid)
        if chat_key in live_rooms and user_id in live_rooms[chat_key]["users"]:
            live_rooms[chat_key]["users"][user_id]["ref_count"] -= 1
            if live_rooms[chat_key]["users"][user_id]["ref_count"] <= 0:
                del live_rooms[chat_key]["users"][user_id]
                unique_users = [u["info"] for u in live_rooms[chat_key]["users"].values()]
                await sio.emit('room_users', {"users": unique_users}, room=f"room_{chat_key}")

@sio.event
async def client_command(sid, data):
    """WebApp Control Commands -> VC Action"""
    try:
        from shakky.core.call import ani
        from shakky.misc import db
        import asyncio

        command = data.get('command')
        value = data.get('value')
        chat_id = data.get('chat_id')
        
        if not chat_id: return
        
        real_id = -abs(int(str(chat_id).replace("c", "")))
        if "100" not in str(real_id):
             # Try mapping back to -100...
             real_id = int("-100" + str(abs(real_id)))

        LOGGER.info(f"[WS] Command: {command} for {real_id}")
            
        if command in ["skip", "end_skip"]:
            from shakky.utils.stream.stream import skip_and_play
            asyncio.create_task(skip_and_play(real_id))
                
        elif command == "pause":
            await ani.pause_stream(real_id)
                    
        elif command == "resume" or command == "play":
            await ani.resume_stream(real_id)
                    
        elif command == "seek" and value is not None:
             # In a real implementation, we'd call ani.seek_stream here
             # For now, we update internal DB and broadcast
             if real_id in db and db[real_id]:
                 target = int(value)
                 db[real_id][0]["start_time"] = time.time() - target
                 from shakky.utils.sync import broadcast_state
                 await broadcast_state(real_id, action="seek")
                
        elif command == "stop":
            await ani.stop_stream(real_id)
            
    except Exception as e:
        LOGGER.error(f"[WS] Command failed: {e}")

# ============================================================
# API Endpoints
# ============================================================
@app.post("/api/update_state")
async def update_state(state: QueueState):
    chat_key = normalize_id(state.chat_id)
    if chat_key not in live_rooms:
        live_rooms[chat_key] = {"state": None, "users": {}}

    state_dict = state.dict()
    current_server_time = time.time()
    
    room = live_rooms.get(chat_key)
    old_state = room.get("state") if room else None
    
    # Preservation & Sync Logic
    if not state_dict.get("current") and old_state and old_state.get("current"):
        state_dict["current"] = old_state["current"]
    
    action = state_dict.get("action", "update")
    is_playing = state_dict.get("is_playing", True)
    elapsed = float(state_dict.get("elapsed", 0.0))
    
    if action in ["play", "seek", "skip"]:
        state_dict["start_time"] = current_server_time - elapsed
    elif old_state:
        state_dict["start_time"] = old_state.get("start_time", current_server_time - elapsed)
    else:
        state_dict["start_time"] = current_server_time - elapsed

    state_dict["server_time"] = current_server_time
    live_rooms[chat_key]["state"] = state_dict
    save_rooms()
    
    await sio.emit('room_update', state_dict, room=f"room_{chat_key}")
    return {"status": "ok"}

active_chat_users = {}

def set_up_pyrogram_listener():
    try:
        from shakky import app as bot_app
        from pyrogram import filters
        
        @bot_app.on_message(filters.group, group=-1)
        async def cache_group_members(client, message):
            if not message.from_user or message.from_user.is_bot: return
            chat_id = message.chat.id
            if chat_id not in active_chat_users: active_chat_users[chat_id] = {}
            active_chat_users[chat_id][message.from_user.id] = {
                "id": message.from_user.id,
                "name": message.from_user.first_name or "User",
                "username": message.from_user.username or ""
            }
        LOGGER.info("[Server] Passive Member Cacher attached.")
    except Exception as e:
        LOGGER.error(f"[Server] Failed to attach member cacher: {e}")

@app.get("/api/members/{raw_id}")
async def get_group_members(raw_id: str):
    chat_key = normalize_id(raw_id)
    # Convert chat_key to real_id
    real_id = -abs(int(chat_key.replace("c", "")))
    if "100" not in str(real_id): real_id = int("-100" + str(abs(real_id)))
    
    members = list(active_chat_users.get(real_id, {}).values())
    members.reverse()
    return {"status": "ok", "members": members[:50]}

# Silently handle /api/new_message (called by external service, not part of Shakky)
@app.post("/api/new_message")
async def handle_new_message():
    return {"status": "ok"}

@app.get("/room/{chat_id}", response_class=HTMLResponse)
@app.get("/", response_class=HTMLResponse)
async def get_room(chat_id: Optional[str] = None):
    room_file = os.path.join(STATIC_DIR, "room.html")
    if os.path.exists(room_file):
        with open(room_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return "room.html not found"

async def start_webapp_server():
    import uvicorn
    import socket
    """Start the WebApp Player FastAPI/Socket.io server."""
    try:
        LOGGER.info(f"Preparing to start WebApp Player Server on port {PORT}...")
        set_up_pyrogram_listener()
        
        config_uv = uvicorn.Config(
            socket_app, 
            host="0.0.0.0", 
            port=PORT, 
            log_level="warning", 
            timeout_keep_alive=60
        )
        server = uvicorn.Server(config_uv)
        
        LOGGER.info(f"WebApp Server BINDING to 0.0.0.0:{PORT}")
        await server.serve()
        
    except Exception as e:
        LOGGER.exception(f"CRITICAL: WebApp Server Failed to start or crashed: {e}")
        # If port is busy, try to log it specifically
        if "address already in use" in str(e).lower():
            LOGGER.error(f"Port {PORT} is already in use. Please check for zombie processes.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(start_webapp_server())
