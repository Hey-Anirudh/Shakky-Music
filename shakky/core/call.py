import asyncio
import logging
import os
import time
from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup

# ─── PyTgCalls Version Compatibility Layer ──────────────────
try:
    # --- Modern Era (v1.0 - v3.0+) ---
    from pytgcalls import PyTgCalls, StreamType
    from pytgcalls.types import AudioPiped, AudioVideoPiped, Update
    from pytgcalls.types.stream import HighQualityAudio, MediumQualityVideo
    
    # Check if it's v3 (has join_group_call and change_stream on the main class)
    IS_LEGACY = False
    
    # We create a simple wrapper to ensure consistent method names if needed,
    # but v3's native change_stream and join_group_call are exactly what we want.
    class PyTgCallsWrapper(PyTgCalls):
        def __init__(self, client, **kwargs):
            self._parent = kwargs.pop("parent", None)
            super().__init__(client, **kwargs)
        
        async def change_stream(self, chat_id, stream):
            """Robust stream switcher for v3."""
            try:
                # v3 native change_stream is very reliable
                return await super().change_stream(chat_id, stream)
            except Exception as e:
                logging.getLogger(__name__).error(f"v3 change_stream failed: {e}")
                # Fallback: Stop and Re-join (Heavy but works)
                try: await self.leave_group_call(chat_id)
                except: pass
                return await self.join_group_call(chat_id, stream)

    # Use the wrapper as our PyTgCalls class
    PyTgCalls = PyTgCallsWrapper

except ImportError:
    # --- Legacy Era (v0.9.x) ---
    IS_LEGACY = True
    try:
        from pytgcalls import GroupCallFactory
        
        class PyTgCalls:
            """Shim to make v0.9.x look like v3.x for the rest of the code."""
            def __init__(self, client, **kwargs):
                self._factory = GroupCallFactory(client)
                self._call = self._factory.get_group_call()
                self._parent = kwargs.get("parent")
                # Direct mappings
                self.start = self._call.start
                self.stop = self._call.stop
                self.join = self._call.join
                self.leave = self._call.leave
                self.start_audio = self._call.start_audio
                self.pause_stream = self._call.pause_stream
                self.resume_stream = self._call.resume_stream
                self.join_group_call = self._call.join # In v0.9 join is basically join_group_call
                self.leave_group_call = self._call.leave
            
            async def change_stream(self, chat_id, stream):
                """Legacy Pipe Engine: Re-spawns FFmpeg for each sync."""
                if isinstance(stream, str) and stream.startswith("ffmpeg"):
                    # 1. Stop current
                    if hasattr(self._call, "stop_audio"):
                        try: await self._call.stop_audio()
                        except: pass
                    
                    # 2. Cleanup old FFmpeg
                    if self._parent and chat_id in self._parent._chat_procs:
                        try:
                            p = self._parent._chat_procs[chat_id]
                            p.kill()
                            await p.wait()
                        except: pass
                    
                    # 3. Setup new pipe
                    pipe_path = os.path.abspath(f"downloads/p_{abs(chat_id)}_{int(time.time()*1000)}.pcm")
                    if hasattr(os, "mkfifo"):
                        try: os.mkfifo(pipe_path)
                        except: pass
                    
                    # 4. Start FFmpeg
                    import shlex
                    cmd = stream.replace("pipe:1", pipe_path)
                    args = shlex.split(cmd)
                    proc = await asyncio.create_subprocess_exec(
                        *args,
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL
                    )
                    if self._parent: self._parent._chat_procs[chat_id] = proc
                    
                    # 5. Buffer and Play
                    await asyncio.sleep(2.0)
                    try:
                        return await self._call.start_audio(pipe_path)
                    except Exception as e:
                        logging.getLogger(__name__).error(f"Legacy Sync Failed: {e}")
                        return False
                
                # Standard file path
                if hasattr(self._call, "stop_audio"):
                    try: await self._call.stop_audio()
                    except: pass
                path = getattr(stream, 'path', stream)
                return await self._call.start_audio(path)

    except ImportError:
        raise ImportError("Critical: No compatible PyTgCalls version found.")

    # Legacy Dummies for Type Safety
    class AudioPiped: 
        def __init__(self, p, **kwargs): 
            self.path = p
            self.filters = kwargs.get("additional_ffmpeg_parameters", "")
    class AudioVideoPiped(AudioPiped): pass
    class HighQualityAudio: pass
    class MediumQualityVideo: pass
    class Update: pass
    class StreamType: pulse = "pulse"

