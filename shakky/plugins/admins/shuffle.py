import random
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from shakky import app
from shakky.misc import db
from shakky.utils.webapp import notify_webapp
from config import BANNED_USERS
from shakky.utils.decorators.admins import AdminRightsCheck

@app.on_message(
    filters.command(["shuffle", "cshuffle"]) & filters.group & ~BANNED_USERS
)
@AdminRightsCheck
async def shuffle_com(Client, message: Message, _, chat_id):
    check = db.get(chat_id)
    if not check or len(check) < 2:
        return await message.reply_text("➲ **Not enough tracks in queue to shuffle.**")
    
    # Keeps current song at index 0, shuffles the rest
    current = check.pop(0)
    random.shuffle(check)
    check.insert(0, current)
    
    # Step 6: Notify WebApp
    await notify_webapp(chat_id, current_song=current, queue=check[1:], action="shuffle")

    await message.reply_text(
        f"➲ **Queue Shuffled** by {message.from_user.mention}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(text="✕", callback_data="close")]])
    )
