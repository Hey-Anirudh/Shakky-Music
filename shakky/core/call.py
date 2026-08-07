import asyncio
import os
import time
import re
import logging
from datetime import datetime, timedelta
from typing import Union

from pyrogram import Client
from pyrogram.enums import ChatType, ChatMemberStatus
from pyrogram.errors import (
    PeerIdInvalid,
    ChatWriteForbidden,
    ChatAdminRequired,
    InviteRequestSent,
    UserAlreadyParticipant,
    UserNotParticipant,
)
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import pytgcalls
from pytgcalls.exceptions import NoActiveGroupCall

# 🤖 Universal Core Switch (ARM VPS Fix)
IS_V3 = False
IS_LEGACY = False

# --- PyTgCalls v2 (installed: play()/leave_call()/on_update(filters)) ---
IS_V3 = False
IS_LEGACY = False

from pytgcalls import PyTgCalls  # noqa: E402
from pytgcalls.exceptions import NoActiveGroupCall  # noqa: E402
from pytgcalls.types import (  # noqa: E402
    MediaStream,
    AudioQuality,
    VideoQuality,
    StreamEnded,
    ChatUpdate,
    Update,
)
from pytgcalls.filters import stream_end, chat_update  # noqa: E402


class _V2Adapter:
    """Adapts the installed pytgcalls v2 API (play / leave_call / on_update)
    to the v1/v3-style surface call.py expects (join_group_call, pause_stream,
    change_stream, stream-end + chat decorators). Downstream methods unchanged."""

    def __init__(self, core):
        self._core = core

    async def start(self):
        await self._core.start()

    async def stop(self):
        try:
            await self._core.stop()
        except Exception:
            pass

    async def join_group_call(self, chat_id, stream, *a, **k):
        return await self._core.play(chat_id, stream)

    async def change_stream(self, chat_id, stream):
        return await self._core.play(chat_id, stream)

    async def pause_stream(self, chat_id):
        return await self._core.pause(chat_id)

    async def resume_stream(self, chat_id):
        return await self._core.resume(chat_id)

    async def leave(self, chat_id):
        await self._core.leave_call(chat_id)

    async def leave_group_call(self, chat_id):
        await self._core.leave_call(chat_id)

    async def stop_stream(self, chat_id):
        await self._core.leave_call(chat_id)

    def on_stream_start(self):
        return lambda f: f

    def _on_chat(self, status, func):
        @self._core.on_update(chat_update(status))
        async def _h(client, update):
            await func(client, update.chat_id)
        return func

    def on_kicked(self):
        return lambda f: self._on_chat(ChatUpdate.Status.KICKED, f)

    def on_closed_voice_chat(self):
        return lambda f: self._on_chat(ChatUpdate.Status.CLOSED_VOICE_CHAT, f)

    def on_left(self):
        return lambda f: self._on_chat(ChatUpdate.Status.LEFT_CALL, f)

    def on_stream_end(self):
        def deco(func):
            @self._core.on_update(stream_end())
            async def _h(client, update):
                await func(self, update)
            return func
        return deco


