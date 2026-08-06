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
from contextlib import suppress

from pyrogram import filters
from pyrogram.enums import ChatMembersFilter, ChatMemberStatus, ChatType
from pyrogram.types import (
    CallbackQuery,
    ChatPermissions,
    ChatPrivileges,
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from string import ascii_lowercase
from typing import Dict, Union

from shakky import app
from shakky.misc import SUDOERS
from shakky.core.mongo import mongodb
from shakky.utils.error import capture_err
from shakky.utils.keyboard import ikb
from shakky.utils.database import save_filter
from shakky.utils.functions import (
    extract_user,
    extract_user_and_reason,
    time_converter,
)
from shakky.utils.permissions import adminsOnly, member_permissions
from config import BANNED_USERS, OWNER_ID

warnsdb = mongodb.warns

__MODULE__ = "Bᴀɴ"
__HELP__ = """
/ban - Ban A User
/banall - Ban All Users
/sban - Delete all messages of user that sended in group and ban the user
/tban - Ban A User For Specific Time
/unban - Unban A User
/warn - Warn A User
/swarn - Delete all the message sended in group and warn the user
/rmwarns - Remove All Warning of A User
/warns - Show Warning Of A User
/kick - Kick A User
/skick - Delete the replied message kicking its sender
/purge - Purge Messages
/purge [n] - Purge "n" number of messages from replied message
/del - Delete Replied Message
/promote - Promote A Member
/fullpromote - Promote A Member With All Rights
/demote - Demote A Member
/pin - Pin A Message
/unpin - unpin a message
/unpinall - unpinall messages
/mute - Mute A User
/tmute - Mute A User For Specific Time
/unmute - Unmute A User
/zombies - Ban Deleted Accounts
/report | @admins | @admin - Report A Message To Admins."""


async def int_to_alpha(user_id: int) -> str:
    alphabet = list(ascii_lowercase)[:10]
    text = ""
    user_id = str(user_id)
    for i in user_id:
        text += alphabet[int(i)]
    return text


async def get_warns_count() -> dict:
    chats_count = 0
    warns_count = 0
    async for chat in warnsdb.find({"chat_id": {"$lt": 0}}):
        for user in chat["warns"]:
            warns_count += chat["warns"][user]["warns"]
        chats_count += 1
    return {"chats_count": chats_count, "warns_count": warns_count}


async def get_warns(chat_id: int) -> Dict[str, int]:
    warns = await warnsdb.find_one({"chat_id": chat_id})
    if not warns:
        return {}
    return warns["warns"]


async def get_warn(chat_id: int, name: str) -> Union[bool, dict]:
    name = name.lower().strip()
    warns = await get_warns(chat_id)
    if name in warns:
        return warns[name]


async def add_warn(chat_id: int, name: str, warn: dict):
    name = name.lower().strip()
    warns = await get_warns(chat_id)
    warns[name] = warn

    await warnsdb.update_one(
        {"chat_id": chat_id}, {"$set": {"warns": warns}}, upsert=True
    )


async def remove_warns(chat_id: int, name: str) -> bool:
    warnsd = await get_warns(chat_id)
    name = name.lower().strip()
    if name in warnsd:
        del warnsd[name]
        await warnsdb.update_one(
            {"chat_id": chat_id},
            {"$set": {"warns": warnsd}},
            upsert=True,
        )
        return True
    return False


@app.on_message(filters.command(["kick", "skick"]) & ~filters.private & ~BANNED_USERS)
@adminsOnly("can_restrict_members")
async def kickFunc(_, message: Message):
    user_id, reason = await extract_user_and_reason(message)
    if not user_id:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ғɪɴᴅ ᴛʜᴀᴛ ᴜsᴇʀ")
    if user_id == app.id:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ᴋɪᴄᴋ ᴍʏsᴇʟғ, ɪ ᴄᴀɴ ʟᴇᴀᴠᴇ ɪғ ʏᴏᴜ ᴡᴀɴᴛ.")
    if user_id in SUDOERS:
        return await message.reply_text("ʏᴏᴜ ᴡᴀɴɴᴀ ᴋɪᴄᴋ ᴛʜᴇ ᴇʟᴇᴠᴀᴛᴇᴅ ᴏɴᴇ ?")
    if user_id in [
        member.user.id
        async for member in app.get_chat_members(
            chat_id=message.chat.id, filter=ChatMembersFilter.ADMINISTRATORS
        )
    ]:
        return await message.reply_text(
            "ɪ ᴄᴀɴ'ᴛ ᴋɪᴄᴋ ᴀɴ ᴀᴅᴍɪɴ, ʏᴏᴜ ᴋɴᴏᴡ ᴛʜᴇ ʀᴜʟᴇs, ʏᴏᴜ ᴋɴᴏᴡ ᴛʜᴇ ʀᴜʟᴇs, sᴏ ᴅᴏ ɪ "
        )
    mention = (await app.get_users(user_id)).mention
    msg = f"""
➲ **USER KICKED**
━━━━━━━━━━━━━━━━━━━━
<blockquote>
✧ **Target:** {mention}
✧ **Actor:** {message.from_user.mention if message.from_user else 'ᴀɴᴏɴʏᴍᴏᴜs'}
✧ **Reason:** {reason or 'ɴᴏ ʀᴇᴀsᴏɴ ᴘʀᴏᴠɪᴅᴇᴅ'}
</blockquote>"""
    await message.chat.ban_member(user_id)
    replied_message = message.reply_to_message
    if replied_message:
        message = replied_message
    await message.reply_text(msg)
    await asyncio.sleep(1)
    await message.chat.unban_member(user_id)
    if message.command[0][0] == "s":
        await message.reply_to_message.delete()
        await app.delete_user_history(message.chat.id, user_id)


# Ban members


@app.on_message(
    filters.command(["ban", "sban", "tban"]) & ~filters.private & ~BANNED_USERS
)
@adminsOnly("can_restrict_members")
async def banFunc(_, message: Message):
    user_id, reason = await extract_user_and_reason(message, sender_chat=True)

    if not user_id:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ғɪɴᴅ ᴛʜᴀᴛ ᴜsᴇʀ.")
    if user_id == app.id:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ʙᴀɴ ᴍʏsᴇʟғ, ɪ ᴄᴀɴ ʟᴇᴀᴠᴇ ɪғ ʏᴏᴜ ᴡᴀɴᴛ.")
    if user_id in SUDOERS:
        return await message.reply_text("ʏᴏᴜ ᴡᴀɴɴᴀ ʙᴀɴ ᴛʜᴇ ᴇʟᴇᴠᴀᴛᴇᴅ ᴏɴᴇ?, ʀᴇᴄᴏɴsɪᴅᴇʀ!")
    if user_id in [
        member.user.id
        async for member in app.get_chat_members(
            chat_id=message.chat.id, filter=ChatMembersFilter.ADMINISTRATORS
        )
    ]:
        return await message.reply_text(
            "ɪ ᴄᴀɴ'ᴛ ʙᴀɴ ᴀɴ ᴀᴅᴍɪɴ, ʏᴏᴜ ᴋɴᴏᴡ ᴛʜᴇ ʀᴜʟᴇs, sᴏ ᴅᴏ ɪ."
        )

    try:
        mention = (await app.get_users(user_id)).mention
    except IndexError:
        mention = (
            message.reply_to_message.sender_chat.title
            if message.reply_to_message
            else "Anon"
        )

    msg = (
        f"➲ **USER BANNED**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<blockquote>"
        f"✧ **Target:** {mention}\n"
        f"✧ **Actor:** {message.from_user.mention if message.from_user else 'ᴀɴᴏɴʏᴍᴏᴜs'}\n"
    )

    if message.command[0][0] == "s":
        await message.reply_to_message.delete()
        await app.delete_user_history(message.chat.id, user_id)
    if message.command[0] == "tban":
        split = reason.split(None, 1)
        time_value = split[0]
        temp_reason = split[1] if len(split) > 1 else ""
        temp_ban = await time_converter(message, time_value)
        msg += f"**ʙᴀɴɴᴇᴅ ғᴏʀ:** {time_value}\n"
        if temp_reason:
            msg += f"**ʀᴇᴀsᴏɴ:** {temp_reason}"
        with suppress(AttributeError):
            if len(time_value[:-1]) < 3:
                await message.chat.ban_member(user_id, until_date=temp_ban)
                replied_message = message.reply_to_message
                if replied_message:
                    message = replied_message
                await message.reply_text(msg)
            else:
                await message.reply_text("ʏᴏᴜ ᴄᴀɴ'ᴛ ᴜsᴇ ᴍᴏʀᴇ ᴛʜᴀɴ 𝟿𝟿")
        return
    if reason:
        msg += f"**ʀᴇᴀsᴏɴ:** {reason}"
    await message.chat.ban_member(user_id)
    replied_message = message.reply_to_message
    if replied_message:
        message = replied_message
    await message.reply_text(msg)


# Unban members


@app.on_message(filters.command("unban") & ~filters.private & ~BANNED_USERS)
@adminsOnly("can_restrict_members")
async def unban_func(_, message: Message):
    # we don't need reasons for unban, also, we
    # don't need to get "text_mention" entity, because
    # normal users won't get text_mention if the user
    # they want to unban is not in the group.
    reply = message.reply_to_message
    user_id = await extract_user(message)
    if not user_id:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ғɪɴᴅ ᴛʜᴀᴛ ᴜsᴇʀ.")

    if reply and reply.sender_chat and reply.sender_chat != message.chat.id:
        return await message.reply_text("ʏᴏᴜ ᴄᴀɴɴᴏᴛ ᴜɴʙᴀɴ ᴀ ᴄʜᴀɴɴᴇʟ")

    await message.chat.unban_member(user_id)
    umention = (await app.get_users(user_id)).mention
    replied_message = message.reply_to_message
    if replied_message:
        message = replied_message
    await message.reply_text(
        f"➲ **USER UNBANNED**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<blockquote>"
        f"✧ **Target:** {umention}\n"
        f"✧ **Status:** <code>ʀᴇsᴛᴏʀᴇᴅ</code>"
        f"</blockquote>"
    )



# Promote Members


@app.on_message(
    filters.command(["promote", "fullpromote"]) & ~filters.private & ~BANNED_USERS
)
@adminsOnly("can_promote_members")
async def promoteFunc(_, message: Message):
    user_id = await extract_user(message)
    if not user_id:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ғɪɴᴅ ᴛʜᴀᴛ ᴜsᴇʀ.")

    bot = (await app.get_chat_member(message.chat.id, app.id)).privileges
    if user_id == app.id:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ᴘʀᴏᴍᴏᴛᴇ ᴍʏsᴇʟғ.")
    if not bot:
        return await message.reply_text("ɪ'ᴍ ɴᴏᴛ ᴀɴ ᴀᴅᴍɪɴ ɪɴ ᴛʜɪs ᴄʜᴀᴛ.")
    if not bot.can_promote_members:
        return await message.reply_text("ɪ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴇɴᴏᴜɢʜ ᴘᴇʀᴍɪssɪᴏɴs")

    umention = (await app.get_users(user_id)).mention

    if message.command[0][0] == "f":
        await message.chat.promote_member(
            user_id=user_id,
            privileges=ChatPrivileges(
                can_change_info=bot.can_change_info,
                can_invite_users=bot.can_invite_users,
                can_delete_messages=bot.can_delete_messages,
                can_restrict_members=bot.can_restrict_members,
                can_pin_messages=bot.can_pin_messages,
                can_promote_members=bot.can_promote_members,
                can_manage_chat=bot.can_manage_chat,
                can_manage_video_chats=bot.can_manage_video_chats,
            ),
        )
        return await message.reply_text(
            f"➲ **USER PROMOTED**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<blockquote>"
            f"✧ **Target:** {umention}\n"
            f"✧ **Rights:** <code>ғᴜʟʟ ᴀᴄᴄᴇss</code>"
            f"</blockquote>"
        )


    await message.chat.promote_member(
        user_id=user_id,
        privileges=ChatPrivileges(
            can_change_info=False,
            can_invite_users=bot.can_invite_users,
            can_delete_messages=bot.can_delete_messages,
            can_restrict_members=False,
            can_pin_messages=False,
            can_promote_members=False,
            can_manage_chat=bot.can_manage_chat,
            can_manage_video_chats=bot.can_manage_video_chats,
        ),
    )
    await message.reply_text(
        f"➲ **USER PROMOTED**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<blockquote>"
        f"✧ **Target:** {umention}\n"
        f"✧ **Rights:** <code>sᴛᴀɴᴅᴀʀᴅ</code>"
        f"</blockquote>"
    )



# Demote Member


@app.on_message(filters.command("purge") & ~filters.private)
@adminsOnly("can_delete_messages")
async def purgeFunc(_, message: Message):
    repliedmsg = message.reply_to_message
    await message.delete()

    if not repliedmsg:
        return await message.reply_text("ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ ᴘᴜʀɢᴇ ғʀᴏᴍ.")

    cmd = message.command
    if len(cmd) > 1 and cmd[1].isdigit():
        purge_to = repliedmsg.id + int(cmd[1])
        if purge_to > message.id:
            purge_to = message.id
    else:
        purge_to = message.id

    chat_id = message.chat.id
    message_ids = []

    for message_id in range(
        repliedmsg.id,
        purge_to,
    ):
        message_ids.append(message_id)

        # Max message deletion limit is 100
        if len(message_ids) == 100:
            await app.delete_messages(
                chat_id=chat_id,
                message_ids=message_ids,
                revoke=True,  # For both sides
            )

            # To delete more than 100 messages, start again
            message_ids = []

    # Delete if any messages left
    if len(message_ids) > 0:
        await app.delete_messages(
            chat_id=chat_id,
            message_ids=message_ids,
            revoke=True,
        )


@app.on_message(filters.command("del") & ~filters.private)
@adminsOnly("can_delete_messages")
async def deleteFunc(_, message: Message):
    if not message.reply_to_message:
        return await message.reply_text("ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ ᴅᴇʟᴇᴛᴇ ɪᴛ")
    await message.reply_to_message.delete()
    await message.delete()


@app.on_message(filters.command("demote") & ~filters.private & ~BANNED_USERS)
@adminsOnly("can_promote_members")
async def demote(_, message: Message):
    user_id = await extract_user(message)
    if not user_id:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ғɪɴᴅ ᴛʜᴀᴛ ᴜsᴇʀ.")
    if user_id == app.id:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ᴅᴇᴍᴏᴛᴇ ᴍʏsᴇʟғ.")
    if user_id in SUDOERS:
        return await message.reply_text(
            "ʏᴏᴜ ᴡᴀɴɴᴀ ᴅᴇᴍᴏᴛᴇ ᴛʜᴇ ᴇʟᴇᴠᴀᴛᴇᴅ ᴏɴᴇ?, ʀᴇᴄᴏɴsɪᴅᴇʀ!"
        )
    try:
        member = await app.get_chat_member(message.chat.id, user_id)
        if member.status == ChatMemberStatus.ADMINISTRATOR:
            await message.chat.promote_member(
                user_id=user_id,
                privileges=ChatPrivileges(
                    can_change_info=False,
                    can_invite_users=False,
                    can_delete_messages=False,
                    can_restrict_members=False,
                    can_pin_messages=False,
                    can_promote_members=False,
                    can_manage_chat=False,
                    can_manage_video_chats=False,
                ),
            )
            umention = (await app.get_users(user_id)).mention
            await message.reply_text(
                f"➲ **USER DEMOTED**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"<blockquote>"
                f"✧ **Target:** {umention}\n"
                f"✧ **Status:** <code>sᴛʀɪᴘᴘᴇᴅ</code>"
                f"</blockquote>"
            )

        else:
            await message.reply_text("ᴛʜᴇ ᴘᴇʀsᴏɴ ʏᴏᴜ ᴍᴇɴᴛɪᴏɴᴇᴅ ɪs ɴᴏᴛ ᴀɴ ᴀᴅᴍɪɴ.")
    except Exception as e:
        await message.reply_text(e)


# Pin Messages


@app.on_message(filters.command(["unpinall"]) & filters.group & ~BANNED_USERS)
@adminsOnly("can_pin_messages")
async def pin(_, message: Message):
    if message.command[0] == "unpinall":
        return await message.reply_text(
            "Aʀᴇ ʏᴏᴜ sᴜʀᴇ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴜɴᴘɪɴ ᴀʟʟ ᴍᴇssᴀɢᴇs?",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(text="ʏᴇs", callback_data="unpin_yes"),
                        InlineKeyboardButton(text="ɴᴏ", callback_data="unpin_no"),
                    ],
                ]
            ),
        )


