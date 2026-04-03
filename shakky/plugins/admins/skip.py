from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

import config
from shakky import app
from shakky.misc import db
from shakky.utils.decorators.admins import AdminRightsCheck
from shakky.utils.stream.stream import skip_and_play
from shakky.utils.inline.play import stream_markup, _join_room_url
from config import BANNED_USERS

@app.on_message(
    filters.command(["skip", "cskip", "next", "cnext"], prefixes=["/", "!"]) & filters.group & ~BANNED_USERS
)
@AdminRightsCheck
async def skip(cli, message: Message, _, chat_id):
    if chat_id not in db or not db[chat_id]:
        return await message.reply_text("➲ **Queue is empty, nothing to skip.**")

    # Skip logic (pops current, starts next via change_stream)
    await skip_and_play(chat_id)
    
    # UI Feedback
    if not db.get(chat_id):
        await message.reply_text(
            f"▷ **Track Skipped**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"✧ **Action By:** {message.from_user.mention}\n"
            f"✧ **Info:** Queue is now empty."
        )
    else:
        current = db[chat_id][0]
        buttons = stream_markup(_, chat_id)
        
        # Generate custom thumbnail with PFPs
        from shakky.utils.thumbnails import get_thumb
        try:
            thumb = await get_thumb(
                current.get("vidid", "unknown"),
                current["title"],
                current.get("dur", "0:00"),
                current.get("by", "User"),
                chat_id,
                user_id=current.get("user_id")
            )
        except:
            thumb = current.get("thumb") or config.STREAM_IMG_URL
            
        try:
            await app.send_photo(
                chat_id,
                photo=thumb,
                caption=(
                    f"▷ **Now Playing**\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"✧ **Track:** `{current['title'][:30]}`\n"
                    f"✧ **Duration:** `{current.get('dur', '0:00')}`\n"
                    f"✧ **Skipped By:** {message.from_user.mention}"
                ),
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except Exception:
            await message.reply_text(
                f"▷ **Now Playing**\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"✧ **Track:** `{current['title'][:30]}`\n"
                f"✧ **Duration:** `{current.get('dur', '0:00')}`\n"
                f"✧ **Skipped By:** {message.from_user.mention}",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
