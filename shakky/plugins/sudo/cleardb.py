import asyncio
from pyrogram import filters
from pyrogram.errors import FloodWait
from shakky import app
from shakky.misc import SUDOERS
import config

CHANNEL_USERNAME = getattr(config, "CHANNEL_USERNAME", "@smashmusicdb")

@app.on_message(filters.command(["cleardb"]) & SUDOERS)
async def cleardb_handler(_, message):
    """Command to clear all messages from the DB channel using assistant."""
    from shakky.core.userbot import userbot
    
    mystic = await message.reply_text(f"➲ **Assistant is clearing the DB channel ({CHANNEL_USERNAME})...**\n\n✧ This avoids bot rate-limits.")
    
    try:
        assistant = userbot.one
        count = 0
        deleted_msgs = []
        
        # We delete in batches of 100 to be efficient via assistant
        async for msg in assistant.get_chat_history(CHANNEL_USERNAME):
            deleted_msgs.append(msg.id)
            count += 1
            
            if len(deleted_msgs) == 100:
                try:
                    await assistant.delete_messages(CHANNEL_USERNAME, deleted_msgs)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    await assistant.delete_messages(CHANNEL_USERNAME, deleted_msgs)
                except:
                    pass
                
                deleted_msgs = []
                if count % 500 == 0:
                    await mystic.edit_text(f"➲ **Assistant is working...**\n\n✧ Deleted so far: `{count}` items.")

        # Final batch
        if deleted_msgs:
            try: await assistant.delete_messages(CHANNEL_USERNAME, deleted_msgs)
            except: pass

        # Final cleanup: Delete local cache files (JSON)
        import os
        for cf in ["song_cache.json", "keyword_cache.json"]:
            if os.path.exists(cf):
                try: os.remove(cf)
                except: pass

        if count == 0:
            await mystic.edit_text(f"➲ **The DB channel is already empty.**\n\n✧ Assistant confirmed.")
        else:
            await mystic.edit_text(f"➲ **Successfully cleared the DB channel via Assistant!**\n\n✧ Total deleted: `{count}` items.\n✧ Caches cleared.")
            
    except Exception as e:
        await mystic.edit_text(f"➲ **Assistant failed to clear DB:** `{e}`")
