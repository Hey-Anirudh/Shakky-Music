"""
MERGE LOGIC:
- ShrutiMusic had: Call class with self.one through self.five (5 PyTgCalls instances)
  Methods: pause_stream, resume_stream, stop_stream, speedup_stream, seek_stream,
           join_group_call, change_stream, force_stop_stream
- SmashMusic had: Stub Call class (WebApp-only) + notify_webapp on every action
- MERGED: Full PyTgCalls with 5 assistants (ShrutiMusic) + notify_webapp on every
  action (SmashMusic). Both must happen simultaneously.
"""

import asyncio
import os
from datetime import datetime, timedelta
from typing import Union

from pyrogram import Client
from pytgcalls import PyTgCalls, StreamType
from pytgcalls.exceptions import AlreadyJoinedError, NoActiveGroupCall, TelegramServerError
from pytgcalls.types import Update
from pytgcalls.types.input_stream import AudioPiped, AudioVideoPiped
from pytgcalls.types.input_stream.quality import HighQualityAudio, MediumQualityVideo
from pytgcalls.types.stream import StreamAudioEnded

import config
import logging
from shakky import app
logger = logging.getlogger("shakky.call")
from shakky.misc import db
from shakky.utils.database import (
    add_active_chat, add_active_video_chat,
    get_loop, group_assistant,
    is_autoend, music_on,
    remove_active_chat, remove_active_video_chat,
    set_loop
)
from shakky.utils.formatters import check_duration, seconds_to_min, speed_converter
# IMPORTANT: notify_webapp must be handled carefully. If it's missing, import passes over it.
try:
    from shakky.utils.webapp import notify_webapp
except ImportError:
    # Fallback stub in case webapp.py isn't fully set up yet
    async def notify_webapp(*args, **kwargs):
        pass

autoend = {}
counter = {}

async def _clear_(chat_id):
    db[chat_id] = []
    await remove_active_video_chat(chat_id)
    await remove_active_chat(chat_id)
