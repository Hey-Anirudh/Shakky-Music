from pyrogram import filters
from pyrogram.types import Message

from shakky import app
from shakky.misc import SUDOERS
from shakky.utils.database import (
    add_gmuted_user,
    is_gmuted_user,
    remove_gmuted_user,
    get_gmuted_users,
)
from shakky.utils.decorators.language import language
from shakky.utils.extraction import extract_user
from config import GMUTED_USERS


@app.on_message(filters.command(["gmute"]) & SUDOERS)
@language
async def global_mute(client, message: Message, _):
    if not message.reply_to_message:
        if len(message.command) != 2:
            return await message.reply_text(_["general_1"])
    user = await extract_user(message)
    if user.id == message.from_user.id:
        return await message.reply_text(_["gmute_1"])
    elif user.id == app.id:
        return await message.reply_text(_["gmute_1"])
    elif user.id in SUDOERS:
        return await message.reply_text(_["gmute_2"])
    
    is_gmuted = await is_gmuted_user(user.id)
    if is_gmuted:
        return await message.reply_text(_["gmute_3"])
    
    await add_gmuted_user(user.id)
    GMUTED_USERS.add(user.id)
    
    await message.reply_text(
        _["gmute_4"].format(user.mention, message.from_user.mention)
    )


@app.on_message(filters.command(["ungmute"]) & SUDOERS)
@language
async def global_unmute(client, message: Message, _):
    if not message.reply_to_message:
        if len(message.command) != 2:
            return await message.reply_text(_["general_1"])
    user = await extract_user(message)
    
    is_gmuted = await is_gmuted_user(user.id)
    if not is_gmuted:
        return await message.reply_text(_["gmute_6"])
    
    await remove_gmuted_user(user.id)
    if user.id in GMUTED_USERS:
        GMUTED_USERS.remove(user.id)
        
    await message.reply_text(
        _["gmute_5"].format(user.mention, message.from_user.mention)
    )


@app.on_message(filters.command(["gmutedusers", "gmuteportal"]) & SUDOERS)
@language
async def gmuted_list(client, message: Message, _):
    users = await get_gmuted_users()
    if not users:
        return await message.reply_text(_["gmute_8"])
    
    msg = _["gmute_7"]
    count = 0
    for user_id in users:
        count += 1
        try:
            user = await app.get_users(user_id)
            user = user.first_name if not user.mention else user.mention
            msg += f"{count}➤ {user} [<code>{user_id}</code>]\n"
        except Exception:
            msg += f"{count}➤ <code>{user_id}</code>\n"
            continue
            
    await message.reply_text(msg)
