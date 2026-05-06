from pyrogram import filters

from shakky import app
from shakky.misc import SUDOERS
from shakky.utils.database import add_off, add_on
from shakky.utils.decorators.language import language


@app.on_message(filters.command(["logger"]) & SUDOERS)
@language
async def logger(client, message, _):
    usage = "➲ **BOT LOGGER**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>**Usage:** /logger [enable|disable]</blockquote>"
    if len(message.command) != 2:
        return await message.reply_text(usage)
    state = message.text.split(None, 1)[1].strip().lower()
    if state == "enable":
        await add_on(2)
        await message.reply_text("➲ **BOT LOGGER**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>ʟᴏɢɢɪɴɢ ʜᴀs ʙᴇᴇɴ ᴇɴᴀʙʟᴇᴅ. ᴀʟʟ ᴀᴄᴛɪᴠɪᴛɪᴇs ᴡɪʟʟ ʙᴇ ʟᴏɢɢᴇᴅ.</blockquote>")
    elif state == "disable":
        await add_off(2)
        await message.reply_text("➲ **BOT LOGGER**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>ʟᴏɢɢɪɴɢ ʜᴀs ʙᴇᴇɴ ᴅɪsᴀʙʟᴇᴅ.</blockquote>")
    else:
        await message.reply_text(usage)
