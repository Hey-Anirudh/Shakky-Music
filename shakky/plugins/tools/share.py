from pyrogram import filters

from shakky import app
from config import BANNED_USERS


@app.on_message(filters.command(["share", "room", "player"]) & ~BANNED_USERS)
async def share_command(client, message):
    await message.reply_text(
        "➲ **The live player webapp has been disabled.**"
    )
