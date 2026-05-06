from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

from shakky import app
from shakky.misc import SUDOERS
from shakky.utils.database import is_autodj, autodj_on, autodj_off
from shakky.utils.decorators import AdminRightsCheck
from config import BANNED_USERS


@app.on_message(
    filters.command(["autodj", "autoDJ", "autoplay"])
    & filters.group
    & ~BANNED_USERS
)
@AdminRightsCheck
async def autodj_command(client, message: Message, _, chat_id):
    """Toggle the Smart Auto-DJ feature for this group."""
    args = message.text.split()

    if len(args) > 1:
        arg = args[1].lower()
        if arg in ("on", "enable", "yes"):
            await autodj_on(chat_id)
            return await message.reply_text(
                "<blockquote>✨ <b>Smart Auto-DJ</b></blockquote>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "✧ <b>Status:</b> <code>Enabled</code>\n\n"
                "<i>When the queue empties, I'll automatically\n"
                "play a related track to keep the vibe alive.</i>",
                parse_mode="html",
            )
        elif arg in ("off", "disable", "no"):
            await autodj_off(chat_id)
            return await message.reply_text(
                "<blockquote>✨ <b>Smart Auto-DJ</b></blockquote>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "✧ <b>Status:</b> <code>Disabled</code>\n\n"
                "<i>Playback will stop when the queue is empty.</i>",
                parse_mode="html",
            )

    # No argument — show current status with toggle button
    is_on = await is_autodj(chat_id)
    status = "Enabled ✓" if is_on else "Disabled ✗"
    toggle_text = "⏻ Disable" if is_on else "✨ Enable"
    toggle_data = f"autodj_toggle off|{chat_id}" if is_on else f"autodj_toggle on|{chat_id}"

    await message.reply_text(
        f"<blockquote>✨ <b>Smart Auto-DJ</b></blockquote>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"✧ <b>Status:</b> <code>{status}</code>\n\n"
        f"<i>When enabled, the bot uses AI to find a\n"
        f"related track when the queue runs out.</i>",
        parse_mode="html",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(text=toggle_text, callback_data=toggle_data)],
                [InlineKeyboardButton(text="✕", callback_data=f"close|{chat_id}")],
            ]
        ),
    )


@app.on_callback_query(filters.regex("autodj_toggle") & ~BANNED_USERS)
async def autodj_toggle_callback(client, callback):
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
                    "➲ Only admins can toggle Auto-DJ.", show_alert=True
                )

    mention = callback.from_user.mention

    if action == "on":
        await autodj_on(chat_id)
        status = "Enabled ✓"
        toggle_text = "⏻ Disable"
        toggle_data = f"autodj_toggle off|{chat_id}"
    else:
        await autodj_off(chat_id)
        status = "Disabled ✗"
        toggle_text = "✨ Enable"
        toggle_data = f"autodj_toggle on|{chat_id}"

    await callback.answer(f"Auto-DJ: {status}")
    await callback.edit_message_text(
        f"<blockquote>✨ <b>Smart Auto-DJ</b></blockquote>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"✧ <b>Status:</b> <code>{status}</code>\n"
        f"✧ <b>By:</b> {mention}\n\n"
        f"<i>When enabled, the bot uses AI to find a\n"
        f"related track when the queue runs out.</i>",
        parse_mode="html",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(text=toggle_text, callback_data=toggle_data)],
                [InlineKeyboardButton(text="✕", callback_data=f"close|{chat_id}")],
            ]
        ),
    )
