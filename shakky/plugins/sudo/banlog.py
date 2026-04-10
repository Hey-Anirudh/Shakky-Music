from datetime import datetime

from pyrogram import filters
from pyrogram.enums import ChatEventAction
from pyrogram.types import ChatEventFilter, Message

from shakky import app
from shakky.misc import SUDOERS
from config import OWNER_ID


@app.on_message(filters.command(["banlog", "banlogs", "recentbans"]) & filters.user(OWNER_ID))
async def ban_log(client, message: Message):
    """Fetch recent ban actions from a group's admin event log."""

    # Parse group ID from command args
    if len(message.command) < 2:
        return await message.reply_text(
            "**⚠️ Usage:** `/banlog <group_id>` \n"
            "**Example:** `/banlog -1001234567890`\n\n"
            "Fetches the recent ban/kick actions from the group's admin log.",
            disable_web_page_preview=True,
        )

    try:
        target_chat_id = int(message.command[1])
    except ValueError:
        return await message.reply_text("**❌ Invalid group ID.** Must be a numeric chat ID.")

    # Optional: limit count (default 20)
    limit = 20
    if len(message.command) >= 3:
        try:
            limit = min(int(message.command[2]), 50)  # cap at 50
        except ValueError:
            pass

    mystic = await message.reply_text("🔍 **Fetching recent ban actions...**")

    try:
        # Get chat info for the header
        try:
            chat_info = await app.get_chat(target_chat_id)
            chat_title = chat_info.title or "Unknown"
        except Exception:
            chat_title = str(target_chat_id)

        # Fetch ban/restriction events from admin log
        event_filter = ChatEventFilter(new_restrictions=True)
        ban_events = []

        async for event in app.get_chat_event_log(
            target_chat_id, filters=event_filter, limit=limit
        ):
            # Only keep actual ban/kick actions
            if event.action in (
                ChatEventAction.MEMBER_PERMISSIONS_CHANGED,
                ChatEventAction.MEMBER_JOINED,
            ):
                # Filter: only show events where user was banned (status = banned)
                ban_events.append(event)
            else:
                ban_events.append(event)

        if not ban_events:
            return await mystic.edit_text(
                f"📋 **No recent ban actions found** in **{chat_title}** (`{target_chat_id}`)."
            )

        # Build the response
        msg = (
            f"🔨 **Recent Ban Actions**\n"
            f"📌 **Group:** {chat_title}\n"
            f"🆔 **ID:** `{target_chat_id}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        count = 0
        for event in ban_events:
            count += 1

            # Admin who performed the action
            admin = event.user
            admin_name = admin.first_name or "Unknown"
            admin_id = admin.id

            # Timestamp
            event_time = event.date.strftime("%Y-%m-%d %H:%M:%S UTC")

            # Try to extract the affected user info
            affected_name = "Unknown"
            affected_id = "N/A"
            action_text = "Unknown Action"

            if event.old_member_permissions:
                affected_user = event.old_member_permissions.user
                affected_name = affected_user.first_name or "Unknown"
                affected_id = affected_user.id
            elif event.new_member_permissions:
                affected_user = event.new_member_permissions.user
                affected_name = affected_user.first_name or "Unknown"
                affected_id = affected_user.id

            # Determine the type of action
            if event.new_member_permissions:
                status = event.new_member_permissions.status
                status_str = str(status).split(".")[-1].upper() if status else "UNKNOWN"
                if "BANNED" in status_str or "KICKED" in status_str:
                    action_text = "🚫 Banned"
                elif "RESTRICTED" in status_str:
                    action_text = "⚠️ Restricted"
                else:
                    action_text = f"🔄 {status_str}"
            else:
                action_text = "🔄 Permission Change"

            msg += (
                f"**{count}.** {action_text}\n"
                f"   👮 **Admin:** {admin_name} (`{admin_id}`)\n"
                f"   👤 **User:** {affected_name} (`{affected_id}`)\n"
                f"   🕐 **Time:** `{event_time}`\n\n"
            )

            if count >= limit:
                break

        msg += f"━━━━━━━━━━━━━━━━━━━━\n📊 **Total:** {count} action(s) shown"

        # Handle message length limit (4096 chars for Telegram)
        if len(msg) > 4096:
            # Split into multiple messages
            parts = []
            current = ""
            for line in msg.split("\n"):
                if len(current) + len(line) + 1 > 4000:
                    parts.append(current)
                    current = line + "\n"
                else:
                    current += line + "\n"
            if current:
                parts.append(current)

            await mystic.edit_text(parts[0])
            for part in parts[1:]:
                await message.reply_text(part)
        else:
            await mystic.edit_text(msg)

    except Exception as e:
        error_msg = str(e)
        if "CHAT_ADMIN_REQUIRED" in error_msg:
            await mystic.edit_text(
                "**❌ Bot is not an admin** in that group.\n"
                "Make sure the bot has admin rights to access the event log."
            )
        elif "CHANNEL_INVALID" in error_msg or "CHANNEL_PRIVATE" in error_msg:
            await mystic.edit_text(
                "**❌ Invalid or inaccessible group.** "
                "Make sure the bot is a member with admin rights."
            )
        else:
            await mystic.edit_text(f"**❌ Error:** `{error_msg}`")