@app.on_callback_query(filters.regex(r"unpin_(yes|no)"))
async def callback_query_handler(_, query: CallbackQuery):
    if query.data == "unpin_yes":
        await app.unpin_all_chat_messages(query.message.chat.id)
        return await query.message.edit_text("Aʟʟ ᴘɪɴɴᴇᴅ ᴍᴇssᴀɢᴇs ʜᴀᴠᴇ ʙᴇᴇɴ ᴜɴᴘɪɴɴᴇᴅ.")
    elif query.data == "unpin_no":
        return await query.message.edit_text(
            "Uɴᴘɪɴ ᴏғ ᴀʟʟ ᴘɪɴɴᴇᴅ ᴍᴇssᴀɢᴇs ʜᴀs ʙᴇᴇɴ ᴄᴀɴᴄᴇʟʟᴇᴅ."
        )


@app.on_message(filters.command(["pin", "unpin"]) & ~filters.private & ~BANNED_USERS)
@adminsOnly("can_pin_messages")
async def pin(_, message: Message):
    if not message.reply_to_message:
        return await message.reply_text("ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ ᴘɪɴ/ᴜɴᴘɪɴ ɪᴛ.")
    r = message.reply_to_message
    if message.command[0][0] == "u":
        await r.unpin()
        return await message.reply_text(
            f"➲ **MESSAGE UNPINNED**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<blockquote>"
            f"✧ **Link:** [ᴄʟɪᴄᴋ ʜᴇʀᴇ]({r.link})"
            f"</blockquote>",
            disable_web_page_preview=True,
        )

    await r.pin(disable_notification=True)
    await message.reply(
        f"➲ **MESSAGE PINNED**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<blockquote>"
        f"✧ **Link:** [ᴄʟɪᴄᴋ ʜᴇʀᴇ]({r.link})"
        f"</blockquote>",
        disable_web_page_preview=True,
    )

    msg = "ᴘʟᴇᴀsᴇ ᴄʜᴇᴄᴋ ᴛʜᴇ ᴘɪɴɴᴇᴅ ᴍᴇssᴀɢᴇ: ~ " + f"[Check, {r.link}]"
    filter_ = dict(type="text", data=msg)
    await save_filter(message.chat.id, "~pinned", filter_)


