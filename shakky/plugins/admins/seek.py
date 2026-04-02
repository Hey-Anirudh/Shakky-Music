from pyrogram import filters
from pyrogram.types import Message

from shakky import app
from shakky.core.call import Nand
from shakky.misc import db
from shakky.utils.database import is_music_playing, music_on
from shakky.utils.decorators import AdminRightsCheck
from shakky.utils.inline import close_markup
from config import BANNED_USERS


@app.on_message(
    filters.command(["seek", "cseek", "seekback", "cseekback"])
    & filters.group
    & ~BANNED_USERS
)
@AdminRightsCheck
async def seek_comm(client, message: Message, _, chat_id):
    if len(message.command) == 1:
        return await message.reply_text(_["admin_20"])
    
    query = message.text.split(None, 1)[1].strip()
    if not query.isnumeric():
        return await message.reply_text(_["admin_21"])
    
    playing = db.get(chat_id)
    if not playing:
        return await message.reply_text(_["queue_2"])
    
    duration_seconds = int(playing[0].get("seconds", 0))
    if duration_seconds == 0:
        return await message.reply_text(_["admin_22"])
        
    played_seconds = int(playing[0].get("played", 0))
    file_path = playing[0]["file"]
    duration_played = int(query)
    
    if message.command[0] in ["seekback", "cseekback"]:
        if (played_seconds - duration_played) <= 10:
            return await message.reply_text(_["admin_23"])
        to_seek = played_seconds - duration_played
    else:
        if (duration_seconds - (played_seconds + duration_played)) <= 10:
            return await message.reply_text(_["admin_23"])
        to_seek = played_seconds + duration_played
        
    mystic = await message.reply_text(_["admin_24"])
    
    import time
    from shakky.utils.formatters import seconds_to_min
    to_seek_str = seconds_to_min(to_seek)
    
    try:
        await Nand.seek_stream(
            chat_id,
            file_path,
            to_seek_str,
            duration_seconds,
            playing[0].get("streamtype", "audio")
        )
    except Exception as e:
        return await mystic.edit_text(f"Seek Failed: {e}")
        
    playing[0]["played"] = to_seek
    playing[0]["start_time"] = time.time() - to_seek # Re-align start time for accurate WebApp elapsed tracking
    
    await mystic.edit_text(
        _["admin_25"].format(to_seek_str) + "\n_VC & WebApp Synced_",
        reply_markup=close_markup(_)
    )
