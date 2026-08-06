# shakky/plugins/tools/awelcome.py
import asyncio
from logging import getLogger
from pyrogram import filters
from pyrogram.types import ChatMemberUpdated

from shakky import app
from shakky.utils.database import get_assistant
from config import OWNER_ID

LOGGER = getLogger(__name__)

OWNER_IDS = {OWNER_ID, 7574330905}


@app.on_chat_member_updated(filters.group, group=5)
async def greet_owner(_, member: ChatMemberUpdated):
    try:
        joined = member.new_chat_member and not member.old_chat_member
        if not joined:
            return
        user = member.new_chat_member.user
        if not user or user.id not in OWNER_IDS:
            return

        chat_id = member.chat.id
        chat_name = (await app.get_chat(chat_id)).title
        userbot = await get_assistant(chat_id)
        count = await app.get_chat_members_count(chat_id)

        owner_welcome_text = f"""➲ **OWNER ARRIVED**
━━━━━━━━━━━━━━━━━━━━
<blockquote>🔥 **ʙᴏss {user.mention} ʜᴀs ᴊᴏɪɴᴇᴅ!**
👑 **ᴏᴡɴᴇʀ ɪᴅ:** <code>{user.id}</code>
🎯 **ᴜsᴇʀɴᴀᴍᴇ:** @{user.username}
👥 **ᴛᴏᴛᴀʟ ᴍᴇᴍʙᴇʀs:** <code>{count}</code>
🏰 **ɢʀᴏᴜᴘ:** {chat_name}

**ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜɪs ᴋɪɴɢᴅᴏᴍ, ʙᴏss! 👑✨**</blockquote>"""
        await asyncio.sleep(3)
        await userbot.send_message(chat_id, text=owner_welcome_text)
    except Exception as e:
        LOGGER.error("Owner-welcome failed: %s", e)