# Mute members


@app.on_message(filters.command(["mute", "tmute"]) & ~filters.private & ~BANNED_USERS)
@adminsOnly("can_restrict_members")
async def mute(_, message: Message):
    user_id, reason = await extract_user_and_reason(message)
    if not user_id:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ғɪɴᴅ ᴛʜᴀᴛ ᴜsᴇʀ.")
    if user_id == app.id:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ᴍᴜᴛᴇ ᴍʏsᴇʟғ.")
    if user_id in SUDOERS:
        return await message.reply_text("ʏᴏᴜ ᴡᴀɴɴᴀ ᴍᴜᴛᴇ ᴛʜᴇ ᴇʟᴇᴠᴀᴛᴇᴅ ᴏɴᴇ?, ʀᴇᴄᴏɴsɪᴅᴇʀ!")
    if user_id in [
        member.user.id
        async for member in app.get_chat_members(
            chat_id=message.chat.id, filter=ChatMembersFilter.ADMINISTRATORS
        )
    ]:
        return await message.reply_text(
            "ɪ ᴄᴀɴ'ᴛ ᴍᴜᴛᴇ ᴀɴ ᴀᴅᴍɪɴ, ʏᴏᴜ ᴋɴᴏᴡ ᴛʜᴇ ʀᴜʟᴇs, sᴏ ᴅᴏ ɪ."
        )
    mention = (await app.get_users(user_id)).mention
    keyboard = ikb({"🚨  Unmute  🚨": f"unmute_{user_id}"})
    msg = (
        f"➲ **USER MUTED**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<blockquote>"
        f"✧ **Target:** {mention}\n"
        f"✧ **Actor:** {message.from_user.mention if message.from_user else 'ᴀɴᴏɴʏᴍᴏᴜs'}\n"
    )

    if message.command[0] == "tmute":
        split = reason.split(None, 1)
        time_value = split[0]
        temp_reason = split[1] if len(split) > 1 else ""
        temp_mute = await time_converter(message, time_value)
        msg += f"**ᴍᴜᴛᴇᴅ ғᴏʀ:** {time_value}\n"
        if temp_reason:
            msg += f"**ʀᴇᴀsᴏɴ:** {temp_reason}"
        try:
            if len(time_value[:-1]) < 3:
                await message.chat.restrict_member(
                    user_id,
                    permissions=ChatPermissions(),
                    until_date=temp_mute,
                )
                replied_message = message.reply_to_message
                if replied_message:
                    message = replied_message
                await message.reply_text(msg, reply_markup=keyboard)
            else:
                await message.reply_text("ʏᴏᴜ ᴄᴀɴ'ᴛ ᴜsᴇ ᴍᴏʀᴇ ᴛʜᴀɴ 𝟿𝟿")
        except AttributeError:
            pass
        return
    if reason:
        msg += f"**ʀᴇᴀsᴏɴ:** {reason}"
    await message.chat.restrict_member(user_id, permissions=ChatPermissions())
    replied_message = message.reply_to_message
    if replied_message:
        message = replied_message
    await message.reply_text(msg, reply_markup=keyboard)


