from pyrogram import filters
from pyrogram.types import Message

from shakky import app
from shakky.misc import SUDOERS
from shakky.utils.database import (
    get_lang,
    is_maintenance,
    maintenance_off,
    maintenance_on,
)
from strings import get_string


@app.on_message(filters.command(["maintenance"]) & SUDOERS)
async def maintenance(client, message: Message):
    try:
        language = await get_lang(message.chat.id)
        _ = get_string(language)
    except:
        _ = get_string("en")
    usage = "➲ **MAINTENANCE MODE**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>**Usage:** /maintenance [enable|disable]</blockquote>"
    if len(message.command) != 2:
        return await message.reply_text(usage)
    state = message.text.split(None, 1)[1].strip().lower()
    if state == "enable":
        if await is_maintenance() is False:
            await message.reply_text("➲ **MAINTENANCE**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ ɪs ᴀʟʀᴇᴀᴅʏ ᴇɴᴀʙʟᴇᴅ.</blockquote>")
        else:
            await maintenance_on()
            await message.reply_text(f"➲ **MAINTENANCE**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ ʜᴀs ʙᴇᴇɴ ᴇɴᴀʙʟᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ ʙʏ {app.mention}.</blockquote>")
    elif state == "disable":
        if await is_maintenance() is False:
            await maintenance_off()
            await message.reply_text(f"➲ **MAINTENANCE**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ ʜᴀs ʙᴇᴇɴ ᴅɪsᴀʙʟᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ ʙʏ {app.mention}.</blockquote>")
        else:
            await message.reply_text("➲ **MAINTENANCE**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ ɪs ᴀʟʀᴇᴀᴅʏ ᴅɪsᴀʙʟᴇᴅ.</blockquote>")
    else:
        await message.reply_text(usage)

