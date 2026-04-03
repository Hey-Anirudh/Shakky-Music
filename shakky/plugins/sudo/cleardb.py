import asyncio
from pyrogram import filters
from pyrogram.errors import FloodWait
from shakky import app
from shakky.misc import SUDOERS
import config

CHANNEL_USERNAME = getattr(config, "CHANNEL_USERNAME", "@smashmusicdb")

@app.on_message(filters.command(["cleardb"]) & SUDOERS)
async def cleardb_handler(_, message):
    """Command to clear all messages from the DB channel."""
    mystic = await message.reply_text(f"➲ **Attempting to clear the DB channel ({CHANNEL_USERNAME})...**\n\n✧ This might take some time if there are many songs.")
    
    try:
        count = 0
        deleted_msgs = []
        
        # We delete in batches of 100 to be efficient
        async for msg in app.get_chat_history(CHANNEL_USERNAME):
            deleted_msgs.append(msg.id)
            count += 1
            
            if len(deleted_msgs) == 100:
                try:
                    await app.delete_messages(CHANNEL_USERNAME, deleted_msgs)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    await app.delete_messages(CHANNEL_USERNAME, deleted_msgs)
                except Exception as e:
                    await message.reply_text(f"➲ **Error during deletion batch:** `{e}`")
                
                deleted_msgs = []
                if count % 500 == 0:
                    await mystic.edit_text(f"➲ **Cleanup in progress...**\n\n✧ Deleted so far: `{count}` songs.")

        # Delete any remaining messages in the final batch
        if deleted_msgs:
            try:
                await app.delete_messages(CHANNEL_USERNAME, deleted_msgs)
            except Exception: pass

        # Final cleanup: Delete local cache files (JSON)
        import os
        cache_files = ["song_cache.json", "keyword_cache.json"]
        for cf in cache_files:
            if os.path.exists(cf):
                try: os.remove(cf)
                except: pass

        if count == 0:
            await mystic.edit_text(f"➲ **The DB channel ({CHANNEL_USERNAME}) is already empty.**\n\n✧ Local caches synchronized.")
        else:
            await mystic.edit_text(f"➲ **Successfully cleared the DB channel!**\n\n✧ Total deleted: `{count}` songs.\n✧ Local caches cleared.")
            
    except Exception as e:
        await mystic.edit_text(f"➲ **Failed to clear DB channel:** `{e}`\n\n✧ Make sure the bot is an admin with 'Delete Messages' permission in `{CHANNEL_USERNAME}`.")
