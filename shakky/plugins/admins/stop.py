from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from shakky import app
from shakky.misc import db
from shakky.core.call import ani
from shakky.utils.webapp import notify_webapp
from config import BANNED_USERS
from shakky.utils.decorators.admins import AdminRightsCheck
from shakky.utils.database import remove_active_chat

@app.on_message(
    filters.command(["end", "stop"], prefixes=["/", "!"]) & filters.group & ~BANNED_USERS
)
@AdminRightsCheck
async def stop_music(cli, message: Message, _, chat_id):
    # Step 5: Clear queue
    db[chat_id] = []
    
    # Step 5: Leave VC
    await remove_active_chat(chat_id)
    await ani.stop_stream(chat_id)
    
    # Step 6: Notify WebApp
    await notify_webapp(chat_id, is_playing=False, action="stop")
    
    # [NEW] Disable AI Pilot
    from shakky.misc import ai_mode
    ai_mode[chat_id] = False
    
    await message.reply_text(
        f"✦ **STREAM STOPPED**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"✧ **Action By:** {message.from_user.mention}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(text="✖ Close", callback_data="close")]])
    )
