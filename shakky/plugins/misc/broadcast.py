import asyncio
from pyrogram import filters
from pyrogram.enums import ChatMembersFilter
from pyrogram.errors import FloodWait

from shakky import app
from shakky.misc import SUDOERS
from shakky.utils.database import (
    get_active_chats,
    get_authuser_names,
    get_client,
    get_served_chats,
    get_served_users,
)
from shakky.utils.decorators.language import language
from shakky.utils.formatters import alpha_to_int
from config import adminlist
from config import OWNER_ID

IS_BROADCASTING = False

@app.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
@language
async def broadcast_message(client, message, _):
    global IS_BROADCASTING
    if message.reply_to_message:
        x = message.reply_to_message.id
        y = message.chat.id
    else:
        if len(message.command) < 2:
            return await message.reply_text(_["broad_2"])
        query = message.text.split(None, 1)[1]
        
        # Strip flags from message text to get the clean query
        for flag in ["-pin", "-nobot", "-pinloud", "-assistant", "-user"]:
            query = query.replace(flag, "")
        query = query.strip()
        
        if query == "" and not message.reply_to_message:
            return await message.reply_text(_["broad_8"])

    IS_BROADCASTING = True
    await message.reply_text(_["broad_1"])

    sent = 0
    pin = 0
    susr = 0

    # 1. Broadcast to Groups (unless -nobot is present)
    if "-nobot" not in message.text:
        schats = await get_served_chats()
        for chat in schats:
            chat_id = int(chat["chat_id"])
            try:
                m = (
                    await app.forward_messages(chat_id, y, x)
                    if message.reply_to_message
                    else await app.send_message(chat_id, text=query)
                )
                if "-pin" in message.text:
                    try:
                        await m.pin(disable_notification=True)
                        pin += 1
                    except:
                        pass
                elif "-pinloud" in message.text:
                    try:
                        await m.pin(disable_notification=False)
                        pin += 1
                    except:
                        pass
                sent += 1
                await asyncio.sleep(0.2)
            except FloodWait as fw:
                if fw.value > 200:
                    continue
                await asyncio.sleep(fw.value)
            except:
                continue

    # 2. Broadcast to Users (Always enabled by default, can use -user flag for compatibility or just leave it)
    # Most bot admins want both.
    susers = await get_served_users()
    for user in susers:
        user_id = int(user["user_id"])
        try:
            m = (
                await app.forward_messages(user_id, y, x)
                if message.reply_to_message
                else await app.send_message(user_id, text=query)
            )
            susr += 1
            await asyncio.sleep(0.2)
        except FloodWait as fw:
            if fw.value > 200:
                continue
            await asyncio.sleep(fw.value)
        except:
            continue

    # 3. Assistant Broadcast (optional flag)
    if "-assistant" in message.text:
        aw = await message.reply_text(_["broad_5"])
        text = _["broad_6"]
        from shakky.core.userbot import assistants

        for num in assistants:
            a_sent = 0
            client = await get_client(num)
            async for dialog in client.get_dialogs():
                try:
                    await client.forward_messages(
                        dialog.chat.id, y, x
                    ) if message.reply_to_message else await client.send_message(
                        dialog.chat.id, text=query
                    )
                    a_sent += 1
                    await asyncio.sleep(3)
                except FloodWait as fw:
                    if fw.value > 200:
                        continue
                    await asyncio.sleep(fw.value)
                except:
                    continue
            text += _["broad_7"].format(num, a_sent)
        try:
            await aw.edit_text(text)
        except:
            pass

    # Final Summary
    summary = ""
    if sent > 0:
        summary += _["broad_3"].format(sent, pin) + "\n"
    if susr > 0:
        summary += _["broad_4"].format(susr)
    
    if summary:
        try:
            await message.reply_text(summary)
        except:
            pass
            
    IS_BROADCASTING = False

async def auto_clean():
    while not await asyncio.sleep(10):
        try:
            served_chats = await get_active_chats()
            for chat_id in served_chats:
                if chat_id not in adminlist:
                    adminlist[chat_id] = []
                    async for user in app.get_chat_members(
                        chat_id, filter=ChatMembersFilter.ADMINISTRATORS
                    ):
                        if user.privileges and user.privileges.can_manage_video_chats:
                            adminlist[chat_id].append(user.user.id)
                    authusers = await get_authuser_names(chat_id)
                    for user in authusers:
                        u_id = await alpha_to_int(user)
                        adminlist[chat_id].append(u_id)
        except:
            continue

asyncio.create_task(auto_clean())
