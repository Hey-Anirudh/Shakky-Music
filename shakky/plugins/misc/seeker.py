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
            
            # Auto-Recovery: if song hangs past its duration
            if db[chat_id][0]["played"] >= duration + 4:
                try:
                    from shakky.core.call import ani
                    from shakky.utils.database import group_assistant
                    # Use the correct assistant for this chat
                    assistant = await group_assistant(ani, chat_id)
                    # Clear the anti-duplicate cooldown so watchdog skip always works
                    ani._last_skip.pop(chat_id, None)
                    LOGGER.info(f"[watchdog] Song hung past duration in {chat_id} (played={db[chat_id][0]['played']}, dur={duration}). Force-skipping.")
                    asyncio.create_task(ani.change_stream(assistant, chat_id))
                    continue
                except Exception as e:
                    LOGGER.error(f"[watchdog] Recovery failed for {chat_id}: {e}")
                    continue
                    
            db[chat_id][0]["played"] += 1


asyncio.create_task(timer())

