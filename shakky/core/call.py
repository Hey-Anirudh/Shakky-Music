import asyncio
import os
import time
import re
import logging
from datetime import datetime, timedelta
from typing import Union

from pyrogram import Client
from pyrogram.enums import ChatType, ChatMemberStatus
from pyrogram.errors import PeerIdInvalid, ChatWriteForbidden, UserNotParticipant
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import pytgcalls
from pytgcalls.exceptions import (
    AlreadyJoinedError,
    NoActiveGroupCall,
    TelegramServerError,
)

# --- 🎭 Remade Effects System (The Core of the Overhaul) ---
class VoiceFilter:
    """Centralized registry and composer for all audio/video effects."""
    
    # Static Filter Library
    PRESETS = {
        "bass_boost": "equalizer=f=60:width_type=h:width=50:g=12,equalizer=f=120:width_type=h:width=100:g=6",
        "8d_audio": "apulsator=mode=sine:hz=0.09:amount=0.8,aecho=0.8:0.88:60:0.4",
        "nightcore": "asetrate=48000*1.25,aresample=48000",
        "slowed_reverb": "asetrate=48000*0.8,aresample=48000,aecho=0.8:0.88:60:0.4",
        "echo": "aecho=0.8:0.88:60:0.4",
        "reverb": "aecho=0.8:0.88:60:0.4",
        "fade_in": "afade=t=in:ss=0:d=2",
        "fade_out": "afade=t=out:st={dur_sec}-2:d=2",
    }

    @classmethod
    def build_ffmpeg_args(cls, payload: dict, duration_sec: int = 0) -> str:
        """
        Translates a logic payload into a raw FFmpeg filter string.
        Payload keys: 'af' (preset key or raw string), 'speed', 'fade_in', 'fade_out'
        """
        if not payload:
            return ""
            
        filters = []
        
        # 1. Base Effects / Presets
        af = payload.get("af")
        if af:
            preset = cls.PRESETS.get(af)
            if preset:
                filters.append(preset)
            else:
                # Assume raw FFmpeg string
                filters.append(af)
        
        # 2. Dynamic Transitions
        if payload.get("fade_in") or payload.get("is_prodj"):
            filters.append(cls.PRESETS["fade_in"])
        
        if payload.get("fade_out") and duration_sec > 10:
            filters.append(cls.PRESETS["fade_out"].format(dur_sec=duration_sec))
            
        # 3. Playback Speed (Independent of pitch)
        speed = payload.get("speed", 1.0)
        if speed != 1.0:
            # Handle speed outside 0.5-2.0 range by chaining atempo
            s = float(speed)
            while s > 2.0:
                filters.append("atempo=2.0")
                s /= 2.0
            while s < 0.5:
                filters.append("atempo=0.5")
                s /= 0.5
            filters.append(f"atempo={s}")
            
        return ",".join(filters)

# 🤖 Universal Core Switch (ARM VPS Fix)
IS_V3 = False
IS_LEGACY = False

try:
    # --- Modern Era (v1, v2, v3) ---
    from pytgcalls import PyTgCalls, StreamType
    from pytgcalls.types.input_stream import AudioPiped, AudioVideoPiped
    from pytgcalls.types.input_stream.quality import HighQualityAudio, MediumQualityVideo
    from pytgcalls.types import Update
    if not hasattr(PyTgCalls, "join_group_call"): raise ImportError("Legacy")
    try:
        from pytgcalls.types.stream import StreamAudioEnded, StreamVideoEnded
        IS_V3 = True
    except ImportError:
        IS_V3 = False
    IS_LEGACY = False
