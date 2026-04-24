from pyrogram import filters
from pyrogram.types import Message
from shakky import app
from shakky.utils.database import is_cohost, cohost_on, cohost_off
from shakky.utils.decorators import AdminRightsCheck
from config import BANNED_USERS

@app.on_message(filters.command(["cohost", "aihost"]) & filters.group & ~BANNED_USERS)
@AdminRightsCheck
async def cohost_toggle(client, message: Message, _):
    if len(message.command) < 2:
        return await message.reply_text("➲ **Usage:** `/cohost [enable|disable]`")
    
    state = message.command[1].lower()
    if state in ["enable", "on", "yes"]:
        await cohost_on(message.chat.id)
        await message.reply_text("➲ **AI VC Co-Host Enabled!**\nShakky will now announce songs and roast users in Voice Chat.")
    elif state in ["disable", "off", "no"]:
        await cohost_off(message.chat.id)
        await message.reply_text("➲ **AI VC Co-Host Disabled.**")
    else:
        await message.reply_text("➲ **Invalid State!** Use `enable` or `disable`.")
