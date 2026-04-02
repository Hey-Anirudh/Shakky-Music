import time
from pyrogram import filters
from pyrogram.types import Message

from shakky import app
from shakky.misc import db
from shakky.core.call import ani
from shakky.utils.webapp import notify_webapp
from config import BANNED_USERS
from shakky.utils.decorators.admins import AdminRightsCheck

@app.on_message(filters.command(["pause", "cpause"]) & filters.group & ~BANNED_USERS)
@AdminRightsCheck
async def pause_admin(cli, message: Message, _, chat_id):
    if chat_id not in db or not db[chat_id]:
        return await message.reply_text("➲ **Nothing is playing to pause.**")

    # Step 5: Pause PyTgCalls VC
    await ani.pause_stream(chat_id)
    
    # Update local state
    current = db[chat_id][0]
    current["paused"] = True
    current["pause_time"] = time.time()
    
    # Step 6: Notify WebApp
    await notify_webapp(chat_id, is_playing=False, action="pause")

    await message.reply_text(
        f"✦ **STREAM PAUSED**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"✧ **Action By:** {message.from_user.mention}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(text="✖ Close", callback_data="close")]])
    )
