# shakky/plugins/admins/equalizer.py
# Single unified audio panel: presets + nightcore + crossfade + speed.

import asyncio
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from shakky import app
from shakky.misc import db
from shakky.utils.effects import (
    EFFECTS, PRESET_NAMES, set_effect, set_speed, current,
    crossfade_enabled, set_crossfade,
)
from shakky.utils.decorators.admins import AdminRightsCheck
from config import BANNED_USERS

SPEED_OPTIONS = ["0.75", "1", "1.25", "1.5", "2"]


def _eq_keyboard(chat_id: int, active: str):
    rows = []
    for name in EFFECTS:
        label = PRESET_NAMES.get(name, name or "Off")
        marker = " •" if name == active else ""
        rows.append(
            InlineKeyboardButton(f"{label}{marker}", callback_data=f"eq_set {name}|{chat_id}")
        )
    # 2 columns of presets
    pairs = [rows[i:i + 2] for i in range(0, len(rows), 2)]

    nightcore_state = "⚡ Nightcore: ON" if active == "nightcore" else "⚡ Nightcore: OFF"
    crossfade_state = "🔀 Crossfade: ON" if crossfade_enabled(chat_id) else "🔀 Crossfade: OFF"
    pairs.append([
        InlineKeyboardButton(nightcore_state, callback_data=f"eq_toggle nightcore|{chat_id}"),
        InlineKeyboardButton(crossfade_state, callback_data=f"eq_toggle crossfade|{chat_id}"),
    ])

    pairs.append([
        InlineKeyboardButton(f"⏩ {s}x", callback_data=f"eq_speed {s}|{chat_id}")
        for s in SPEED_OPTIONS
    ])

    pairs.append([InlineKeyboardButton("✕", callback_data=f"close|{chat_id}")])
    return InlineKeyboardMarkup(pairs)


def _apply_live(chat_id):
    playing = db.get(chat_id)
    if playing:
        from shakky.core.call import Nand
        asyncio.create_task(Nand.resync_stream(chat_id, refresh_time=False))


@app.on_message(filters.command(["equalizer", "eq", "effects", "audio"]) & ~BANNED_USERS)
@AdminRightsCheck
async def equalizer_command(client, message: Message, _, chat_id):
    active = current(chat_id)
    speed_note = ""
    if active.startswith("atempo"):
        speed_note = f"\n✧ <b>Speed:</b> <code>{active.split('=')[1]}x</code>"
    reply = f"<blockquote><b>🎚 Audio Effects</b></blockquote>\n"
    reply += f"━━━━━━━━━━━━━━━━━━\n✧ <b>Preset:</b> <code>{PRESET_NAMES.get(active, 'Off')}</code>{speed_note}\n\n"
    reply += "<i>Everything applies live to the current & next tracks.\n"
    reply += "Use <code>/speed 1.5</code> for exact speeds too.</i>"
    await message.reply_text(reply, reply_markup=_eq_keyboard(chat_id, active))


@app.on_callback_query(filters.regex(r"^eq_set "))
async def eq_set_callback(client, callback):
    from config import adminlist
    from shakky.misc import SUDOERS

    name, chat_id_str = callback.data.split(None, 1)[1].split("|")
    chat_id = int(chat_id_str)

    is_admin = callback.from_user.id in SUDOERS
    if not is_admin:
        admins = adminlist.get(callback.message.chat.id, [])
        if callback.from_user.id not in admins:
            return await callback.answer("➲ Only admins can change the equalizer.", show_alert=True)

    if not set_effect(chat_id, name):
        return await callback.answer("Unknown preset.", show_alert=True)

    _apply_live(chat_id)

    active = current(chat_id)
    await callback.answer(f"Equalizer: {PRESET_NAMES.get(active, 'Off')}")
    try:
        await callback.edit_message_reply_markup(_eq_keyboard(chat_id, active))
    except Exception:
        pass


@app.on_callback_query(filters.regex(r"^eq_toggle "))
async def eq_toggle_callback(client, callback):
    from config import adminlist
    from shakky.misc import SUDOERS

    kind, chat_id_str = callback.data.split(None, 1)[1].split("|")
    chat_id = int(chat_id_str)

    is_admin = callback.from_user.id in SUDOERS
    if not is_admin:
        admins = adminlist.get(callback.message.chat.id, [])
        if callback.from_user.id not in admins:
            return await callback.answer("➲ Only admins can change audio effects.", show_alert=True)

    if kind == "nightcore":
        if current(chat_id) == "nightcore":
            set_effect(chat_id, "")
            msg = "Nightcore: OFF"
        else:
            set_effect(chat_id, "nightcore")
            msg = "Nightcore: ON ⚡"
    else:  # crossfade
        state = not crossfade_enabled(chat_id)
        set_crossfade(chat_id, state)
        msg = f"Crossfade: {'ON' if state else 'OFF'}"

    _apply_live(chat_id)
    await callback.answer(msg)
    try:
        await callback.edit_message_reply_markup(_eq_keyboard(chat_id, current(chat_id)))
    except Exception:
        pass


@app.on_callback_query(filters.regex(r"^eq_speed "))
async def eq_speed_callback(client, callback):
    from config import adminlist
    from shakky.misc import SUDOERS

    val, chat_id_str = callback.data.split(None, 1)[1].split("|")
    chat_id = int(chat_id_str)

    is_admin = callback.from_user.id in SUDOERS
    if not is_admin:
        admins = adminlist.get(callback.message.chat.id, [])
        if callback.from_user.id not in admins:
            return await callback.answer("➲ Only admins can change audio effects.", show_alert=True)

    speed = float(val)
    if abs(speed - 1.0) < 0.05:
        set_effect(chat_id, "")
        msg = "Speed reset to 1x"
    else:
        set_speed(chat_id, speed)
        msg = f"Speed: {speed:g}x"

    _apply_live(chat_id)
    await callback.answer(msg)
    try:
        await callback.edit_message_reply_markup(_eq_keyboard(chat_id, current(chat_id)))
    except Exception:
        pass


@app.on_message(filters.command("speed") & ~BANNED_USERS)
@AdminRightsCheck
async def speed_command(client, message: Message, _, chat_id):
    if len(message.command) < 2:
        return await message.reply_text(
            "➲ **Usage:** `/speed 1.5` (0.5–2.0).\nUse `/speed 1` to reset.\n"
            "Or open `/eq` for the full audio panel."
        )
    try:
        val = float(message.text.split(None, 1)[1])
        if val < 0.5 or val > 2.0:
            return await message.reply_text("➲ Speed must be between 0.5x and 2.0x.")
    except ValueError:
        return await message.reply_text("➲ Invalid speed value.")

    if abs(val - 1.0) < 0.05:
        set_effect(chat_id, "")
        await message.reply_text("➲ **Speed: reset to 1x**")
    else:
        set_speed(chat_id, val)
        await message.reply_text(f"➲ **Speed: {val:.2f}x**")

    _apply_live(chat_id)