except ImportError:
    # --- Legacy Era (v0.9.x) ---
    IS_LEGACY = True
    try:
        from pytgcalls import GroupCallFactory
        class PyTgCalls:
            def __init__(self, client, **kwargs):
                self._factory = GroupCallFactory(client)
                self._call = self._factory.get_group_call()
                self._parent = kwargs.get("parent")
                self.start = self._call.start
                self.stop = self._call.stop
                self.join = self._call.join
                self.leave = self._call.leave
                self.start_audio = self._call.start_audio
                self.pause_stream = self._call.pause_stream
                self.resume_stream = self._call.resume_stream
                
                async def change_stream(chat_id, stream):
                    if isinstance(stream, str) and stream.startswith("ffmpeg"):
                        # 🌪️ DIRECT OUTPUT UPDATE: Robust Legacy Engine
                        
                        # 1. Stop current audio if possible
                        if hasattr(self._call, "stop_audio"):
                            try: await self._call.stop_audio()
                            except: pass
                        
                        # 2. Cleanup old process
                        if self._parent and chat_id in self._parent._chat_procs:
                            try: 
                                proc = self._parent._chat_procs[chat_id]
                                proc.kill()
                                await proc.wait()
                            except: pass
                        
                        # 3. Create a unique pipe path
                        ts = int(time.time() * 1000)
                        pipe_path = os.path.abspath(f"downloads/pipe_{abs(chat_id)}_{ts}.pcm")
                        
                        if hasattr(os, "mkfifo"):
                            try: os.mkfifo(pipe_path)
                            except: pass
                        
                        # 4. Prepare and start FFmpeg with shlex parsing for safety
                        import shlex
                        final_cmd = stream.replace("pipe:1", pipe_path)
                        args = shlex.split(final_cmd)
                        
                        proc = await asyncio.create_subprocess_exec(
                            *args,
                            stdout=asyncio.subprocess.DEVNULL,
                            stderr=asyncio.subprocess.DEVNULL
                        )
                        if self._parent: self._parent._chat_procs[chat_id] = proc
                        
                        # 5. Wait for the pipe to be ready
                        await asyncio.sleep(2.5)
                        
                        # 6. Start the new audio stream (Raw PCM path)
                        try:
                            # We don't await this as start_audio in v0.9.x might be blocking or weird
                            return await self._call.start_audio(pipe_path)
                        except Exception as e:
                            LOGGER.error(f"Legacy start_audio failed: {e}")
                            return False
                    
                    if hasattr(self._call, "stop_audio"):
                        try: await self._call.stop_audio()
                        except: pass
                    path = getattr(stream, 'path', stream)
                    return await self._call.start_audio(path)
                self.change_stream = change_stream
    except ImportError:
        try: from pytgcalls import PyTgCalls
        except ImportError: raise ImportError("Critical: No PyTgCalls found.")

    # Legacy dummies/shims
    class AudioPiped: 
        def __init__(self, p, **kwargs): 
            self.path = p
            self.filters = kwargs.get("additional_ffmpeg_parameters", "")
    class AudioVideoPiped(AudioPiped): pass
    class HighQualityAudio: pass
    class MediumQualityVideo: pass
    class Update: pass
    class StreamAudioEnded: pass
    class StreamVideoEnded: pass
    class StreamDeleted: pass
    class StreamType:
        pulse_stream = "pulse"
        pulse = "pulse"

# Ensure types
if "StreamAudioEnded" not in globals():
    class StreamAudioEnded: pass
if "Update" not in globals():
    class Update: pass
if "StreamType" not in globals():
    class StreamType:
        pulse = "pulse"
        pulse_stream = "pulse"

import config
from shakky import YouTube, app
from shakky.misc import db
from shakky.utils.database import (
    add_active_chat,
    add_active_video_chat,
    get_lang,
    get_loop,
    group_assistant,
    is_autoend,
    music_on,
    remove_active_chat,
    remove_active_video_chat,
    set_loop,
)
from shakky.utils.exceptions import AssistantErr
from shakky.utils.formatters import check_duration, seconds_to_min, speed_converter, time_to_seconds
from shakky.utils.inline.play import stream_markup
from shakky.utils.stream.autoclear import auto_clean
from shakky.utils.webapp import notify_webapp
from shakky.utils.thumbnails import get_thumb
from strings import get_string

autoend = {}
counter = {}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
LOGGER = logging.getLogger(__name__)

async def _clear_(chat_id):
    db[chat_id] = []
    await remove_active_video_chat(chat_id)
    await remove_active_chat(chat_id)

