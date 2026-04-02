from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from shakky import app
from shakky.misc import db
from shakky.utils.database import get_loop, set_loop
from shakky.utils.webapp import notify_webapp
from config import BANNED_USERS
from shakky.utils.decorators.admins import AdminRightsCheck

@app.on_message(filters.command(["loop", "cloop"]) & filters.group & ~BANNED_USERS)
@AdminRightsCheck
async def loop_com(cli, message: Message, _, chat_id):
    if len(message.command) != 2:
        return await message.reply_text("➲ **Usage: /loop [enable|disable|1-10]**")

    state = message.text.split(None, 1)[1].strip()
    
    if state.isnumeric():
        state = int(state)
        if 1 <= state <= 10:
            await set_loop(chat_id, state)
            msg = f"🔁 **Loop Enabled** for {state} times"
        else:
            return await message.reply_text("➲ **Loop count must be between 1-10.**")
    elif state.lower() == "enable":
        await set_loop(chat_id, 10)
        msg = "🔁 **Loop Enabled** (10 times)"
    elif state.lower() == "disable":
        await set_loop(chat_id, 0)
        msg = "🔁 **Loop Disabled**"
    else:
        return await message.reply_text("➲ **Usage: /loop [enable|disable|1-10]**")

    # Step 6: Notify WebApp
    loop_val = await get_loop(chat_id)
    await notify_webapp(chat_id, is_playing=True, action="loop", loop=loop_val)

    await message.reply_text(
        f"{msg} by {message.from_user.mention}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(text="✖ Close", callback_data="close")]])
    )
