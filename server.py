import os
import time
import uvicorn
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

try:
    import config
    DEFAULT_PORT = getattr(config, 'WEBAPP_PORT', 8100)
except ImportError:
    DEFAULT_PORT = 8100

PORT = int(os.getenv("WEBAPP_PORT", DEFAULT_PORT))

app = FastAPI(title="Smash Music WebApp")
sio = AsyncServer(async_mode='asgi', cors_allowed_origins='*')
socket_app = ASGIApp(sio, app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Mount both downloads (normal) and playback (speed-modified) directories
# Robust directory resolution (checks multiple levels)
def get_dir(name):
    # 1. Check relative to current file's parent (inside webapp/)
    # 2. Check relative to smashmusic root
    # 3. Check relative to workspace root
    candidates = [
        os.path.join(os.path.dirname(BASE_DIR), name),
        os.path.join(os.getcwd(), name),
        os.path.join(os.getcwd(), "smashmusic", name)
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    # Default to smashmusic root if not found
    path = os.path.join(os.path.dirname(BASE_DIR), name)
    os.makedirs(path, exist_ok=True)
    return path

PLAYBACK_DIR = get_dir("playback")
DOWNLOADS_DIR = get_dir("downloads")

# Custom StaticFiles to prevent aggressive caching of media files
class NoCacheStaticFiles(StaticFiles):
    def is_not_modified(self, response_headers, request_headers) -> bool:
        return False # Force re-validation for media chunks

app.mount("/media", NoCacheStaticFiles(directory=DOWNLOADS_DIR), name="media")
app.mount("/speed", StaticFiles(directory=PLAYBACK_DIR), name="speed")

# ============================================================
# MODELS - media_url is REQUIRED here so it passes through
# ============================================================
class SongInfo(BaseModel):
    title: str
    duration: str
    thumbnail: str
    by: str
    vidid: Optional[str] = None
    streamtype: str
    media_url: Optional[str] = None  # THE KEY FIX: was missing before

class QueueState(BaseModel):
    chat_id: str
    action: Optional[str] = "update"  # Tells webapp what happened
    current: Optional[SongInfo] = None
    queue: List[Any] = []
    is_playing: bool = True
    start_time: float = 0.0
    elapsed: float = 0.0                 # Current playback offset from bot
    server_time: float = 0.0             # Current server epoch
    seek_to: Optional[int] = None      # New
    loop: Optional[int] = 0             # New

# ============================================================
# Persistent State Store
# ============================================================
DB_PATH = os.path.join(os.path.dirname(BASE_DIR), "webapp_db.json")

def load_rooms():
    import json
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_rooms():
    import json
    try:
        # Create a deep copy and STRIP out the users list for database persistence
        to_save = {}
        for k, v in live_rooms.items():
            to_save[k] = {
                "state": v.get("state"),
                "users": {} # Users are real-time only
            }
        with open(DB_PATH, "w") as f:
            json.dump(to_save, f)
    except Exception as e:
        print(f"[DB] Save failed: {e}")

live_rooms = load_rooms()
print(f"[DB] Loaded {len(live_rooms)} room states from disk.")

def normalize_id(chat_id) -> str:
    """Consistently use absolute numeric string for IDs, but keep 'c' prefix for channels to match webapp.py."""
    if not chat_id:
        return "global"
    s = str(chat_id).strip().lower()
    
    # Remove any unwanted characters like slashes if they leaked in
    s = s.replace("/", "").replace("\\", "")
    
    # If it's already 'c' prefixed, return as is
    if s.startswith("c"):
        return s
    # If it's negative (Telegram convention), convert to 'c' prefix
    if s.startswith("-"):
        return "c" + s[1:]
    # If it's a positive 100... ID (WebApp start_param convention), also 'c' prefix it
    if s.startswith("100") and len(s) >= 11:
        return "c" + s
    
    # Fallback to absolute int string
    try:
        return str(abs(int(s)))
    except:
        return s

# ============================================================
# Socket.io Events
# ============================================================
@sio.event
async def connect(sid, environ):
    print(f"[WS] Connected: {sid}")

# 🗺️ Global SID to User mapping for cleanup
# Structure: { sid: (chat_key, user_id) }
sid_to_user = {}

@sio.event
async def join_room(sid, data):
    raw_id = data.get('chat_id')
    user_info = data.get('user', {})
    user_id = user_info.get('id', f"anon_{sid[:4]}")
    name = user_info.get('name', f"User_{sid[:4]}")
    photo = user_info.get('photo')

    if not raw_id:
        print(f"[WS] join_room called without chat_id from {sid}")
        return

    chat_key = normalize_id(raw_id)
    print(f"[WS] {sid} joining room: raw={raw_id} -> key={chat_key}")

    if chat_key not in live_rooms:
        live_rooms[chat_key] = {"state": None, "users": {}}

    # 🛂 UNIQUE TRACKING: Key by user_id instead of sid
    if user_id not in live_rooms[chat_key]["users"]:
        live_rooms[chat_key]["users"][user_id] = {
            "info": {"id": user_id, "name": name, "photo": photo},
            "ref_count": 0
        }
    
    live_rooms[chat_key]["users"][user_id]["ref_count"] += 1
    sid_to_user[sid] = (chat_key, user_id)

    room_name = f"room_{chat_key}"
    await sio.enter_room(sid, room_name)
    
    # Broadcast ONLY unique user info to the room
    unique_users = [u["info"] for u in live_rooms[chat_key]["users"].values()]
    await sio.emit('room_users', {"users": unique_users}, room=room_name)

    # Confirm join and send current state
    await sio.emit('session_init', {"sid": sid, "chat_key": chat_key}, room=sid)
    if live_rooms[chat_key]["state"]:
        state = dict(live_rooms[chat_key]["state"])
        state["server_time"] = time.time()
        await sio.emit('room_update', state, room=sid)
    else:
        print(f"[WS] No state yet for room {chat_key}")

@sio.event
async def disconnect(sid):
    print(f"[WS] Disconnected: {sid}")
    if sid in sid_to_user:
        chat_key, user_id = sid_to_user.pop(sid)
        if chat_key in live_rooms and user_id in live_rooms[chat_key]["users"]:
            # Decrement ref_count
            live_rooms[chat_key]["users"][user_id]["ref_count"] -= 1
            
            # If NO tabs are open for this user, remove them from the room
            if live_rooms[chat_key]["users"][user_id]["ref_count"] <= 0:
                del live_rooms[chat_key]["users"][user_id]
                # Notify remaining users of the updated unique list
                unique_users = [u["info"] for u in live_rooms[chat_key]["users"].values()]
                await sio.emit('room_users', {"users": unique_users}, room=f"room_{chat_key}")
                print(f"[WS] User {user_id} fully left room {chat_key}")

@sio.event
async def client_command(sid, data):
    try:
        from Ani.misc import db
        import time
        from Ani.utils.webapp import notify_webapp
        import asyncio
        
        real_id = -abs(int(chat_id))
        # Robust ID resolution for WebApp commands
        temp_id = chat_id[1:] if str(chat_id).startswith("c") else str(chat_id)
        str_id = str(abs(int(temp_id)))
        if str_id.startswith("100"):
            real_id = int("-" + str_id)
        else:
            real_id = int("-100" + str_id)
            
        print(f"[WS] Executing WebApp Command: {command} for {real_id}")
            
        if command in ["skip", "end_skip"]:
            try:
                from Ani.utils.stream.stream import skip_and_play
                room = live_rooms.get(str(chat_id))
                if command == "end_skip":
                    # Debounce simultaneous end_skips
                    if room and room.get("state") and not room["state"].get("is_playing", False):
                        return
                
                asyncio.create_task(skip_and_play(real_id))
            except Exception as e:
                print(f"Skip error: {e}")
                
        elif command == "pause":
            if real_id in db and db[real_id]:
                if not db[real_id][0].get("paused"):
                    db[real_id][0]["paused"] = True
                    db[real_id][0]["pause_time"] = time.time()
                    await notify_webapp(real_id, is_playing=False, action="pause")
                    
        elif command == "resume" or command == "play":
            if real_id in db and db[real_id]:
                if db[real_id][0].get("paused"):
                    db[real_id][0]["paused"] = False
                    pause_dur = time.time() - db[real_id][0].get("pause_time", time.time())
                    db[real_id][0]["start_time"] += pause_dur
                    await notify_webapp(real_id, is_playing=True, action="resume")
                    
        elif command == "seek":
            if real_id in db and db[real_id]:
                target = int(value or 0)
                db[real_id][0]["start_time"] = time.time() - target
                await notify_webapp(real_id, is_playing=not db[real_id][0].get("paused"), elapsed=target, action="seek")
                
        elif command == "stop":
            db[real_id] = []
            await notify_webapp(real_id, is_playing=False, action="stop")
            
    except Exception as e:
        print(f"[WS] Command execution failed: {e}")

# ============================================================
# REST API - Bot posts here to update state
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
    
    # 🩹 PRESERVATION: If the bot sends a queue-only update (missing 'current'), 
    # we MUST restore the current song from the old state BEFORE checking for "new song"
    if not state_dict.get("current") and old_state and old_state.get("current"):
        state_dict["current"] = old_state["current"]
        action = "update" # Force action to update if we're just restoring metadata
    
    # 🩹 MEDIA URL PRESERVATION: If media_url is missing in the new state, keep the old one
    if state_dict.get("current") and old_state and old_state.get("current"):
        if not state_dict["current"].get("media_url") and old_state["current"].get("media_url"):
            state_dict["current"]["media_url"] = old_state["current"]["media_url"]

    # ⚓ STABLE ANCHOR: Determine if we should reset the sync point
    action = state_dict.get("action", "update")
    is_playing = state_dict.get("is_playing", True)
    elapsed = float(state_dict.get("elapsed", 0.0))
    
    # 🕵️ MEDIA FINGERPRINT: Check if this is truly a NEW song (Url-ID change)
    is_new_song = False
    new_media = state_dict.get("current", {}).get("media_url") if state_dict.get("current") else None
    old_media = old_state.get("current", {}).get("media_url") if old_state and old_state.get("current") else None
    
    if new_media and old_media and new_media != old_media:
        is_new_song = True
        print(f"[SYNC] New Song Detected: {new_media}")

    # 🛂 SYNC LOCK: If it's the SAME song, don't reset the timer (stops the 'restart-on-queue' bug)
    if not is_new_song and action == "play":
        action = "update"
        print(f"[SYNC] Sync Lock: Keeping current playback position while updating queue.")

    if action in ["play", "seek", "skip"] or is_new_song:
        # Fresh Anchor (New event or New song)
        state_dict["start_time"] = current_server_time - elapsed
        print(f"[SYNC] RESET Anchor: action={action} elapsed={elapsed}")
    elif old_state:
        # Preserve existing anchor during simple queue updates or pauses
        state_dict["start_time"] = old_state.get("start_time", current_server_time - elapsed)
        # Handle "Resume" without action="play"
        if is_playing and not old_state.get("is_playing"):
            state_dict["start_time"] = current_server_time - elapsed
            print(f"[SYNC] Resume Anchor Reset: elapsed={elapsed}")
    else:
        # First-ever state
        state_dict["start_time"] = current_server_time - elapsed

    state_dict["server_time"] = current_server_time
    live_rooms[chat_key]["state"] = state_dict
    save_rooms() # Persist
    room_name = f"room_{chat_key}"
    
    media = state_dict.get("current", {}).get("media_url") if state_dict.get("current") else None
    title = state_dict.get("current", {}).get("title") if state_dict.get("current") else "None"
    print(f"[BOT] BROADCAST update room={chat_key} | action={action} | playing={is_playing} | media={media is not None}")

    await sio.emit('room_update', state_dict, room=room_name)
    return {"status": "ok", "chat_key": chat_key, "has_media": bool(media)}

@app.get("/api/state/{raw_id}")
async def get_state(raw_id: str):
    """Allows frontend to poll for current state on page load."""
    chat_key = normalize_id(raw_id)
    room = live_rooms.get(chat_key)
    
    # Log the lookup to debug 404s
    print(f"[API] State request: raw={raw_id} -> key={chat_key} | found={room is not None}")
    
    if room and room.get("state"):
        state = dict(room["state"])
        state["server_time"] = time.time() # Inject fresh server time
        return {"status": "ok", "state": state}
    
    # Robustness: Check if we have an un-prefixed version in live_rooms (legacy fallback)
    alt_key = str(raw_id).strip().replace("-", "")
    if alt_key != chat_key:
        room = live_rooms.get(alt_key)
        if room and room.get("state"):
            print(f"[API] Fallback HIT: key={alt_key}")
            state = dict(room["state"])
            state["server_time"] = time.time()
            return {"status": "ok", "state": state}

    return {"status": "empty", "state": None}

class InviteData(BaseModel):
    chat_id: str
    inviter_id: int
    inviter_name: str
    target_id: int
    target_name: str

active_chat_users = {}

def set_up_pyrogram_listener():
    try:
        from Ani import app as bot_app
        from pyrogram import filters
        
        @bot_app.on_message(filters.group, group=-1)
        async def cache_group_members(client, message):
            if not message.from_user or message.from_user.is_bot:
                return
            chat_id = message.chat.id
            if chat_id not in active_chat_users:
                active_chat_users[chat_id] = {}
            
            if len(active_chat_users[chat_id]) >= 60 and message.from_user.id not in active_chat_users[chat_id]:
                oldest = next(iter(active_chat_users[chat_id]))
                del active_chat_users[chat_id][oldest]
                
            # Re-insert to push to the end of the ordered dict
            if message.from_user.id in active_chat_users[chat_id]:
                del active_chat_users[chat_id][message.from_user.id]
                
            active_chat_users[chat_id][message.from_user.id] = {
                "id": message.from_user.id,
                "name": message.from_user.first_name or "User",
                "username": message.from_user.username or ""
            }
            
        print("[DB] Passive Member Cache Listener attached to Pyrogram")
    except Exception as e:
        print(f"[!] Failed to attach member cacher: {e}")

@app.get("/api/members/{raw_id}")
async def get_group_members(raw_id: str):
    """Fetch recent members from the passive cache"""
    try:
        try:
            real_id = -abs(int(raw_id))
            str_id = str(abs(int(raw_id)))
            if str_id.startswith("100"):
                real_id = int("-" + str_id)
            else:
                real_id = int("-100" + str_id)
        except ValueError:
            return {"status": "error", "message": "Invalid ID"}
            
        global active_chat_users
        members = []
        if real_id in active_chat_users:
            members = list(active_chat_users[real_id].values())
            members.reverse()
            print(f"[API] Fetched {len(members)} active members from cache for {real_id}")
            
        if not members:
            try:
                from Ani import app as bot_app
                async for member in bot_app.get_chat_members(real_id, limit=30):
                    if member.user and not member.user.is_bot:
                        members.append({
                            "id": member.user.id,
                            "name": member.user.first_name or "User",
                            "username": member.user.username or ""
                        })
                print(f"[API] Fetched {len(members)} fallback members using API for {real_id}")
            except Exception as e:
                print(f"[API] Telegram API member fetch fallback blocked: {e}")
                
        return {"status": "ok", "members": members}
    except Exception as e:
        print(f"[API] Error fetching members: {e}")
        return {"status": "error", "members": []}

@app.post("/api/invite")
async def invite_friend(data: InviteData):
    """Send an invite message using the Telegram Bot"""
    try:
        from Ani import app as bot_app
        from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        import config
        
        try:
            str_id = str(abs(int(data.chat_id)))
            if str_id.startswith("100"):
                real_id = int("-" + str_id)
            else:
                real_id = int("-100" + str_id)
        except ValueError:
            return {"status": "error", "message": "Invalid ID"}
            
        bot_username = getattr(config, "BOT_USERNAME", "").replace('@', '')
        webapp_url = f"https://t.me/{bot_username}/join?startapp={abs(real_id)}"
        
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(text="🎧 Join Room", url=webapp_url)]])
        text = (
            f"✦ **ROOM INVITE**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"✧ <a href='tg://user?id={data.inviter_id}'>{data.inviter_name}</a> invited <a href='tg://user?id={data.target_id}'>{data.target_name}</a> to listen to music!\n"
            f"✧ **Click below to join them.**"
        )
        
        await bot_app.send_message(real_id, text, reply_markup=keyboard, disable_web_page_preview=True)
        return {"status": "ok"}
    except Exception as e:
        print(f"[API] Error sending invite: {e}")
        return {"status": "error", "message": str(e)}

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
    import sys
    
    # 🔍 EARLY PORT CHECK: Detect 'already in use' before uvicorn crashes
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("0.0.0.0", PORT))
        sock.close()
    except OSError as e:
        if e.errno == 98 or e.errno == 48: # Linux or Mac/Unix
            print(f"\n[!] WEBAPP STOPPED: Port {PORT} is occupied by another process.")
            print(f"[!] FIX: Run 'fuser -k {PORT}/tcp' then restart the bot.")
            print(f"[!] The Bot will continue running WITHOUT the webapp for now.\n")
            return
        else:
            print(f"[!] WebApp Port Check Failed: {e}")
            return

    try:
        set_up_pyrogram_listener()
        config_uv = uvicorn.Config(socket_app, host="0.0.0.0", port=PORT, log_level="info", handle_signals=False)
        server = uvicorn.Server(config_uv)
        await server.serve()
    except Exception as e:
        print(f"[!] WebApp Server Error: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(start_webapp_server())
