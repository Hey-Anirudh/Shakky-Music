# Copyright (c) 2025 Nand Yaduwanshi <NoxxOP>
# Location: Supaul, Bihar
#
# All rights reserved.
#
# This code is the intellectual property of Nand Yaduwanshi.
# You are not allowed to copy, modify, redistribute, or use this
# code for commercial or personal projects without explicit permission.
#
# Allowed:
# - Forking for personal learning
# - Submitting improvements via pull requests
#
# Not Allowed:
# - Claiming this code as your own
# - Re-uploading without credit or permission
# - Selling or using commercially
#
# Contact for permissions:
# Email: badboy809075@gmail.com


import asyncio

from pyrogram import filters
from pyrogram.errors import FloodWait
from pyrogram.types import Message

from shakky import app
from shakky.misc import SUDOERS
from shakky.utils import get_readable_time
from shakky.utils.database import (
    add_banned_user,
    get_banned_count,
    get_banned_users,
    get_served_chats,
    is_banned_user,
    remove_banned_user,
)
from shakky.utils.decorators.language import language
from shakky.utils.extraction import extract_user
from config import BANNED_USERS


@app.on_message(filters.command(["gban", "globalban"]) & SUDOERS)
@language
async def global_ban(client, message: Message, _):
    if not message.reply_to_message:
        if len(message.command) != 2:
            return await message.reply_text("➲ **GBAN SYSTEM**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>**Usage:** /gban [username|id]</blockquote>")
    user = await extract_user(message)
    if user.id == message.from_user.id:
        return await message.reply_text("➲ **GBAN SYSTEM**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>ʏᴏᴜ ᴄᴀɴɴᴏᴛ ʙᴀɴ ʏᴏᴜʀsᴇʟғ.</blockquote>")
    elif user.id == app.id:
        return await message.reply_text("➲ **GBAN SYSTEM**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>ɪ ᴄᴀɴɴᴏᴛ ʙᴀɴ ᴍʏsᴇʟғ.</blockquote>")
    elif user.id in SUDOERS:
        return await message.reply_text("➲ **GBAN SYSTEM**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>ʏᴏᴜ ᴄᴀɴɴᴏᴛ ʙᴀɴ ᴀɴᴏᴛʜᴇʀ sᴜᴅᴏ ᴜsᴇʀ.</blockquote>")
    is_gbanned = await is_banned_user(user.id)
    if is_gbanned:
        return await message.reply_text(f"➲ **GBAN SYSTEM**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>{user.mention} ɪs ᴀʟʀᴇᴀᴅʏ ɢʟᴏʙᴀʟʟʏ ʙᴀɴɴᴇᴅ.</blockquote>")
    if user.id not in BANNED_USERS:
        BANNED_USERS.add(user.id)
    served_chats = []
    chats = await get_served_chats()
    for chat in chats:
        served_chats.append(int(chat["chat_id"]))
    time_expected = get_readable_time(len(served_chats))
    mystic = await message.reply_text(f"➲ **GBAN SYSTEM**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>ɪɴɪᴛɪᴀᴛɪɴɢ ɢʟᴏʙᴀʟ ʙᴀɴ ғᴏʀ {user.mention}...\n**ᴇxᴘᴇᴄᴛᴇᴅ ᴛɪᴍᴇ:** <code>{time_expected}</code></blockquote>")
    number_of_chats = 0
    for chat_id in served_chats:
        try:
            await app.ban_chat_member(chat_id, user.id)
            number_of_chats += 1
        except FloodWait as fw:
            await asyncio.sleep(int(fw.value))
        except:
            continue
            
    await add_banned_user(user.id)
    if user.id not in BANNED_USERS:
        BANNED_USERS.add(user.id)
        
    await message.reply_text(
        f"➲ **NEW GLOBAL BAN**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<blockquote>"
        f"✧ **Target:** {user.mention}\n"
        f"✧ **Banned By:** {message.from_user.mention}\n"
        f"✧ **Chats Banned:** <code>{number_of_chats}</code>"
        f"</blockquote>"
    )
    await mystic.delete()