# --- 🎭 Premium Spatial Audio Engine (v2.0) ---
class VoiceFilter:
    """Refined registry for professional audio/video effects."""
    
    PRESETS = {
        "bass_boost": "equalizer=f=60:width_type=h:width=50:g=15,equalizer=f=120:width_type=h:width=100:g=8",
        "8d_audio": "apulsator=mode=sine:hz=0.1:amount=0.9,aecho=0.8:0.88:60:0.4",
        "nightcore": "asetrate=48000*1.25,aresample=48000,atempo=1.0",
        "slowed_reverb": "asetrate=48000*0.8,aresample=48000,aecho=0.8:0.9:1000:0.3",
        "reverb": "aecho=0.8:0.88:60:0.4",
        "fade_in": "afade=t=in:ss=0:d=2",
    }

    @classmethod
    def build_ffmpeg_args(cls, payload: dict) -> str:
        """Translates payload to FFmpeg filter string."""
        if not payload: return ""
        filters = []
        
        # 1. Base Effects
        af = payload.get("af")
        if af and af in cls.PRESETS:
            filters.append(cls.PRESETS[af])
        elif af:
            filters.append(af) # Raw string

        # 2. Variable Speed (TEMPO)
        speed = payload.get("speed", 1.0)
        try:
            speed = float(speed)
            if speed != 1.0:
                filters.append(f"atempo={speed}")
        except: pass
        
        return ",".join(filters)

