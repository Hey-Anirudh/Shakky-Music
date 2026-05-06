import random
import asyncio
from pyrogram import filters
from shakky import app
from shakky.misc import SUDOERS
from shakky.platforms.Youtube import youtube
from shakky.utils.mongo import add_contributor
import config

CHANNEL_USERNAME = getattr(config, "CHANNEL_USERNAME", "@smashmusicdb")

@app.on_message(filters.command(["addsong"]) & SUDOERS)
async def addsong_handler(_, message):
    if len(message.command) < 2:
        return await message.reply_text("➲ **ADD SONG**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>**Usage:** /addsong [keyword]\nʀᴇᴘʟʏ ᴛᴏ ᴀɴ ᴀᴜᴅɪᴏ ғɪʟᴇ.</blockquote>")
    
    if not message.reply_to_message or not (message.reply_to_message.audio or message.reply_to_message.document):
        return await message.reply_text("➲ **ADD SONG**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>ᴘʟᴇᴀsᴇ ʀᴇᴘʟʏ ᴛᴏ ᴀɴ ᴀᴜᴅɪᴏ ғɪʟᴇ ᴏʀ ᴅᴏᴄᴜᴍᴇɴᴛ.</blockquote>")
    
    keyword = message.text.split(None, 1)[1].strip()
    replied = message.reply_to_message
    
    mystic = await message.reply_text(f"➲ **ADD SONG**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>ᴀᴅᴅɪɴɢ sᴏɴɢ ᴡɪᴛʜ ᴋᴇʏᴡᴏʀᴅ <code>#{keyword}</code> ᴛᴏ ᴅʙ...</blockquote>")
    
    try:
        # Copy the message to the channel
        sent_msg = await replied.copy(
            chat_id=CHANNEL_USERNAME,
            caption=f"#{keyword}"
        )
        # Edit the message to include the ID to match other songs
        await sent_msg.edit_caption(f"Keyword: #{keyword}\n\nAdded via /addsong command\n\nID: db_{sent_msg.id}")
        
        # Track contribution
        await add_contributor(message.from_user.id)
        
        await mystic.edit_text(f"➲ **ADD SONG**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>✧ **Status:** sᴜᴄᴄᴇssғᴜʟʟʏ ᴀᴅᴅᴇᴅ!\n✧ **Keyword:** <code>#{keyword}</code>\n✧ **ID:** <code>db_{sent_msg.id}</code></blockquote>")
    except Exception as e:
        await mystic.edit_text(f"➲ **ADD SONG**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>❌ ғᴀɪʟᴇᴅ ᴛᴏ ᴀᴅᴅ sᴏɴɢ ᴛᴏ ᴅʙ.\n**Error:** <code>{e}</code></blockquote>")