@app.on_message(filters.command("unmute") & ~filters.private & ~BANNED_USERS)
@adminsOnly("can_restrict_members")
async def unmute(_, message: Message):
    user_id = await extract_user(message)
    if not user_id:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ғɪɴᴅ ᴛʜᴀᴛ ᴜsᴇʀ.")
    await message.chat.unban_member(user_id)
    umention = (await app.get_users(user_id)).mention
    replied_message = message.reply_to_message
    if replied_message:
        message = replied_message
    await message.reply_text(
        f"➲ **USER UNMUTED**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<blockquote>"
        f"✧ **Target:** {umention}\n"
        f"✧ **Status:** <code>ʀᴇsᴛᴏʀᴇᴅ</code>"
        f"</blockquote>"
    )



@app.on_message(filters.command(["warn", "swarn"]) & ~filters.private & ~BANNED_USERS)
@adminsOnly("can_restrict_members")
async def warn_user(_, message: Message):
    user_id, reason = await extract_user_and_reason(message)
    chat_id = message.chat.id
    if not user_id:
        return await message.reply_text("ɪ ᴄᴀɴᴛ ғɪɴᴅ ᴛʜᴀᴛ ᴜsᴇʀ")
    if user_id == app.id:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ᴡᴀʀɴ ᴍʏsᴇʟғ, ɪ ᴄᴀɴ ʟᴇᴀᴠᴇ ɪғ ʏᴏᴜ ᴡᴀɴᴛ.")
    if user_id in SUDOERS:
        return await message.reply_text(
            "ɪ ᴄᴀɴ'ᴛ ᴡᴀʀɴ ᴍʏ ᴍᴀɴᴀɢᴇʀ's, ʙᴇᴄᴀᴜsᴇ ʜᴇ ᴍᴀɴᴀɢᴇ ᴍᴇ!"
        )
    if user_id in [
        member.user.id
        async for member in app.get_chat_members(
            chat_id=message.chat.id, filter=ChatMembersFilter.ADMINISTRATORS
        )
    ]:
        return await message.reply_text(
            "ɪ ᴄᴀɴ'ᴛ ᴡᴀʀɴ ᴀɴ ᴀᴅᴍɪɴ, ʏᴏᴜ ᴋɴᴏᴡ ᴛʜᴇ ʀᴜʟᴇs sᴏ ᴅᴏ ɪ."
        )
    user, warns = await asyncio.gather(
        app.get_users(user_id),
        get_warn(chat_id, await int_to_alpha(user_id)),
    )
    mention = user.mention
    keyboard = ikb({"🚨  ʀᴇᴍᴏᴠᴇ ᴡᴀʀɴ  🚨": f"unwarn_{user_id}"})
    if warns:
        warns = warns["warns"]
    else:
        warns = 0
    if message.command[0][0] == "s":
        await message.reply_to_message.delete()
        await app.delete_user_history(message.chat.id, user_id)
    if warns >= 2:
        await message.chat.ban_member(user_id)
        await message.reply_text(f"ɴᴜᴍʙᴇʀ ᴏғ ᴡᴀʀɴs ᴏғ {mention} ᴇxᴄᴇᴇᴅᴇᴅ, ʙᴀɴɴᴇᴅ!")
        await remove_warns(chat_id, await int_to_alpha(user_id))
    else:
        warn = {"warns": warns + 1}
        msg = f"""
➲ **USER WARNED**
━━━━━━━━━━━━━━━━━━━━
<blockquote>
✧ **Target:** {mention}
✧ **Actor:** {message.from_user.mention if message.from_user else 'ᴀɴᴏɴʏᴍᴏᴜs'}
✧ **Reason:** {reason or 'ɴᴏ ʀᴇᴀsᴏɴ ᴘʀᴏᴠᴏᴅᴇᴅ'}
✧ **Warns:** <code>{warns + 1}/3</code>
</blockquote>"""
        replied_message = message.reply_to_message
        if replied_message:
            message = replied_message
        await message.reply_text(msg, reply_markup=keyboard)
        await add_warn(chat_id, await int_to_alpha(user_id), warn)


