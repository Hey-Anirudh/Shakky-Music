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

# ─── Active Filters State ───────────────────────────────────
# Tracks the currently active filter per chat: {chat_id: "filter_name" or None}
active_filters = {}

# ─── FFmpeg Filter Definitions ──────────────────────────────
AUDIO_FILTERS = {
    "bass_boost": {
        "label": "🔊 Bass Boost",
        "ffmpeg": "equalizer=f=60:width_type=h:width=50:g=12,equalizer=f=120:width_type=h:width=100:g=6",
        "description": "Deep bass enhancement",
    },
    "8d_audio": {
        "label": "🎧 8D Audio",
        "ffmpeg": "apulsator=mode=sine:hz=0.09:amount=0.8,aecho=0.8:0.88:60:0.4",
        "description": "Circular spatial panning",
    },
    "nightcore": {
        "label": "🌙 Nightcore",
        "ffmpeg": "asetrate=44100*1.25,aresample=44100,atempo=1.06",
        "description": "Fast tempo + high pitch",
    },
    "slowed_reverb": {
        "label": "🎻 Slowed+Reverb",
        "ffmpeg": "asetrate=44100*0.85,aresample=44100,aecho=0.8:0.9:500:0.4,aecho=0.8:0.88:250:0.3",
        "description": "Lo-fi slowed with reverb",
    },
}


def _filter_menu_buttons(chat_id):
    """Build the inline keyboard for the Filters sub-menu."""
    current = active_filters.get(chat_id)
    rows = []
    for key, fdata in AUDIO_FILTERS.items():
        indicator = " ✓" if current == key else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{fdata['label']}{indicator}",
                    callback_data=f"af_apply {key}|{chat_id}",
                )
            ]
        )
    # Reset / Off button
    rows.append(
        [
            InlineKeyboardButton(
                text="⏻ Reset (Original)" if current else "⏻ No Filter Active",
                callback_data=f"af_apply reset|{chat_id}",
            )
        ]
    )
    rows.append(
        [InlineKeyboardButton(text="✕ Close", callback_data=f"close|{chat_id}")]
    )
    return rows


# ─── /filter Command ────────────────────────────────────────
@app.on_message(
    filters.command(["effects"])
    & filters.group
    & ~BANNED_USERS
)
@AdminRightsCheck
async def filters_command(client, message: Message, _, chat_id):
    playing = db.get(chat_id)
    if not playing:
        return await message.reply_text(
            "<blockquote>🎚️ <b>Audio Filters</b></blockquote>\n\n"
            "➲ Nothing is playing right now.",
            parse_mode=ParseMode.HTML,
        )

    current = active_filters.get(chat_id)
    status_text = (
        f"Active: <b>{AUDIO_FILTERS[current]['label']}</b>"
        if current and current in AUDIO_FILTERS
        else "No filter active"
    )

    await message.reply_text(
        f"<blockquote>🎚️ <b>Spatial Audio Filters</b></blockquote>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"✧ <b>Track:</b> <code>{playing[0].get('title', 'Unknown')[:30]}</code>\n"
        f"✧ <b>Status:</b> {status_text}\n\n"
        f"<i>Select a filter to apply in real-time:</i>",
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
                    "➲ Only admins can change filters.", show_alert=True
                )

    if not await is_active_chat(chat_id):
        return await callback.answer("➲ Nothing is playing.", show_alert=True)

    playing = db.get(chat_id)
    if not playing:
        return await callback.answer("➲ Queue is empty.", show_alert=True)

    mention = callback.from_user.mention

    if filter_key == "reset":
        if not active_filters.get(chat_id):
            return await callback.answer("No filter is active.", show_alert=False)

        await callback.answer("⏻ Resetting to original...")
        try:
            await Nand.apply_audio_filter(chat_id, None, playing)
            active_filters.pop(chat_id, None)
        except Exception as e:
            return await callback.answer(f"Error: {e}", show_alert=True)

        await callback.edit_message_text(
            f"<blockquote>🎚️ <b>Filter Reset</b></blockquote>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"✧ <b>Audio restored to original</b>\n"
            f"✧ <b>By:</b> {mention}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(text="🎚️ Filters", callback_data=f"af_menu|{chat_id}")],
                 [InlineKeyboardButton(text="✕", callback_data=f"close|{chat_id}")]]
            ),
        )
        return

    if filter_key not in AUDIO_FILTERS:
        return await callback.answer("Unknown filter.", show_alert=True)

    fdata = AUDIO_FILTERS[filter_key]

    # If already active, deactivate
    if active_filters.get(chat_id) == filter_key:
        await callback.answer("⏻ Removing filter...")
        try:
            await Nand.apply_audio_filter(chat_id, None, playing)
            active_filters.pop(chat_id, None)
        except Exception as e:
            return await callback.answer(f"Error: {e}", show_alert=True)

        await callback.edit_message_text(
            f"<blockquote>🎚️ <b>Filter Removed</b></blockquote>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"✧ <b>{fdata['label']}</b> deactivated\n"
            f"✧ <b>By:</b> {mention}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(text="🎚️ Filters", callback_data=f"af_menu|{chat_id}")],
                 [InlineKeyboardButton(text="✕", callback_data=f"close|{chat_id}")]]
            ),
        )
        return

    # Apply new filter
    await callback.answer(f"Applying {fdata['label']}...")
    try:
        await Nand.apply_audio_filter(chat_id, filter_key, playing)
        active_filters[chat_id] = filter_key
    except Exception as e:
        return await callback.answer(f"Error: {e}", show_alert=True)

    await callback.edit_message_text(
        f"<blockquote>🎚️ <b>{fdata['label']} Active</b></blockquote>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"✧ <b>Effect:</b> {fdata['description']}\n"
        f"✧ <b>Track:</b> <code>{playing[0].get('title', 'Unknown')[:30]}</code>\n"
        f"✧ <b>By:</b> {mention}",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton(text="🎚️ Change Filter", callback_data=f"af_menu|{chat_id}")],
             [InlineKeyboardButton(text="⏻ Reset", callback_data=f"af_apply reset|{chat_id}"),
              InlineKeyboardButton(text="✕", callback_data=f"close|{chat_id}")]]
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

    current = active_filters.get(chat_id)
    status_text = (
        f"Active: <b>{AUDIO_FILTERS[current]['label']}</b>"
        if current and current in AUDIO_FILTERS
        else "No filter active"
    )

    await callback.answer()
    await callback.edit_message_text(
        f"<blockquote>🎚️ <b>Spatial Audio Filters</b></blockquote>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"✧ <b>Track:</b> <code>{playing[0].get('title', 'Unknown')[:30]}</code>\n"
        f"✧ <b>Status:</b> {status_text}\n\n"
        f"<i>Select a filter to apply in real-time:</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(_filter_menu_buttons(chat_id)),
    )