class Call(PyTgCalls):
    def __init__(self):
        from shakky.core.userbot import userbot
        # Initialize base PyTgCalls with assistant 1 (to satisfy _app requirements)
        super().__init__(userbot.one, cache_duration=100)
        # 5 assistant userbot clients (ShrutiMusic architecture)
        self.userbot1 = userbot.one
        self.one = PyTgCalls(self.userbot1, cache_duration=100)

        self.userbot2 = userbot.two
        if self.userbot2:
            self.two = PyTgCalls(self.userbot2, cache_duration=100)
        
        self.userbot3 = userbot.three
        if self.userbot3:
            self.three = PyTgCalls(self.userbot3, cache_duration=100)

        self.userbot4 = userbot.four
        if self.userbot4:
            self.four = PyTgCalls(self.userbot4, cache_duration=100)

        self.userbot5 = userbot.five
        if self.userbot5:
            self.five = PyTgCalls(self.userbot5, cache_duration=100)

    async def join_group_call(self, chat_id: int, file_path: str,
                               video: bool = False, image: str = None):
        """Start VC stream AND notify WebApp."""
        assistant = await group_assistant(self, chat_id)
        if video:
            stream = AudioVideoPiped(file_path, HighQualityAudio(), MediumQualityVideo())
        else:
            stream = AudioPiped(file_path, HighQualityAudio())
        try:
            await assistant.join_group_call(chat_id, stream,
                                             stream_type=StreamType().local_stream)
        except AlreadyJoinedError:
            try:
                await assistant.change_stream(chat_id, stream)
            except Exception as e:
                logger(__name__).error(f"Change stream failed: {e}")
        except Exception as e:
            if "No active group call" in str(e):
                logger(__name__).warning(f"Voice chat not started in {chat_id}. Assistant cannot join.")
            else:
                logger(__name__).error(f"Assistant {assistant} failed to join VC: {e}")
            raise e

        # WebApp sync
        if db.get(chat_id):
            await notify_webapp(chat_id, current_song=db[chat_id][0],
                                queue=db[chat_id][1:], action="play", is_playing=True)

    async def change_stream(self, client, chat_id: int):
        """Change to next song in VC AND sync WebApp."""
        playing = db.get(chat_id)
        if not playing:
            try:
                return await client.leave_group_call(chat_id)
            except:
                return
        file_path = playing[0]["file"]
        video = playing[0].get("streamtype") == "video"
        if video:
            stream = AudioVideoPiped(file_path, HighQualityAudio(), MediumQualityVideo())
        else:
            stream = AudioPiped(file_path, HighQualityAudio())
        await client.change_stream(chat_id, stream)
        await notify_webapp(chat_id, current_song=playing[0],
                            queue=playing[1:], action="skip", is_playing=True)

    async def pause_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.pause_stream(chat_id)
        await notify_webapp(chat_id, action="pause", is_playing=False)

    async def resume_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.resume_stream(chat_id)
        await notify_webapp(chat_id, action="resume", is_playing=True)

    async def stop_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        try:
            await _clear_(chat_id)
            await assistant.leave_group_call(chat_id)
        except:
            pass
        await notify_webapp(chat_id, is_playing=False, action="stop")

    async def seek_stream(self, chat_id: int, file_path: str,
                           to_seek: str, duration: str, mode: str):
        """Seek in VC AND sync WebApp seek position."""
        assistant = await group_assistant(self, chat_id)
        if mode == "video":
            stream = AudioVideoPiped(file_path, HighQualityAudio(), MediumQualityVideo(),
                                      additional_ffmpeg_parameters=f"-ss {to_seek}")
        else:
            stream = AudioPiped(file_path, HighQualityAudio(),
                                 additional_ffmpeg_parameters=f"-ss {to_seek}")
        await assistant.change_stream(chat_id, stream)
        # Convert to_seek string "mm:ss" back to seconds for WebApp
        seek_seconds = sum(int(x) * 60**i for i, x in
                           enumerate(reversed(to_seek.split(":"))))
        await notify_webapp(chat_id, action="seek", seek_to=seek_seconds, is_playing=True)

    async def speedup_stream(self, chat_id: int, file_path: str,
                              speed: str, playing: list):
        """Apply speed via ffmpeg (ShrutiMusic) AND notify WebApp."""
        assistant = await group_assistant(self, chat_id)
        if str(speed) != "1.0":
            vs_map = {"0.5": 2.0, "0.75": 1.35, "1.5": 0.68, "2.0": 0.5}
            vs = vs_map.get(str(speed), 1.0)
            base = os.path.basename(file_path)
            chatdir = os.path.join(os.getcwd(), "playback", str(speed))
            os.makedirs(chatdir, exist_ok=True)
            out = os.path.join(chatdir, base)
            if not os.path.isfile(out):
                proc = await asyncio.create_subprocess_shell(
                    f"ffmpeg -i {file_path} -filter:v setpts={vs}*PTS "
                    f"-filter:a atempo={speed} {out}"
                )
                await proc.communicate()
            file_path = out
            db[chat_id][0]["speed_path"] = file_path
        stream = AudioPiped(file_path, HighQualityAudio())
        await assistant.change_stream(chat_id, stream)
        # Keep WebApp in sync — update elapsed based on current position
        current = db[chat_id][0] if db.get(chat_id) else None
        if current:
            await notify_webapp(chat_id, current_song=current,
                                queue=db[chat_id][1:], action="update", is_playing=True)

    async def force_stop_stream(self, chat_id: int):
        """Emergency stop all 5 assistants."""
        for attr in ["one", "two", "three", "four", "five"]:
            try:
                instance = getattr(self, attr, None)
                if instance:
                    await instance.leave_group_call(chat_id)
            except:
                pass
        await _clear_(chat_id)
        await notify_webapp(chat_id, is_playing=False, action="stop")

    async def start(self):
        logger.info("Starting PyTgCalls Clients...\n")
        await self.one.start()
        for attr in ["two", "three", "four", "five"]:
            instance = getattr(self, attr, None)
            if instance:
                try:
                    await instance.start()
                except:
                    pass

    async def decorators(self):
        @self.one.on_kicked()
        @self.one.on_closed_voice_chat()
        @self.one.on_left()
        async def stream_services_handler(client, chat_id: int):
            await self.stop_stream(chat_id)

        @self.one.on_stream_end()
        async def stream_end_handler(client, update: Update):
            if not isinstance(update, StreamAudioEnded):
                return
            await self.change_stream(client, update.chat_id)

        # Apply to others if they exist
        for attr in ["two", "three", "four", "five"]:
            instance = getattr(self, attr, None)
            if instance:
                @instance.on_kicked()
                @instance.on_closed_voice_chat()
                @instance.on_left()
                async def stream_services_handler_multi(client, chat_id: int):
                    await self.stop_stream(chat_id)

                @instance.on_stream_end()
                async def stream_end_handler_multi(client, update: Update):
                    if not isinstance(update, StreamAudioEnded):
                        return
                    await self.change_stream(client, update.chat_id)

Nand = Call()  # Keep ShrutiMusic's alias
ani = Nand     # Keep SmashMusic's alias — both point to the same instance
