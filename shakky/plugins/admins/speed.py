from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.enums import ParseMode

from shakky import app
from shakky.core.call import Nand
from shakky.misc import db
from shakky.utils.database import is_active_chat
from shakky.utils.decorators import AdminRightsCheck
from config import BANNED_USERS

@app.on_message(
    filters.command(["speed", "playback", "cspeed", "cplayback"])
    & filters.group
    & ~BANNED_USERS
)
@AdminRightsCheck
async def speed_command(client, message: Message, _, chat_id):
    playing = db.get(chat_id)
    if not playing:
        return await message.reply_text("<blockquote>⚡ <b>Playback Speed</b></blockquote>\n\n➲ Nothing is playing.")
    
    speed_msg = message.text.split()
    if len(speed_msg) == 1:
        # Show a premium menu for speed selection
        buttons = [
            [
                InlineKeyboardButton("0.5x", callback_data=f"af_speed 0.5|{chat_id}"),
                InlineKeyboardButton("0.75x", callback_data=f"af_speed 0.75|{chat_id}"),
                InlineKeyboardButton("1.0x", callback_data=f"af_speed 1.0|{chat_id}"),
            ],
            [
                InlineKeyboardButton("1.5x", callback_data=f"af_speed 1.5|{chat_id}"),
                InlineKeyboardButton("2.0x", callback_data=f"af_speed 2.0|{chat_id}"),
            ],
            [InlineKeyboardButton("✕ Close", callback_data=f"close|{chat_id}")]
        ]
        return await message.reply_text(
            "<blockquote>⚡ <b>Playback Speed Control</b></blockquote>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "<i>Select a speed to transform the current stream:</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    speed = speed_msg[1]
    if speed not in ["0.5", "0.75", "1.0", "1.5", "2.0"]:
        return await message.reply_text("➲ Please specify a valid speed: 0.5, 0.75, 1.0, 1.5, or 2.0")
        
    mystic = await message.reply_text(f"🚀 **Applying {speed}x speed transformation...**")
    try:
        await Nand.speedup_stream(chat_id, speed, playing)
        await mystic.edit_text(
            f"<blockquote>🚀 <b>Speed Modified to {speed}x</b></blockquote>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"✧ <b>Status:</b> Syncing stream...\n"
            f"✧ <b>By:</b> {message.from_user.mention}",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await mystic.edit_text(f"❌ **Transformation Failed:** {e}")

@app.on_callback_query(filters.regex("af_speed") & ~BANNED_USERS)
async def speed_callback(client, callback):
    data = callback.data.split(None, 1)[1]
    speed, chat_id = data.split("|")
    chat_id = int(chat_id)
    
    playing = db.get(chat_id)
    if not playing: return await callback.answer("➲ Stream ended.")
    
    await callback.answer(f"Applying {speed}x speed...")
    try:
        await Nand.speedup_stream(chat_id, speed, playing)
        await callback.edit_message_text(
            f"<blockquote>🚀 <b>Speed Modified to {speed}x</b></blockquote>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"✧ <b>Status:</b> Stream Synced\n"
            f"✧ <b>By:</b> {callback.from_user.mention}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✕ Close", callback_data=f"close|{chat_id}")]])
        )
    except Exception as e:
        await callback.answer(f"Failed: {e}", show_alert=True)
