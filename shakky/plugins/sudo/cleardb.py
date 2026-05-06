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
    
    mystic = await message.reply_text(f"➲ **CLEAR DB SYSTEM**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>✧ **Action:** ᴄʟᴇᴀʀɪɴɢ {CHANNEL_USERNAME} ᴠɪᴀ ᴀssɪsᴛᴀɴᴛ.\n✧ **Status:** ɪɴ ᴘʀᴏɢʀᴇss...</blockquote>")
    
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
                    await mystic.edit_text(f"➲ **CLEAR DB SYSTEM**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>✧ **Action:** ᴄʟᴇᴀʀɪɴɢ {CHANNEL_USERNAME}\n✧ **Deleted:** <code>{count}</code> ɪᴛᴇᴍs...</blockquote>")

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
            await mystic.edit_text(f"➲ **CLEAR DB SYSTEM**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>✧ ᴛʜᴇ ᴅʙ ᴄʜᴀɴɴᴇʟ ɪs ᴀʟʀᴇᴀᴅʏ ᴇᴍᴘᴛʏ.</blockquote>")
        else:
            await mystic.edit_text(f"➲ **CLEAR DB SYSTEM**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>✧ **Status:** sᴜᴄᴄᴇssғᴜʟʟʏ ᴄʟᴇᴀʀᴇᴅ!\n✧ **Total Deleted:** <code>{count}</code>\n✧ **Caches:** ᴄʟᴇᴀʀᴇᴅ.</blockquote>")
            
    except Exception as e:
        await mystic.edit_text(f"➲ **CLEAR DB SYSTEM**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>✧ **Error:** ᴀssɪsᴛᴀɴᴛ ғᴀɪʟᴇᴅ ᴛᴏ ᴄʟᴇᴀʀ ᴅʙ.\n✧ **Details:** <code>{e}</code></blockquote>")
