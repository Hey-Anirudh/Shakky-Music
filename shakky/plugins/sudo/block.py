from pyrogram import filters
from pyrogram.types import Message

from shakky import app
from shakky.misc import SUDOERS
from shakky.utils.database import add_gban_user, remove_gban_user
from shakky.utils.decorators.language import language
from shakky.utils.extraction import extract_user
from config import BANNED_USERS


@app.on_message(filters.command(["block"]) & SUDOERS)
@language
async def useradd(client, message: Message, _):
    if not message.reply_to_message:
        if len(message.command) != 2:
            return await message.reply_text(_["general_1"])
    user = await extract_user(message)
    if user.id in BANNED_USERS:
        return await message.reply_text(f"➲ **BLOCK USER**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>{user.mention} ɪs ᴀʟʀᴇᴀᴅʏ ʙʟᴏᴄᴋᴇᴅ!</blockquote>")
    await add_gban_user(user.id)
    BANNED_USERS.add(user.id)
    await message.reply_text(f"➲ **BLOCK USER**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>sᴜᴄᴄᴇssғᴜʟʟʏ ʙʟᴏᴄᴋᴇᴅ {user.mention} ғʀᴏᴍ ᴛʜᴇ ʙᴏᴛ.</blockquote>")


@app.on_message(filters.command(["unblock"]) & SUDOERS)
@language
async def userdel(client, message: Message, _):
    if not message.reply_to_message:
        if len(message.command) != 2:
            return await message.reply_text(_["general_1"])
    user = await extract_user(message)
    if user.id not in BANNED_USERS:
        return await message.reply_text(f"➲ **UNBLOCK USER**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>{user.mention} ɪs ɴᴏᴛ ʙʟᴏᴄᴋᴇᴅ!</blockquote>")
    await remove_gban_user(user.id)
    BANNED_USERS.remove(user.id)
    await message.reply_text(f"➲ **UNBLOCK USER**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>sᴜᴄᴄᴇssғᴜʟʟʏ ᴜɴʙʟᴏᴄᴋᴇᴅ {user.mention}.</blockquote>")


@app.on_message(filters.command(["blocked", "blockedusers", "blusers"]) & SUDOERS)
@language
async def sudoers_list(client, message: Message, _):
    if not BANNED_USERS:
        return await message.reply_text("➲ **BLOCKED USERS**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>ɴᴏ ʙʟᴏᴄᴋᴇᴅ ᴜsᴇʀs ғᴏᴜɴᴅ.</blockquote>")
    mystic = await message.reply_text("➲ **BLOCKED USERS**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>ғᴇᴛᴄʜɪɴɢ...</blockquote>")
    msg = "➲ **BLOCKED USERS**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>\n"
    count = 0
    for users in BANNED_USERS:
        try:
            user = await app.get_users(users)
            user = user.first_name if not user.mention else user.mention
            count += 1
        except:
            continue
        msg += f"✧ {count}. {user}\n"
    msg += "</blockquote>"
    if count == 0:
        return await mystic.edit_text("➲ **BLOCKED USERS**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>ɴᴏ ʙʟᴏᴄᴋᴇᴅ ᴜsᴇʀs ғᴏᴜɴᴅ.</blockquote>")
    else:
        return await mystic.edit_text(msg)
