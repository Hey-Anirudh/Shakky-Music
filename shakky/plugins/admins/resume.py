import time
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from shakky import app
from shakky.misc import db
from shakky.core.call import ani
from shakky.utils.webapp import notify_webapp
from config import BANNED_USERS
from shakky.utils.decorators.admins import AdminRightsCheck

@app.on_message(filters.command(["resume", "cresume"]) & filters.group & ~BANNED_USERS)
@AdminRightsCheck
async def resume_com(cli, message: Message, _, chat_id):
    if chat_id not in db or not db[chat_id]:
        return await message.reply_text("➲ **Nothing is paused to resume.**")

    # Step 5: Resume PyTgCalls VC
    await ani.resume_stream(chat_id)
    
    # Update local state
    current = db[chat_id][0]
    
    if current.get("paused"):
        current["paused"] = False
        pause_time = current.get("pause_time")
        if pause_time:
            # Shift the start time forward by the exact duration it was paused
            pause_duration = time.time() - pause_time
            current["start_time"] += pause_duration
    
    # Step 6: Notify WebApp
    await notify_webapp(chat_id, is_playing=True, action="resume")

    await message.reply_text(
        f"▶ **Resumed** by {message.from_user.mention}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(text="✕", callback_data="close")]])
    )
