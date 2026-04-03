import asyncio

from shakky.misc import db
from shakky.utils.database import get_active_chats, is_music_playing


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
                    # Force a skip event
                    import random
                    client = random.choice([ani.one, ani.two, ani.three, ani.four, ani.five])
                    asyncio.create_task(ani.change_stream(client, chat_id))
                    continue
                except:
                    continue
                    
            db[chat_id][0]["played"] += 1


asyncio.create_task(timer())
