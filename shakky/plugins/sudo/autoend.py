from pyrogram import filters
from pyrogram.types import Message

from shakky import app
from shakky.misc import SUDOERS
from shakky.utils.database import autoend_off, autoend_on


@app.on_message(filters.command("autoend") & SUDOERS)
async def auto_end_stream(_, message: Message):
    usage = "➲ **AUTO END STREAM**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>**Usage:** /autoend [enable|disable]</blockquote>"
    if len(message.command) != 2:
        return await message.reply_text(usage)
    state = message.text.split(None, 1)[1].strip().lower()
    if state == "enable":
        await autoend_on()
        await message.reply_text(
            "➲ **AUTO END**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>ᴀᴜᴛᴏ ᴇɴᴅ sᴛʀᴇᴀᴍ ᴇɴᴀʙʟᴇᴅ.\n\nᴀssɪsᴛᴀɴᴛ ᴡɪʟʟ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ʟᴇᴀᴠᴇ ᴛʜᴇ ᴠɪᴅᴇᴏᴄʜᴀᴛ ᴡʜᴇɴ ɴᴏ ᴏɴᴇ ɪs ʟɪsᴛᴇɴɪɴɢ.</blockquote>"
        )
    elif state == "disable":
        await autoend_off()
        await message.reply_text("➲ **AUTO END**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>ᴀᴜᴛᴏ ᴇɴᴅ sᴛʀᴇᴀᴍ ᴅɪsᴀʙʟᴇᴅ.</blockquote>")
    else:
        await message.reply_text(usage)