# Placeholders kept so any stray references in this module still resolve.
class StreamAudioEnded: pass
class StreamVideoEnded: pass
class StreamDeleted: pass

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
            return _V2Adapter(PyTgCalls(userbot, cache_duration=100))

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
        self._switching = set() 
        self._chat_procs = {} # chat_id -> FFmpeg subprocess

    def get_lock(self, chat_id: int):
        if chat_id not in self._locks: self._locks[chat_id] = asyncio.Lock()
        return self._locks[chat_id]

    def build_stream(self, path, video, payload=None, duration=0, chat_id=None):
        """Constructs the stream path or object."""
        payload = payload or {}
        ss = payload.get("ss", 0)

        # Live audio effect (EQ / speed / nightcore etc.) + crossfade fade-in
        af_filter = ""
        if chat_id:
            try:
                from shakky.utils.effects import build_af as _chat_af
                af_filter = _chat_af(chat_id, ss=ss)
            except Exception:
                af_filter = ""

        if IS_LEGACY:
            af_args = f' -af "{af_filter}"' if af_filter else ""
            if ss != 0:
                re_arg = "-re" if str(path).startswith("http") else ""
                return f'ffmpeg -y -loglevel panic {re_arg} -ss {ss} -i "{path}" -vn{af_args} -f s16le -ac 2 -ar 48000 pipe:1'
            return f'ffmpeg -y -loglevel panic -i "{path}" -vn{af_args} -f s16le -ac 2 -ar 48000 pipe:1'

        ffmpeg_args = f"-ss {ss}" + (f' -af "{af_filter}"' if af_filter else "")
        if video:
            return MediaStream(
                path,
                audio_parameters=AudioQuality.HIGH,
                video_parameters=VideoQuality.HD_720p,
                ffmpeg_parameters=ffmpeg_args,
            )
        return MediaStream(
            path,
            audio_parameters=AudioQuality.HIGH,
            ffmpeg_parameters=ffmpeg_args,
            video_flags=MediaStream.Flags.IGNORE,
        )

    async def join_call(self, chat_id, original_chat_id, link, video=None, image=None, payload=None):
        assistant = await group_assistant(self, chat_id)
        userbot = self.userbot1 if assistant == self.one else (self.userbot2 if assistant == self.two else (self.userbot3 if assistant == self.three else (self.userbot4 if assistant == self.four else self.userbot5)))
        
        stream = self.build_stream(link, video, payload, payload.get("seconds", 0) if payload else 0, chat_id=chat_id)

        invited = False
        try:
            if not userbot.me:
                await userbot.get_me()
            try:
                await app.get_chat_member(chat_id, userbot.me.id)
                invited = True
                LOGGER.info(f"[join] Assistant {userbot.me.id} already a member of {chat_id}")
            except UserNotParticipant:
                await app.add_chat_members(chat_id, userbot.me.id)
                invited = True
                LOGGER.info(f"[join] Invited assistant {userbot.me.id} into {chat_id}")
        except Exception as e:
            LOGGER.warning(f"[join] Could not auto-invite assistant into {chat_id}: {e}")
            invitelink = None
            try:
                invitelink = await app.export_chat_invite_link(chat_id)
            except ChatAdminRequired:
                LOGGER.warning(f"[join] Bot is not an admin in {chat_id} — cannot create an invite link. "
                               f"Add {config.ASSUSERNAME} manually or promote the bot to admin.")
            except Exception as e2:
                LOGGER.warning(f"[join] Could not create invite link for {chat_id}: {e2}")
            if invitelink:
                if invitelink.startswith("https://t.me/+"):
                    invitelink = invitelink.replace("https://t.me/+", "https://t.me/joinchat/")
                try:
                    await userbot.join_chat(invitelink)
                    invited = True
                    LOGGER.info(f"[join] Assistant {userbot.me.id} joined {chat_id} via invite link")
                except InviteRequestSent:
                    try:
                        await app.approve_chat_join_request(chat_id, userbot.me.id)
                        invited = True
                        LOGGER.info(f"[join] Approved assistant {userbot.me.id} join request for {chat_id}")
                    except Exception as e2:
                        LOGGER.warning(f"[join] Could not approve assistant join request: {e2}")
                except UserAlreadyParticipant:
                    invited = True
                except Exception as e2:
                    LOGGER.warning(f"[join] Invite-link join failed: {e2}")

        if invited:
            for _ in range(3):
                try:
                    await userbot.get_chat(chat_id)
                    break
                except Exception:
                    await asyncio.sleep(1)

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
            except Exception as e:
                msg = str(e).upper()
                if "ALREADY" in msg or "JOINED" in msg or "CALL_BUSY" in msg:
                    joined = True; break
                LOGGER.error(f"[join] Attempt {attempt} failed: {e}")
                await asyncio.sleep(1)

        if joined:
            await add_active_chat(chat_id)
            await music_on(chat_id)
            if video: await add_active_video_chat(chat_id)
        else:
            hint = ""
            if not invited:
                hint = (
                    f"\n\nℹ️ I couldn't add my assistant **{config.ASSUSERNAME}** to this chat automatically."
                    f"\n➥ Please add **{config.ASSUSERNAME}** to this group manually (promote it to admin if possible), then try again."
                )
            try: await app.send_message(original_chat_id, text=f"❌ **Failed to join Voice Chat.**{hint}")
            except Exception: pass

    async def seek_stream(self, chat_id, to_seek, *args, **kwargs):
        playing = db.get(chat_id)
        if not playing: return
        if isinstance(to_seek, str): to_seek = time_to_seconds(to_seek)
        
        self._switching.add(chat_id)
        try:
            playing[0]["start_time"] = time.time() - to_seek
            await self._sync_stream(chat_id, playing)
        finally:
            await asyncio.sleep(2)
            self._switching.discard(chat_id)

    async def resync_stream(self, chat_id, refresh_time: bool = True):
        """Re-build the current stream with the latest effects/filters
        (e.g. after /equalizer changes) without restarting the track."""
        playing = db.get(chat_id)
        if not playing:
            return False
        if refresh_time:
            playing[0]["start_time"] = time.time()
        await self._sync_stream(chat_id, playing)
        return True

    async def _sync_stream(self, chat_id, playing):
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
            LOGGER.error(f"Sync stream failed: {e}")

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
                await notify_webapp(chat_id, is_playing=False, action="stop")
                return

            if not skip_pop:
                loop = await get_loop(chat_id)
                if loop == 0:
                    popped = check.pop(0)
                    await auto_clean(popped)
                else: await set_loop(chat_id, loop - 1)
                
                if not check:
                    try:
                        from shakky.utils.database import is_autodj
                        if await is_autodj(chat_id):
                            from shakky.platforms import youtube
                            last_track = popped if 'popped' in locals() else None
                            if last_track and last_track.get("vidid"):
                                related = await youtube.get_related(last_track["vidid"], last_track["title"])
                                if related:
                                    await app.send_message(chat_id, text=f"✨ **Auto-DJ: Playing {related['title']}**")
                                    from shakky.utils.stream.stream import put_queue
                                    await put_queue(chat_id, last_track["chat_id"], f"vid_{related['vidid']}", related['title'], related['duration'], "Auto-DJ", related['vidid'], 0, "audio")
                                    check = db.get(chat_id)
                                    if check: return await self.change_stream(client, chat_id, skip_pop=True)
                    except: pass
                    await _clear_(chat_id)
                    try:
                        if IS_LEGACY: await client.leave(chat_id)
                        else: await client.leave_group_call(chat_id)
                    except: pass
                    await notify_webapp(chat_id, is_playing=False, action="stop")
                    return

            track = check[0]
            queued = track["file"]
            title = track["title"].title()
            videoid = track["vidid"]
            video = (track["streamtype"] == "video")
            is_url = isinstance(queued, str) and queued.startswith(("http://", "https://"))
            
            if "vid_" in queued and not is_url and not os.path.exists(queued) and videoid:
                try:
                    from shakky.platforms import YouTube as YT
                    file_path, _ = await asyncio.wait_for(YT.download(videoid, video=video, raw_query=title, chat_id=chat_id), timeout=60)
                    if file_path: queued = file_path; track["file"] = file_path
                except: queued = None
            
            if not queued or (not is_url and not os.path.exists(queued)):
                if len(check) > 0:
                    check.pop(0)
                    if len(check) > 0: return await self.change_stream(client, chat_id, skip_pop=True)
                await _clear_(chat_id)
                try:
                    if IS_LEGACY: await client.leave(chat_id)
                    else: await client.leave_group_call(chat_id)
                except: pass
                await notify_webapp(chat_id, is_playing=False, action="stop")
                return

            stream = self.build_stream(queued, video, {}, track.get("seconds", 0), chat_id=chat_id)
            try:
                track["start_time"] = time.time()
                await client.change_stream(chat_id, stream)
            except:
                if len(check) > 0:
                    check.pop(0)
                    if len(check) > 0: return await self.change_stream(client, chat_id, skip_pop=True)
                await _clear_(chat_id)
                try:
                    if IS_LEGACY: await client.leave(chat_id)
                    else: await client.leave_group_call(chat_id)
                except: pass
                await notify_webapp(chat_id, is_playing=False, action="stop")
                return

            asyncio.create_task(self._send_now_playing(chat_id, videoid, title, track["by"], track["chat_id"], mention))
            asyncio.create_task(notify_webapp(chat_id, current_song=track, queue=check[1:] if len(check) > 1 else [], is_playing=True, action="update"))

    async def pause_stream(self, chat_id):
        ass = await group_assistant(self, chat_id)
        try:
             if not IS_LEGACY: await ass.pause_stream(chat_id)
        except: pass

    async def resume_stream(self, chat_id):
        ass = await group_assistant(self, chat_id)
        try:
             if not IS_LEGACY: await ass.resume_stream(chat_id)
        except: pass

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

    async def stop_stream_force(self, chat_id):
        return await self.stop_stream(chat_id)

    async def _send_now_playing(self, chat_id, videoid, title, user, original_chat_id, mention):
        try:
            track = db[chat_id][0]
            dur = track.get("dur", "0:00")
            artist = track.get("artist") or user
            thumb = await get_thumb(videoid, title, dur, artist, chat_id)
            markup = stream_markup(None, chat_id)
            
            caption = (
                f"<blockquote><b>▷ Now Playing</b></blockquote>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"✧ **Track:** <code>{title[:30]}</code>\n"
                f"✧ **Duration:** <code>{dur}</code>\n"
                f"✧ **By:** {user}"
            )
            if mention: caption += f"\n✧ **Skipped By:** {mention}"
            msg = await app.send_photo(original_chat_id, photo=thumb, caption=caption, reply_markup=InlineKeyboardMarkup(markup))
            track["mystic"] = msg
        except: pass

    async def start(self):
        for ass in [self.one, self.two, self.three, self.four, self.five]:
            if ass: await ass.start()

    async def stop(self):
        for ass in [self.one, self.two, self.three, self.four, self.five]:
            if ass:
                try: await ass.stop()
                except: pass

    async def _play_podcast_intro(self, chat_id, next_track):
        """Removed: AI Podcast feature has been removed."""
        return

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
                name = type(update).__name__
                is_end = isinstance(update, StreamEnded) or name in ["StreamAudioEnded", "StreamVideoEnded", "StreamDeleted"]
                if is_end: asyncio.create_task(self.change_stream(client, cid))

        for ass in [self.one, self.two, self.three, self.four, self.five]:
            if not ass: continue
            reg(ass, "on_kicked", sh); reg(ass, "on_closed_voice_chat", sh); reg(ass, "on_left", sh); reg(ass, "on_stream_end", eh)

Nand = Call()
ani = Nand