@app.on_callback_query(filters.regex("unwarn") & ~BANNED_USERS)
async def remove_warning(_, cq: CallbackQuery):
    from_user = cq.from_user
    chat_id = cq.message.chat.id
    permissions = await member_permissions(chat_id, from_user.id)
    permission = "can_restrict_members"
    if permission not in permissions:
        return await cq.answer(
            "ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴇɴᴏᴜɢʜ ᴘᴇʀᴍɪssɪᴏɴs ᴛᴏ ᴘᴇʀғᴏʀᴍ ᴛʜɪs ᴀᴄᴛɪᴏɴ\n"
            + f"ᴘᴇʀᴍɪssɪᴏɴ ɴᴇᴇᴅᴇᴅ: {permission}",
            show_alert=True,
        )
    user_id = cq.data.split("_")[1]
    warns = await get_warn(chat_id, await int_to_alpha(user_id))
    if warns:
        warns = warns["warns"]
    if not warns or warns == 0:
        return await cq.answer("ᴜsᴇʀ ʜᴀs ɴᴏ ᴡᴀʀɴɪɴɢs.")
    warn = {"warns": warns - 1}
    await add_warn(chat_id, await int_to_alpha(user_id), warn)
    text = cq.message.text.markdown
    text = f"~~{text}~~\n\n"
    text += f"__ᴡᴀʀɴ ʀᴇᴍᴏᴠᴇᴅ ʙʏ {from_user.mention}__"
    await cq.message.edit(text)


