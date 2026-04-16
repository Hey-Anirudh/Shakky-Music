from pyrogram import filters
from pyrogram.types import Message
from shakky import app
from shakky.misc import SUDOERS
from config import GMUTED_USERS

@app.on_message(GMUTED_USERS & filters.group, group=-1)
async def gmute_watcher_func(client, message: Message):
    if not message.from_user:
        return
    
    # Check if user is sudo
    if message.from_user.id in SUDOERS:
        return
    
    try:
        await message.delete()
    except:
        pass
