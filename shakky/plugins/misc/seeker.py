import asyncio
import logging

from shakky.misc import db
from shakky.utils.database import get_active_chats, is_music_playing

LOGGER = logging.getLogger(__name__)

async def timer():
    while not await asyncio.sleep(1):
        active_chats = await get_active_chats()
        for chat_id in active_chats:
            if not await is_music_playing(chat_id):
                continue
            playing = db.get(chat_id)
            if not playing:
                continue
            duration = int(playing[0]["seconds"])
            if duration == 0:
                continue
            # Removed the time-based force skip.
            # We now rely entirely on pytgcalls' natural on_stream_end event 
            # to transition songs, which fires when the ffmpeg audio pipe actually closes.
            # This prevents songs from being cut off early.
            db[chat_id][0]["played"] += 1


asyncio.create_task(timer())