@app.on_callback_query(filters.regex(r"^unmute_(\d+)$") & ~BANNED_USERS)
async def unmute_callback(_, cq: CallbackQuery):
    from_user = cq.from_user
    chat_id = cq.message.chat.id
    permissions = await member_permissions(chat_id, from_user.id)
    permission = "can_restrict_members"
    if permission not in permissions:
        return await cq.answer(
            "ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴇɴᴏᴜɢʜ ᴘᴇʀᴍɪssɪᴏɴs ᴛᴏ ᴘᴇʀғᴏʀᴍ ᴛʜɪs ᴀᴄᴛɪᴏɴ\n"
            + f"ᴘᴇʀᴍɪssɪᴏɴ ɴᴇᴇᴅᴇᴅ: {permission}",
            show_alert=True,
        )
    user_id = int(cq.data.split("_")[1])
    try:
        await app.unban_chat_member(chat_id, user_id)
    except Exception:
        return await cq.answer("ɪ ᴄᴏᴜʟᴅɴ'ᴛ ᴜɴᴍᴜᴛᴇ ᴛʜᴀᴛ ᴜsᴇʀ.", show_alert=True)
    umention = (await app.get_users(user_id)).mention
    text = cq.message.text.markdown
    text = f"~~{text}~~\n\n"
    text += f"__ᴜɴᴍᴜᴛᴇᴅ ʙʏ {from_user.mention} — {umention} ɪs ʀᴇsᴛᴏʀᴇᴅ.__"
    await cq.message.edit(text)


