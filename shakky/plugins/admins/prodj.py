from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.enums import ParseMode

from shakky import app
from shakky.misc import SUDOERS
from shakky.utils.database import is_prodj, prodj_on, prodj_off, is_autodj, autodj_on
from shakky.utils.decorators import AdminRightsCheck
from config import BANNED_USERS


@app.on_message(
    filters.command(["prodj", "djmode", "clubmode", "nonstop"])
    & filters.group
    & ~BANNED_USERS
)
@AdminRightsCheck
async def prodj_command(client, message: Message, _, chat_id):
    """Toggle the High-Energy Pro-DJ Mode (35s transitions)."""
    args = message.text.split()

    if len(args) > 1:
        arg = args[1].lower()
        if arg in ("on", "enable", "yes"):
            await prodj_on(chat_id)
            await autodj_on(chat_id) # Auto-DJ must be on for transitions to work
            return await message.reply_text(
                "<blockquote>🎧 <b>Pro-DJ Mode Active</b></blockquote>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "✧ <b>Status:</b> <code>Enabled</code>\n\n"
                "<i>I'll now play the best 40s of each song\n"
                "and transition to the next vibe automatically.</i>",
                parse_mode=ParseMode.HTML,
            )
        elif arg in ("off", "disable", "no"):
            await prodj_off(chat_id)
            return await message.reply_text(
                "<blockquote>🎧 <b>Pro-DJ Mode</b></blockquote>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "✧ <b>Status:</b> <code>Disabled</code>\n\n"
                "<i>Songs will now play in full length.</i>",
                parse_mode=ParseMode.HTML,
            )

    # No argument — show current status with toggle button
    is_on = await is_prodj(chat_id)
    status = "Active 🔥" if is_on else "Off ⏻"
    toggle_text = "⏻ Disable" if is_on else "🔥 Enable Pro-DJ"
    toggle_data = f"prodj_toggle off|{chat_id}" if is_on else f"prodj_toggle on|{chat_id}"

    await message.reply_text(
        f"<blockquote>🎧 <b>Pro-DJ: High-Energy Mix</b></blockquote>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"✧ <b>Status:</b> <code>{status}</code>\n\n"
        f"<i>When enabled, the bot transitions to a new\n"
        f"song every 40s, acting like a club DJ.</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(text=toggle_text, callback_data=toggle_data)],
                [InlineKeyboardButton(text="✕", callback_data=f"close|{chat_id}")],
            ]
        ),
    )


@app.on_callback_query(filters.regex("prodj_toggle") & ~BANNED_USERS)
async def prodj_toggle_callback(client, callback):
    data = callback.data.strip().split(None, 1)[1]
    action, chat_id_str = data.split("|")
    chat_id = int(chat_id_str)

    # Admin check
    from shakky.utils.database import is_nonadmin_chat
    from config import adminlist

    is_non_admin = await is_nonadmin_chat(callback.message.chat.id)
    if not is_non_admin:
        if callback.from_user.id not in SUDOERS:
            admins = adminlist.get(callback.message.chat.id)
            if admins and callback.from_user.id not in admins:
                return await callback.answer(
                    "➲ Only admins can toggle Pro-DJ Mode.", show_alert=True
                )

    mention = callback.from_user.mention

    if action == "on":
        await prodj_on(chat_id)
        await autodj_on(chat_id)
        status = "Active 🔥"
        toggle_text = "⏻ Disable"
        toggle_data = f"prodj_toggle off|{chat_id}"
    else:
        await prodj_off(chat_id)
        status = "Off ⏻"
        toggle_text = "🔥 Enable Pro-DJ"
        toggle_data = f"prodj_toggle on|{chat_id}"

    await callback.answer(f"Pro-DJ Mode: {status}")
    await callback.edit_message_text(
        f"<blockquote>🎧 <b>Pro-DJ: High-Energy Mix</b></blockquote>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"✧ <b>Status:</b> <code>{status}</code>\n"
        f"✧ <b>By:</b> {mention}\n\n"
        f"<i>Transitions every 40s enabled. Keep the vibe!</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(text=toggle_text, callback_data=toggle_data)],
                [InlineKeyboardButton(text="✕", callback_data=f"close|{chat_id}")],
            ]
        ),
    )
