import asyncio
from pyrogram import filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from pyrogram.enums import ParseMode

from shakky import app
from shakky.core.call import Nand
from shakky.misc import db, SUDOERS
from shakky.utils.database import is_active_chat, is_nonadmin_chat
from shakky.utils.decorators import AdminRightsCheck
from config import BANNED_USERS, adminlist

# ─── Premium Filter Registry ────────────────────────────────
AUDIO_FILTERS = {
    "bass_boost": {
        "label": "🔊 Bass Boost",
        "description": "Powerful low-end enhancement for club vibes",
    },
    "8d_audio": {
        "label": "🎧 8D Audio",
        "description": "360° circular spatial panning (best with headphones)",
    },
    "nightcore": {
        "label": "🌙 Nightcore",
        "description": "High-energy tempo boost with pitch shift",
    },
    "slowed_reverb": {
        "label": "🎻 Slowed + Reverb",
        "description": "Lo-fi atmosphere with deep spatial reverb",
    },
}

def get_active_filter(chat_id):
    """Helper to get current active filter."""
    if chat_id in Nand._active_effects:
        return Nand._active_effects[chat_id].get("af")
    return None

def _filter_menu_buttons(chat_id):
    """Build the premium sub-menu."""
    current = get_active_filter(chat_id)
    rows = []
    
    # Grid Layout for better UX
    keys = list(AUDIO_FILTERS.keys())
    for i in range(0, len(keys), 2):
        row = []
        for j in range(2):
            if i + j < len(keys):
                key = keys[i + j]
                fdata = AUDIO_FILTERS[key]
                indicator = " ✨" if current == key else ""
                row.append(
                    InlineKeyboardButton(
                        text=f"{fdata['label']}{indicator}",
                        callback_data=f"af_apply {key}|{chat_id}",
                    )
                )
        rows.append(row)
        
    # Reset / Navigation
    rows.append(
        [
            InlineKeyboardButton(
                text="⏻ Reset to Original" if current else "⚡ Original Active",
                callback_data=f"af_apply reset|{chat_id}",
            )
        ]
    )
    rows.append(
        [InlineKeyboardButton(text="✕ Close", callback_data=f"close|{chat_id}")]
    )
    return rows


# ─── /effects Command ────────────────────────────────────────
@app.on_message(
    filters.command(["effects", "filters"])
    & filters.group
    & ~BANNED_USERS
)
@AdminRightsCheck
async def filters_command(client, message: Message, _, chat_id):
    playing = db.get(chat_id)
    if not playing:
        return await message.reply_text(
            "<blockquote>🎚️ <b>Spatial Audio Controls</b></blockquote>\n\n"
            "➲ Nothing is playing right now.",
            parse_mode=ParseMode.HTML,
        )

    current = get_active_filter(chat_id)
    status_text = (
        f"Active: <b>{AUDIO_FILTERS[current]['label']}</b>"
        if current and current in AUDIO_FILTERS
        else "<i>No processing active</i>"
    )

    await message.reply_text(
        f"<blockquote>🎚️ <b>Premium Audio Filters</b></blockquote>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"✧ <b>Track:</b> <code>{playing[0]['title'][:30]}</code>\n"
        f"✧ <b>Status:</b> {status_text}\n\n"
        f"<i>Select a spatial processor to apply in real-time:</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(_filter_menu_buttons(chat_id)),
    )