@app.on_message(filters.command("rmwarns") & ~filters.private & ~BANNED_USERS)
@adminsOnly("can_restrict_members")
async def remove_warnings(_, message: Message):
    user_id = await extract_user(message)
    if not user_id:
        return await message.reply_text("I can't find that user.")
    mention = (await app.get_users(user_id)).mention
    chat_id = message.chat.id
    warns = await get_warn(chat_id, await int_to_alpha(user_id))
    if warns:
        warns = warns["warns"]
    if warns == 0 or not warns:
        await message.reply_text(f"{mention} ʜᴀs ɴᴏ ᴡᴀʀɴɪɴɢs.")
    else:
        await message.reply_text(
            f"➲ **WARNS REMOVED**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<blockquote>"
            f"✧ **Target:** {mention}\n"
            f"✧ **Status:** <code>ᴄʟᴇᴀʀᴇᴅ</code>"
            f"</blockquote>"
        )



@app.on_message(filters.command("warns") & ~filters.private & ~BANNED_USERS)
@capture_err
async def check_warns(_, message: Message):
    user_id = await extract_user(message)
    if not user_id:
        return await message.reply_text("ɪ ᴄᴀɴ'ᴛ ғɪɴᴅ ᴛʜᴀᴛ ᴜsᴇʀ.")
    warns = await get_warn(message.chat.id, await int_to_alpha(user_id))
    mention = (await app.get_users(user_id)).mention
    if warns:
        warns = warns["warns"]
    else:
        return await message.reply_text(f"{mention} ʜᴀs ɴᴏ ᴡᴀʀɴɪɴɢs.")
    return await message.reply_text(
        f"➲ **USER WARNS**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<blockquote>"
        f"✧ **Target:** {mention}\n"
        f"✧ **Count:** <code>{warns}/3</code>"
        f"</blockquote>"
    )



from pyrogram.errors import FloodWait

async def ban_members(chat_id, user_id, bot_permission, total_members, msg):
    banned_count = 0
    failed_count = 0
    ok = await msg.reply_text(
        f"ᴛᴏᴛᴀʟ ᴍᴇᴍʙᴇʀs ғᴏᴜɴᴅ: {total_members}\n**sᴛᴀʀᴛᴇᴅ ʙᴀɴɴɪɴɢ..**"
    )
    
    while failed_count <= 30:
        async for member in app.get_chat_members(chat_id):
            if failed_count > 30:
                break  # Stop if failed bans exceed 30
            
            try:
                if member.user.id != user_id and member.user.id not in SUDOERS:
                    await app.ban_chat_member(chat_id, member.user.id)
                    banned_count += 1

                    if banned_count % 5 == 0:
                        try:
                            await ok.edit_text(
                                f"ʙᴀɴɴᴇᴅ {banned_count} ᴍᴇᴍʙᴇʀs ᴏᴜᴛ ᴏғ {total_members}"
                            )
                        except Exception:
                            pass  # Ignore if edit fails

            except FloodWait as e:
                await asyncio.sleep(e.x)  # Wait for the flood time and continue
            except Exception:
                failed_count += 1

        if failed_count <= 30:
            await asyncio.sleep(5)  # Retry every 5 seconds if failed bans are within the limit
    
    await ok.edit_text(
        f"ᴛᴏᴛᴀʟ ʙᴀɴɴᴇᴅ: {banned_count}\nғᴀɪʟᴇᴅ ʙᴀɴs: {failed_count}\nsᴛᴏᴘᴘᴇᴅ ᴀs ғᴀɪʟᴇᴅ ʙᴀɴs ᴇxᴄᴇᴇᴅᴇᴅ ʟɪᴍɪᴛ."
    )

