import logging
from functools import wraps
from traceback import format_exc as err
from pyrogram.errors.exceptions.forbidden_403 import ChatWriteForbidden
from pyrogram.types import Message
from shakky import app
from shakky.misc import SUDOERS

async def member_permissions(chat_id: int, user_id: int):
    perms = []
    try:
        member = await app.get_chat_member(chat_id, user_id)
        if not member.privileges:
            return []
        p = member.privileges
        if p.can_post_messages:
            perms.append("can_post_messages")
        if p.can_edit_messages:
            perms.append("can_edit_messages")
        if p.can_delete_messages:
            perms.append("can_delete_messages")
        if p.can_restrict_members:
            perms.append("can_restrict_members")
        if p.can_promote_members:
            perms.append("can_promote_members")
        if p.can_change_info:
            perms.append("can_change_info")
        if p.can_invite_users:
            perms.append("can_invite_users")
        if p.can_pin_messages:
            perms.append("can_pin_messages")
        if p.can_manage_video_chats:
            perms.append("can_manage_video_chats")
    except Exception:
        return []
    return perms

async def authorised(func, subFunc2, client, message, *args, **kwargs):
    chatID = message.chat.id
    try:
        await func(client, message, *args, **kwargs)
    except ChatWriteForbidden:
        await app.leave_chat(chatID)
    except Exception as e:
        logging.exception(e)
        try:
            await message.reply_text(str(e))
        except:
            pass
    return subFunc2

async def unauthorised(
    message: Message, permission, subFunc2, bot_lacking_permission=False
):
    chatID = message.chat.id
    if bot_lacking_permission:
        text = (
            "I don't have the required permission to perform this action."
            + f"\n<b>Permission:</b> <code>{permission}</code>"
        )
    else:
        text = (
            "You don't have the required permission to perform this action."
            + f"\n<b>Permission:</b> <code>{permission}</code>"
        )
    try:
        await message.reply_text(text)
    except ChatWriteForbidden:
        await app.leave_chat(chatID)
    return subFunc2

async def bot_permissions(chat_id: int):
    return await member_permissions(chat_id, app.id)

def adminsOnly(permission):
    def subFunc(func):
        @wraps(func)
        async def subFunc2(client, message: Message, *args, **kwargs):
            chatID = message.chat.id
            if not message.chat.type in ["group", "supergroup"]:
                return await func(client, message, *args, **kwargs)
                
            bot_perms = await bot_permissions(chatID)
            if permission not in bot_perms:
                return await unauthorised(
                    message, permission, subFunc2, bot_lacking_permission=True
                )

            if not message.from_user:
                if message.sender_chat and message.sender_chat.id == message.chat.id:
                    return await authorised(func, subFunc2, client, message, *args, **kwargs)
                return await unauthorised(message, permission, subFunc2)

            userID = message.from_user.id
            permissions = await member_permissions(chatID, userID)
            if userID not in SUDOERS and permission not in permissions:
                return await unauthorised(message, permission, subFunc2)
            return await authorised(func, subFunc2, client, message, *args, **kwargs)
        return subFunc2
    return subFunc