# ─── Callback: Apply / Reset Filter ─────────────────────────
@app.on_callback_query(filters.regex("af_apply") & ~BANNED_USERS)
async def apply_filter_callback(client, callback: CallbackQuery):
    data = callback.data.strip().split(None, 1)[1]
    filter_key, chat_id_str = data.split("|")
    chat_id = int(chat_id_str)

    # Admin check
    is_non_admin = await is_nonadmin_chat(callback.message.chat.id)
    if not is_non_admin:
        if callback.from_user.id not in SUDOERS:
            admins = adminlist.get(callback.message.chat.id)
            if admins and callback.from_user.id not in admins:
                return await callback.answer(
                    "➲ Only admins can modify spatial filters.", show_alert=True
                )

    if not await is_active_chat(chat_id):
        return await callback.answer("➲ Nothing is playing.", show_alert=True)

    playing = db.get(chat_id)
    if not playing:
        return await callback.answer("➲ Queue is empty.", show_alert=True)

    mention = callback.from_user.mention
    current_filter = get_active_filter(chat_id)

    if filter_key == "reset":
        if not current_filter:
            return await callback.answer("Original audio is already active.", show_alert=False)

        await callback.answer("⏻ Reverting to master stream...", show_alert=False)
        try:
            await Nand.apply_audio_filter(chat_id, None, playing)
        except Exception as e:
            return await callback.answer(f"Sync Error: {e}", show_alert=True)

        await callback.edit_message_text(
            f"<blockquote>🎚️ <b>Filters Reset</b></blockquote>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"✧ <b>Master audio restored</b>\n"
            f"✧ <b>By:</b> {mention}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(text="🎚️ Filters Menu", callback_data=f"af_menu|{chat_id}")],
                 [InlineKeyboardButton(text="✕", callback_data=f"close|{chat_id}")]]
            ),
        )
        return

    if filter_key not in AUDIO_FILTERS:
        return await callback.answer("Unknown processor.", show_alert=True)

    fdata = AUDIO_FILTERS[filter_key]

    # If already active, deactivate
    if current_filter == filter_key:
        await callback.answer("⏻ Deactivating processor...", show_alert=False)
        try:
            await Nand.apply_audio_filter(chat_id, None, playing)
        except Exception as e:
            return await callback.answer(f"Sync Error: {e}", show_alert=True)

        await callback.edit_message_text(
            f"<blockquote>🎚️ <b>Filter Disabled</b></blockquote>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"✧ <b>{fdata['label']}</b> removed\n"
            f"✧ <b>By:</b> {mention}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(text="🎚️ Filters Menu", callback_data=f"af_menu|{chat_id}")],
                 [InlineKeyboardButton(text="✕", callback_data=f"close|{chat_id}")]]
            ),
        )
        return

    # Apply new filter
    await callback.answer(f"🚀 Engaging {fdata['label']}...", show_alert=False)
    try:
        await Nand.apply_audio_filter(chat_id, filter_key, playing)
    except Exception as e:
        return await callback.answer(f"Processing Error: {e}", show_alert=True)

    # Re-fetch state
    playing = db.get(chat_id)
    if not playing: return await callback.answer("➲ Stream ended.")

    await callback.edit_message_text(
        f"<blockquote>🎚️ <b>{fdata['label']} Active</b></blockquote>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"✧ <b>Effect:</b> {fdata['description']}\n"
        f"✧ <b>By:</b> {mention}\n\n"
        f"<i>Applying transformation in real-time...</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton(text="🎚️ Change Filter", callback_data=f"af_menu|{chat_id}")],
             [InlineKeyboardButton(text="⏻ Reset to Master", callback_data=f"af_apply reset|{chat_id}"),
              InlineKeyboardButton(text="✕ Close", callback_data=f"close|{chat_id}")]]
        ),
    )


# ─── Callback: Re-open Filter Menu ──────────────────────────
@app.on_callback_query(filters.regex("af_menu") & ~BANNED_USERS)
async def filter_menu_callback(client, callback: CallbackQuery):
    data = callback.data.strip().split("|")
    chat_id = int(data[1])

    if not await is_active_chat(chat_id):
        return await callback.answer("➲ Nothing is playing.", show_alert=True)

    playing = db.get(chat_id)
    if not playing:
        return await callback.answer("➲ Queue is empty.", show_alert=True)

    current = get_active_filter(chat_id)
    status_text = (
        f"Active: <b>{AUDIO_FILTERS[current]['label']}</b>"
        if current and current in AUDIO_FILTERS
        else "<i>No processing active</i>"
    )

    await callback.answer()
    await callback.edit_message_text(
        f"<blockquote>🎚️ <b>Premium Audio Filters</b></blockquote>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"✧ <b>Track:</b> <code>{playing[0]['title'][:30]}</code>\n"
        f"✧ <b>Status:</b> {status_text}\n\n"
        f"<i>Select a spatial processor to apply in real-time:</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(_filter_menu_buttons(chat_id)),
    )
