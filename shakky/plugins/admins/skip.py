from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

import config
from shakky import app
from shakky.misc import db
from shakky.utils.decorators.admins import AdminRightsCheck
from shakky.utils.stream.stream import skip_and_play
from config import BANNED_USERS

@app.on_message(
    filters.command(["skip", "cskip", "next", "cnext"], prefixes=["/", "!"]) & filters.group & ~BANNED_USERS
)
@AdminRightsCheck
async def skip(cli, message: Message, _, chat_id):
    if chat_id not in db or not db[chat_id]:
        return await message.reply_text("➲ **Queue is empty, nothing to skip.**")

    # Step 5: Skip logic (Cleans up current, starts next)
    await skip_and_play(chat_id)
    
    # UI Feedback
    if not db.get(chat_id):
        await message.reply_text(
            f"✦ **TRACK SKIPPED**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"✧ **Action By:** {message.from_user.mention}\n"
            f"✧ **Info:** Queue is now empty."
        )
    else:
        current = db[chat_id][0]
        thumb = current.get("thumb") or config.STREAM_IMG_URL
        webapp_url = f"https://t.me/{app.me.username if app.me else config.BOT_USERNAME.replace('@', '')}/join?startapp={abs(chat_id)}"
        buttons = [[InlineKeyboardButton(text="🎧 Join Room", url=webapp_url)]]
        
        # UI Feedback with robust photo fallback
        try:
            await app.send_photo(
                chat_id,
                photo=thumb,
                caption=(
                    f"✦ **TRACK SKIPPED**\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"✧ **Now Playing:** `{current['title']}`\n"
                    f"✧ **Action By:** {message.from_user.mention}"
                ),
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except Exception:
            try:
                await app.send_photo(
                    chat_id,
                    photo=config.STREAM_IMG_URL,
                    caption=(
                        f"✦ **TRACK SKIPPED**\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"✧ **Now Playing:** `{current['title']}`\n"
                        f"✧ **Action By:** {message.from_user.mention}"
                    ),
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            except Exception:
                await message.reply_text(
                    f"✦ **TRACK SKIPPED**\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"✧ **Now Playing:** `{current['title']}`\n"
                    f"✧ **Action By:** {message.from_user.mention}",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