@app.on_message(filters.command(["ungban"]) & SUDOERS)
@language
async def global_un(client, message: Message, _):
    if not message.reply_to_message:
        if len(message.command) != 2:
            return await message.reply_text("➲ **UN-GBAN SYSTEM**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>**Usage:** /ungban [username|id]</blockquote>")
    user = await extract_user(message)
    is_gbanned = await is_banned_user(user.id)
    if not is_gbanned:
        return await message.reply_text(f"➲ **UN-GBAN SYSTEM**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>{user.mention} ɪs ɴᴏᴛ ɢʟᴏʙᴀʟʟʏ ʙᴀɴɴᴇᴅ.</blockquote>")
    if user.id in BANNED_USERS:
        BANNED_USERS.remove(user.id)
    served_chats = []
    chats = await get_served_chats()
    for chat in chats:
        served_chats.append(int(chat["chat_id"]))
    time_expected = get_readable_time(len(served_chats))
    mystic = await message.reply_text(f"➲ **UN-GBAN SYSTEM**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>ɪɴɪᴛɪᴀᴛɪɴɢ ɢʟᴏʙᴀʟ ᴜɴʙᴀɴ ғᴏʀ {user.mention}...\n**ᴇxᴘᴇᴄᴛᴇᴅ ᴛɪᴍᴇ:** <code>{time_expected}</code></blockquote>")
    number_of_chats = 0
    for chat_id in served_chats:
        try:
            await app.unban_chat_member(chat_id, user.id)
            number_of_chats += 1
        except FloodWait as fw:
            await asyncio.sleep(int(fw.value))
        except:
            continue
    await remove_banned_user(user.id)
    await message.reply_text(f"➲ **GLOBAL UNBAN**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>sᴜᴄᴄᴇssғᴜʟʟʏ ᴜɴʙᴀɴɴᴇᴅ {user.mention} ɢʟᴏʙᴀʟʟʏ.\n**ᴜɴʙᴀɴɴᴇᴅ ɪɴ:** <code>{number_of_chats}</code> ᴄʜᴀᴛs.</blockquote>")
    await mystic.delete()


@app.on_message(filters.command(["gbannedusers", "gbanlist"]) & SUDOERS)
@language
async def gbanned_list(client, message: Message, _):
    counts = await get_banned_count()
    if counts == 0:
        return await message.reply_text("➲ **GBANNED USERS**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>ɴᴏ ɢʟᴏʙᴀʟʟʏ ʙᴀɴɴᴇᴅ ᴜsᴇʀs ғᴏᴜɴᴅ.</blockquote>")
    mystic = await message.reply_text("➲ **GBANNED USERS**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>ғᴇᴛᴄʜɪɴɢ...</blockquote>")
    msg = "➲ **GBANNED USERS**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>\n"
    count = 0
    users = await get_banned_users()
    for user_id in users:
        count += 1
        try:
            user = await app.get_users(user_id)
            user = user.first_name if not user.mention else user.mention
            msg += f"✧ {count}. {user}\n"
        except Exception:
            msg += f"✧ {count}. <code>{user_id}</code>\n"
            continue
    msg += "</blockquote>"
    if count == 0:
        return await mystic.edit_text("➲ **GBANNED USERS**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>ɴᴏ ɢʟᴏʙᴀʟʟʏ ʙᴀɴɴᴇᴅ ᴜsᴇʀs ғᴏᴜɴᴅ.</blockquote>")
    else:
        return await mystic.edit_text(msg)


# ©️ Copyright Reserved - @NoxxOP  Nand Yaduwanshi

# ===========================================
# ©️ 2025 Nand Yaduwanshi (aka @NoxxOP)
# 🔗 GitHub : https://github.com/NoxxOP/shakky
# 📢 Telegram Channel : https://t.me/ShrutiBots
# ===========================================


# ❤️ Love From ShrutiBots 