class Call:
    def __init__(self):
        os.makedirs("downloads", exist_ok=True)
        def _init_ass(userbot):
            if not userbot: return None
            if IS_LEGACY: return PyTgCalls(userbot, parent=self, cache_duration=100)
            return PyTgCalls(userbot, cache_duration=100)

        self.userbot1 = Client(name="Ass1", api_id=config.API_ID, api_hash=config.API_HASH, session_string=str(config.STRING1), no_updates=True)
        self.one = _init_ass(self.userbot1)
        self.userbot2 = Client(name="Ass2", api_id=config.API_ID, api_hash=config.API_HASH, session_string=str(config.STRING2), no_updates=True) if config.STRING2 else None
        self.two = _init_ass(self.userbot2)
        self.userbot3 = Client(name="Ass3", api_id=config.API_ID, api_hash=config.API_HASH, session_string=str(config.STRING3), no_updates=True) if config.STRING3 else None
        self.three = _init_ass(self.userbot3)
        self.userbot4 = Client(name="Ass4", api_id=config.API_ID, api_hash=config.API_HASH, session_string=str(config.STRING4), no_updates=True) if config.STRING4 else None
        self.four = _init_ass(self.userbot4)
        self.userbot5 = Client(name="Ass5", api_id=config.API_ID, api_hash=config.API_HASH, session_string=str(config.STRING5), no_updates=True) if config.STRING5 else None
        self.five = _init_ass(self.userbot5)
        self._locks = {}
        self._last_skip = {}
        self._active_effects = {} # chat_id -> effect_payload
        self._switching = set() # Tracks chats currently applying filters to ignore transient "end" events
        self._chat_procs = {} # chat_id -> FFmpeg subprocess for legacy piping

    def get_lock(self, chat_id: int):
        if chat_id not in self._locks: self._locks[chat_id] = asyncio.Lock()
        return self._locks[chat_id]

    # --- 🛠️ Remade Stream Builder (Extreme VPS Compatibility Edition) ---
    def build_stream(self, path, video, payload=None, duration=0, chat_id=None):
        """Constructs the stream path or object. For Legacy + Effects, returns a Pipe command."""
        # Merge global effects if any
        if chat_id and chat_id in self._active_effects:
             merged_payload = {**self._active_effects[chat_id], **(payload or {})}
        else:
             merged_payload = payload or {}

        filters = VoiceFilter.build_ffmpeg_args(merged_payload, duration)
        
        # Seek logic
        ss = merged_payload.get("ss", 0)
        to = merged_payload.get("to", "")
        
        if IS_LEGACY and (filters or ss != 0):
            # 🚀 REMAKE: For Legacy, we use Raw PCM for maximum stability
            seek_arg = f"-ss {ss}"
            if to: seek_arg += f" -to {to}"
            
            filter_arg = f"-af \"{filters}\"" if filters else ""
            re_arg = "-re" if str(path).startswith("http") else ""
            
            # Switched to Raw PCM (s16le) as some legacy versions struggle with WAV headers in pipes
            return f'ffmpeg -y -loglevel panic {re_arg} {seek_arg} -i "{path}" {filter_arg} -vn -f s16le -ac 2 -ar 48000 pipe:1'

        # Modern or No-Effect Legacy
        ffmpeg_args = f"-ss {ss}"
        if to: ffmpeg_args += f" -to {to}"
        if filters: ffmpeg_args += f" -af \"{filters}\""

        if video:
            return AudioVideoPiped(path, HighQualityAudio(), MediumQualityVideo(), additional_ffmpeg_parameters=ffmpeg_args)
        return AudioPiped(path, HighQualityAudio(), additional_ffmpeg_parameters=ffmpeg_args)

    async def join_call(self, chat_id, original_chat_id, link, video=None, image=None, payload=None):
        assistant = await group_assistant(self, chat_id)
        userbot = self.userbot1 if assistant == self.one else (self.userbot2 if assistant == self.two else (self.userbot3 if assistant == self.three else (self.userbot4 if assistant == self.four else self.userbot5)))
        
        # Build stream
        stream = self.build_stream(link, video, payload, payload.get("seconds", 0) if payload else 0, chat_id=chat_id)

        # Step 1: Membership Check
        try:
            if not userbot.me: await userbot.get_me()
            try: await app.add_chat_members(chat_id, userbot.me.id)
            except: pass
        except: pass

        # Step 2: Join Logic
        joined = False
        for attempt in range(2):
            try:
                if IS_LEGACY:
                    try: await assistant.join(chat_id)
                    except: pass
                    await asyncio.wait_for(assistant.start_audio(stream), timeout=20)
                else:
                    await asyncio.wait_for(assistant.join_group_call(chat_id, stream), timeout=30)
                joined = True; break
            except AlreadyJoinedError: joined = True; break
            except Exception as e:
                if "ALREADY_JOINED" in str(e).upper(): joined = True; break
                LOGGER.error(f"[join] Attempt {attempt} failed: {e}")
                await asyncio.sleep(1)

        if joined:
            await add_active_chat(chat_id)
            await music_on(chat_id)
            if video: await add_active_video_chat(chat_id)
        else:
             try: await app.send_message(original_chat_id, text="⚠️ **Failed to join Voice Chat. Please ensure Assistant is in group.**")
             except: pass

    async def apply_audio_filter(self, chat_id: int, filter_key: str, playing: list):
        """Applies a specific audio filter in real-time by re-syncing the stream."""
        if not playing: return
        
        self._switching.add(chat_id)
        try:
            # Update active effect state
            if chat_id not in self._active_effects: self._active_effects[chat_id] = {}
            
            if filter_key:
                # Store the filter key or raw ffmpeg string
                self._active_effects[chat_id]["af"] = filter_key 
            else:
                self._active_effects[chat_id].pop("af", None)

            # Sync stream
            await self._sync_stream(chat_id, playing)
        finally:
            await asyncio.sleep(2)
            self._switching.discard(chat_id)

    async def seek_stream(self, chat_id, to_seek, *args, **kwargs):
        """Seeks to a specific position in the current track."""
        playing = db.get(chat_id)
        if not playing: return
        
        # Handle both integer seconds and "MM:SS" strings
        if isinstance(to_seek, str):
            to_seek = time_to_seconds(to_seek)
        
        self._switching.add(chat_id)
        try:
            playing[0]["start_time"] = time.time() - to_seek
            await self._sync_stream(chat_id, playing)
        finally:
            await asyncio.sleep(2)
            self._switching.discard(chat_id)

    async def speedup_stream(self, chat_id, file_path, speed, playing):
        """Changes the playback speed of the current stream."""
        if not playing: return
        
        self._switching.add(chat_id)
        try:
            if chat_id not in self._active_effects: self._active_effects[chat_id] = {}
            self._active_effects[chat_id]["speed"] = float(speed)
            
            await self._sync_stream(chat_id, playing)
        finally:
            await asyncio.sleep(2)
            self._switching.discard(chat_id)

    async def _sync_stream(self, chat_id, playing):
        """Core internal method to re-initialize the stream with current state (seek/filters/speed)."""
        track = playing[0]
        start_time = track.get("start_time", time.time())
        current_pos = int(time.time() - start_time)
        if current_pos < 0: current_pos = 0
        
        payload = {"ss": current_pos}
        stream = self.build_stream(track["file"], (track["streamtype"] == "video"), payload, track.get("seconds", 0), chat_id=chat_id)
        
        ass = await group_assistant(self, chat_id)
        try:
            await ass.change_stream(chat_id, stream)
            if not IS_LEGACY:
                await asyncio.sleep(0.5)
                await ass.resume_stream(chat_id)
        except Exception as e:
            LOGGER.error(f"Sync stream failed for {chat_id}: {e}")

    async def change_stream(self, client, chat_id, mention=None, skip_pop: bool = False):
        lock = self.get_lock(chat_id)
        async with lock:
            if not skip_pop:
                if time.time() - self._last_skip.get(chat_id, 0) < 1.5: return
                self._last_skip[chat_id] = time.time()

            check = db.get(chat_id)
            if not check:
                await _clear_(chat_id)
                try: 
                    if IS_LEGACY: await client.leave(chat_id)
                    else: await client.leave_group_call(chat_id)
                except: pass
                return

            if not skip_pop:
                loop = await get_loop(chat_id)
                if loop == 0:
                    popped = check.pop(0)
                    await auto_clean(popped)
                else: await set_loop(chat_id, loop - 1)
                
                if not check:
                    await _clear_(chat_id)
                    try:
                        if IS_LEGACY: await client.leave(chat_id)
                        else: await client.leave_group_call(chat_id)
                    except: pass
                    return

            track = check[0]
            queued = track["file"]
            title = track["title"].title()
            videoid = track["vidid"]
            video = (track["streamtype"] == "video")
            
            if "vid_" in queued and not os.path.exists(queued) and videoid:
                try:
                    from shakky.platforms import YouTube as YT
                    file_path, _ = await asyncio.wait_for(YT.download(videoid, video=video, raw_query=title), timeout=60)
                    if file_path: queued = file_path; track["file"] = file_path
                except: queued = None
            
            if not queued or not os.path.exists(queued):
                if len(check) > 0:
                    check.pop(0)
                    if len(check) > 0: return await self.change_stream(client, chat_id, skip_pop=True)
                await _clear_(chat_id); return

            payload = {"is_prodj": True} if chat_id in self._active_effects else {}
            stream = self.build_stream(queued, video, payload, track.get("seconds", 0), chat_id=chat_id)
            
            try:
                track["start_time"] = time.time()
                await client.change_stream(chat_id, stream)
            except Exception as e:
                LOGGER.error(f"change_stream failed: {e}")
                if len(check) > 0:
                    check.pop(0)
                    if len(check) > 0: return await self.change_stream(client, chat_id, skip_pop=True)
                await _clear_(chat_id); return

            asyncio.create_task(notify_webapp(chat_id, current_song=track, queue=check[1:6], action="skip", is_playing=True))
            asyncio.create_task(self._send_now_playing(chat_id, videoid, title, track["by"], track["chat_id"], mention))

    async def pause_stream(self, chat_id):
        ass = await group_assistant(self, chat_id)
        try:
             if not IS_LEGACY: await ass.pause_stream(chat_id)
        except: pass
        await notify_webapp(chat_id, action="pause", is_playing=False)

    async def resume_stream(self, chat_id):
        ass = await group_assistant(self, chat_id)
        try:
             if not IS_LEGACY: await ass.resume_stream(chat_id)
        except: pass
        await notify_webapp(chat_id, action="play", is_playing=True)

    async def stop_stream(self, chat_id):
        ass = await group_assistant(self, chat_id)
        try:
            await _clear_(chat_id)
            if chat_id in self._chat_procs:
                try: self._chat_procs[chat_id].terminate()
                except: pass
                del self._chat_procs[chat_id]
            
            if IS_LEGACY: await ass.leave(chat_id)
            else: await ass.leave_group_call(chat_id)
        except: pass
        await notify_webapp(chat_id, action="stop")

    async def _send_now_playing(self, chat_id, videoid, title, user, original_chat_id, mention):
        try:
            dur = db[chat_id][0].get("dur", "0:00")
            thumb = await get_thumb(videoid, title, dur, user, chat_id)
            markup = stream_markup(None, chat_id)
            cap = f"▷ **Now Playing**\n━━━━━━━━━━━━━━━━━━\n✧ **Track:** `{title[:30]}`\n✧ **Duration:** `{dur}`\n✧ **By:** {user}"
            if mention: cap += f"\n✧ **Skipped By:** {mention}"
            msg = await app.send_photo(original_chat_id, photo=thumb, caption=cap, reply_markup=InlineKeyboardMarkup(markup))
            db[chat_id][0]["mystic"] = msg
        except: pass

    async def start(self):
        for ass in [self.one, self.two, self.three, self.four, self.five]:
            if ass: await ass.start()

    async def stop(self):
        for ass in [self.one, self.two, self.three, self.four, self.five]:
            if ass:
                try: await ass.stop()
                except: pass

    async def decorators(self):
        def reg(client, ev, h):
            if not client: return
            try:
                m = getattr(client, ev, None)
                if m: m()(h)
            except: pass
        async def sh(_, chat_id: int): await self.stop_stream(chat_id)
        async def eh(client, update: Update):
            cid = getattr(update, 'chat_id', None)
            if cid:
                if cid in self._switching: return
                is_end = False
                if IS_V3:
                    from pytgcalls.types.stream import StreamAudioEnded, StreamVideoEnded, StreamDeleted
                    if isinstance(update, (StreamAudioEnded, StreamVideoEnded, StreamDeleted)): is_end = True
                elif type(update).__name__ in ["StreamAudioEnded", "StreamVideoEnded", "StreamDeleted"]: is_end = True
                if is_end: asyncio.create_task(self.change_stream(client, cid))

        for ass in [self.one, self.two, self.three, self.four, self.five]:
            if not ass: continue
            reg(ass, "on_kicked", sh); reg(ass, "on_closed_voice_chat", sh); reg(ass, "on_left", sh); reg(ass, "on_stream_end", eh)

Nand = Call()
ani = Nand
