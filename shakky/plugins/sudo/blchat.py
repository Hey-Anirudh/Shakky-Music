from pyrogram import filters
from pyrogram.types import Message

from shakky import app
from shakky.misc import SUDOERS
from shakky.utils.database import blacklist_chat, blacklisted_chats, whitelist_chat
from shakky.utils.decorators.language import language
from config import BANNED_USERS


@app.on_message(filters.command(["blchat", "blacklistchat"]) & SUDOERS)
@language
async def blacklist_chat_func(client, message: Message, _):
    if len(message.command) != 2:
        return await message.reply_text("➲ **BLACKLIST**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>**Usage:** /blacklistchat [chat_id]</blockquote>")
    chat_id = int(message.text.strip().split()[1])
    if chat_id in await blacklisted_chats():
        return await message.reply_text("➲ **BLACKLIST**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>ᴛʜɪs ᴄʜᴀᴛ ɪs ᴀʟʀᴇᴀᴅʏ ʙʟᴀᴄᴋʟɪsᴛᴇᴅ!</blockquote>")
    blacklisted = await blacklist_chat(chat_id)
    if blacklisted:
        await message.reply_text("➲ **BLACKLIST**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>sᴜᴄᴄᴇssғᴜʟʟʏ ʙʟᴀᴄᴋʟɪsᴛᴇᴅ ᴛʜᴇ ᴄʜᴀᴛ.</blockquote>")
    else:
        await message.reply_text("➲ **BLACKLIST**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>sᴏᴍᴇᴛʜɪɴɢ ᴡᴇɴᴛ ᴡʀᴏɴɢ. ᴛʀʏ ᴀɢᴀɪɴ.</blockquote>")
    try:
        await app.leave_chat(chat_id)
    except:
        pass


@app.on_message(
    filters.command(["whitelistchat", "unblacklistchat", "unblchat"]) & SUDOERS
)
@language
async def white_funciton(client, message: Message, _):
    if len(message.command) != 2:
        return await message.reply_text("➲ **WHITELIST**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>**Usage:** /whitelistchat [chat_id]</blockquote>")
    chat_id = int(message.text.strip().split()[1])
    if chat_id not in await blacklisted_chats():
        return await message.reply_text("➲ **WHITELIST**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>ᴛʜɪs ᴄʜᴀᴛ ɪs ɴᴏᴛ ʙʟᴀᴄᴋʟɪsᴛᴇᴅ!</blockquote>")
    whitelisted = await whitelist_chat(chat_id)
    if whitelisted:
        return await message.reply_text("➲ **WHITELIST**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>sᴜᴄᴄᴇssғᴜʟʟʏ ᴡʜɪᴛᴇʟɪsᴛᴇᴅ ᴛʜᴇ ᴄʜᴀᴛ.</blockquote>")
    await message.reply_text("➲ **WHITELIST**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>sᴏᴍᴇᴛʜɪɴɢ ᴡᴇɴᴛ ᴡʀᴏɴɢ. ᴛʀʏ ᴀɢᴀɪɴ.</blockquote>")


@app.on_message(filters.command(["blchats", "blacklistedchats"]) & ~BANNED_USERS)
@language
async def all_chats(client, message: Message, _):
    text = "➲ **BLACKLISTED CHATS**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>"
    j = 0
    for count, chat_id in enumerate(await blacklisted_chats(), 1):
        try:
            title = (await app.get_chat(chat_id)).title
        except:
            title = "ᴘʀɪᴠᴀᴛᴇ ᴄʜᴀᴛ"
        j = 1
        text += f"✧ {count}. {title} [<code>{chat_id}</code>]\n"
    text += "</blockquote>"
    if j == 0:
        await message.reply_text(f"➲ **BLACKLIST**\n━━━━━━━━━━━━━━━━━━━━\n<blockquote>ɴᴏ ʙʟᴀᴄᴋʟɪsᴛᴇᴅ ᴄʜᴀᴛs ғᴏᴜɴᴅ.</blockquote>")
    else:
        await message.reply_text(text)