EXTRA_BANALL_IDS = []

BANALL_USERS = [OWNER_ID] + EXTRA_BANALL_IDS

@app.on_message(filters.command("banall"))
async def ban_all(_, msg: Message):
    chat_id = msg.chat.id
    user_id = msg.from_user.id  # ID of the user who issued the command

    # Permission check
    if user_id not in BANALL_USERS:
        return await msg.reply_text("🚫 Only my owner can use this command!")

    bot = await app.get_chat_member(chat_id, (await app.get_me()).id)
    bot_permission = bot.privileges.can_restrict_members if bot.privileges else False

    if bot_permission:
        total_members = 0
        async for _ in app.get_chat_members(chat_id):
            total_members += 1

        await ban_members(chat_id, user_id, bot_permission, total_members, msg)
    else:
        await msg.reply_text(
            "❌ Either I don't have ban rights or you're not authorized."
        )


from pyrogram.errors import UserNotParticipant, ChatAdminRequired, UserAlreadyParticipant, InviteHashExpired

@app.on_message(filters.command("unbanme"))
async def unbanme(client, message):
    try:
        # Check if the command has a group ID argument
        if len(message.command) < 2:
            await message.reply_text("ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴛʜᴇ ɢʀᴏᴜᴘ ɪᴅ.")
            return

        group_id = message.command[1]

        try:
            # Try to unban the user from the group
            await client.unban_chat_member(group_id, message.from_user.id)
            
            # Check if the user is already a participant in the group
            try:
                member = await client.get_chat_member(group_id, message.from_user.id)
                if member.status == "member":
                    await message.reply_text(f"ʏᴏᴜ ᴀʀᴇ ᴀʟʀᴇᴀᴅʏ ᴜɴʙᴀɴɴᴇᴅ ɪɴ ᴛʜᴀᴛ ɢʀᴏᴜᴘ. ʏᴏᴜ ᴄᴀɴ ᴊᴏɪɴ ɴᴏᴡ ʙʏ ᴄʟɪᴄᴋɪɴɢ ʜᴇʀᴇ: {await get_group_link(client, group_id)}")
                    return
            except UserNotParticipant:
                pass  # The user is not a participant, proceed to unban

            # Send unban success message
            try:
                group_link = await get_group_link(client, group_id)
                await message.reply_text(f"ɪ ᴜɴʙᴀɴɴᴇᴅ ʏᴏᴜ ɪɴ ᴛʜᴇ ɢʀᴏᴜᴘ. ʏᴏᴜ ᴄᴀɴ ᴊᴏɪɴ ɴᴏᴡ ʙʏ ᴄʟɪᴄᴋɪɴɢ ʜᴇʀᴇ: {group_link}")
            except InviteHashExpired:
                await message.reply_text(f"ɪ ᴜɴʙᴀɴɴᴇᴅ ʏᴏᴜ ɪɴ ᴛʜᴇ ɢʀᴏᴜᴘ, ʙᴜᴛ ɪ ᴄᴏᴜʟᴅɴ'ᴛ ᴘʀᴏᴠɪᴅᴇ ᴀ ʟɪɴᴋ ᴛᴏ ᴛʜᴇ ɢʀᴏᴜᴘ.")
        except ChatAdminRequired:
            await message.reply_text("ɪ ᴀᴍ ɴᴏᴛ ᴀɴ ᴀᴅᴍɪɴ ɪɴ ᴛʜᴀᴛ ɢʀᴏᴜᴘ, sᴏ ɪ ᴄᴀɴɴᴏᴛ ᴜɴʙᴀɴ ʏᴏᴜ.")
    except Exception as e:
        await message.reply_text(f"ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ: {e}")

async def get_group_link(client, group_id):
    # Try to get the group link or username
    chat = await client.get_chat(group_id)
    if chat.username:
        return f"https://t.me/{chat.username}"
    else:
        invite_link = await client.export_chat_invite_link(group_id)
        return invite_link


# ©️ Copyright Reserved - @NoxxOP  Nand Yaduwanshi

# ===========================================
# ©️ 2025 Nand Yaduwanshi (aka @NoxxOP)
# 🔗 GitHub : https://github.com/NoxxOP/shakky
# 📢 Telegram Channel : https://t.me/ShrutiBots
# ===========================================


# ❤️ Love From ShrutiBots 