# Types that might be missing in some environments
if "StreamAudioEnded" not in globals():
    class StreamAudioEnded: pass

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
            return PyTgCalls(userbot, parent=self, cache_duration=100)

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
        self._active_effects = {} # chat_id -> payload
        self._switching = set() # Tracks chats currently re-syncing
        self._chat_procs = {} # chat_id -> FFmpeg subprocess (Legacy only)

    def get_lock(self, chat_id: int):
        if chat_id not in self._locks: self._locks[chat_id] = asyncio.Lock()
        return self._locks[chat_id]

    def build_stream(self, path, video, payload=None, duration=0, chat_id=None):
        """Constructs the stream path or object with premium filters."""
        if not payload: payload = {}
        # Merge with global chat effects
        merged = {**(self._active_effects.get(chat_id, {})), **payload}
        filters = VoiceFilter.build_ffmpeg_args(merged)
        
        ss = merged.get("ss", 0)
        to = merged.get("to", "")
        
        if IS_LEGACY and (filters or ss != 0):
            # 🚀 Legacy Pipe Engine (Refined for Windows/Stability)
            seek_arg = f"-ss {ss}"
            if to: seek_arg += f" -to {to}"
            filter_arg = f"-af {filters}" if filters else ""
            return f'ffmpeg -y -loglevel panic -re {seek_arg} -i "{path}" {filter_arg} -vn -f s16le -ac 2 -ar 48000 pipe:1'

        # Modern Pytgcalls (v1.0+)
        # IMPORTANT: No manual quotes for additional_ffmpeg_parameters! 
        ffmpeg_args = f"-ss {ss}"
        if to: ffmpeg_args += f" -to {to}"
        if filters: ffmpeg_args += f" -af {filters}"

        if video:
            return AudioVideoPiped(path, HighQualityAudio(), MediumQualityVideo(), additional_ffmpeg_parameters=ffmpeg_args)
        return AudioPiped(path, HighQualityAudio(), additional_ffmpeg_parameters=ffmpeg_args)

    async def _sync_stream(self, chat_id, playing):
        """Core internal method to re-initialize the stream with current state."""
        track = playing[0]
        start_time = track.get("start_time", time.time())
        current_pos = int(time.time() - start_time)
        if current_pos < 0: current_pos = 0
        
        payload = {"ss": current_pos}
        stream = self.build_stream(track["file"], (track["streamtype"] == "video"), payload, track.get("seconds", 0), chat_id=chat_id)
        
        ass = await group_assistant(self, chat_id)
        try:
            await ass.change_stream(chat_id, stream)
        except Exception as e:
            LOGGER.error(f"Sync stream failed: {e}")

    async def apply_audio_filter(self, chat_id: int, filter_key: str, playing: list):
        """Applies a premium audio filter in real-time."""
        if not playing: return
        self._switching.add(chat_id)
        try:
            if chat_id not in self._active_effects: self._active_effects[chat_id] = {}
            if filter_key: self._active_effects[chat_id]["af"] = filter_key
            else: self._active_effects[chat_id].pop("af", None)
            await self._sync_stream(chat_id, playing)
        finally:
            await asyncio.sleep(1) # Reduced cooldown
            self._switching.discard(chat_id)

    async def speedup_stream(self, chat_id: int, speed: float, playing: list):
        """Modifies playback speed in real-time."""
        if not playing: return
        self._switching.add(chat_id)
        try:
            if chat_id not in self._active_effects: self._active_effects[chat_id] = {}
            self._active_effects[chat_id]["speed"] = speed
            await self._sync_stream(chat_id, playing)
        finally:
            await asyncio.sleep(1)
            self._switching.discard(chat_id)

    async def stop_stream(self, chat_id):
        ass = await group_assistant(self, chat_id)
        try:
            if IS_LEGACY: await ass.leave_group_call(chat_id)
            else: await ass.leave_group_call(chat_id)
        except: pass
        await _clear_(chat_id)
        await notify_webapp(chat_id, action="stop")

    async def _send_now_playing(self, chat_id, videoid, title, user, original_chat_id, mention):
        """Dynamic Aura Card: Premium Now Playing UI."""
        try:
            track = db[chat_id][0]
            dur = track.get("dur", "0:00")
            thumb = await get_thumb(videoid, title, dur, user, chat_id)
            markup = stream_markup(None, chat_id)
            
            current_effect = self._active_effects.get(chat_id, {}).get("af")
            effect_text = f"\n✧ **Effect:** `{' '.join(current_effect.split('_')).title()}`" if current_effect else ""
            
            caption = (
                f"<blockquote><b>▷ Now Playing</b></blockquote>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"✧ **Track:** <code>{title[:30]}</code>\n"
                f"✧ **Duration:** <code>{dur}</code>\n"
                f"✧ **By:** {user}"
                f"{effect_text}"
            )
            if mention: caption += f"\n✧ **Skipped By:** {mention}"
                
            msg = await app.send_photo(original_chat_id, photo=thumb, caption=caption, reply_markup=InlineKeyboardMarkup(markup))
            track["mystic"] = msg
        except Exception as e:
            LOGGER.error(f"Aura Card send failed: {e}")

    async def change_stream(self, client, chat_id, skip_pop=False):
        """Main queue transition logic with Auto-DJ."""
        check = db.get(chat_id)
        if not check: return
        
        popped = None
        if not skip_pop:
            popped = check.pop(0)
            
        if not check:
            # --- Smart Auto-DJ Logic ---
            try:
                from shakky.platforms import youtube
                last_track = popped
                if last_track and last_track.get("vidid"):
                    related = await youtube.get_related(last_track["vidid"], last_track["title"])
                    if related:
                        await app.send_message(chat_id, text=f"✨ **Auto-DJ: Keeping the vibe alive with {related['title']}**")
                        from shakky.utils.stream.stream import put_queue
                        await put_queue(
                            chat_id, last_track["chat_id"], f"vid_{related['vidid']}",
                            related['title'], related['duration'], "Auto-DJ",
                            related['vidid'], 0, "audio"
                        )
                        check = db.get(chat_id)
                        if check: return await self.change_stream(client, chat_id, skip_pop=True)
            except Exception as e:
                LOGGER.error(f"Auto-DJ failed: {e}")

            await _clear_(chat_id)
            try: await client.leave_group_call(chat_id)
            except: pass
            return

        track = check[0]
        videoid = track["vidid"]
        title = track["title"]
        user = track["by"]
        original_chat_id = track["chat_id"]
        
        # Reset effects for new song? (Usually better for UX)
        self._active_effects.pop(chat_id, None)
        
        stream = self.build_stream(track["file"], (track["streamtype"] == "video"), chat_id=chat_id)
        ass = await group_assistant(self, chat_id)
        
        try:
            await ass.change_stream(chat_id, stream)
        except Exception as e:
            return await client.send_message(original_chat_id, text=f"❌ Error switching stream: {e}")
            
        await self._send_now_playing(chat_id, videoid, title, user, original_chat_id, None)

    async def start(self):
        for ass in [self.one, self.two, self.three, self.four, self.five]:
            if ass: await ass.start()

    async def stop_all(self):
        for ass in [self.one, self.two, self.three, self.four, self.five]:
            if ass: await ass.stop()

Nand = Call()
