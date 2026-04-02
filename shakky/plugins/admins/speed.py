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
    filters.command(["speed", "playback", "cspeed", "cplayback"])
    & filters.group
    & ~BANNED_USERS
)
@AdminRightsCheck
async def speed_command(client, message: Message, _, chat_id):
    playing = db.get(chat_id)
    if not playing:
        return await message.reply_text(_["queue_2"])
    
    speed_msg = message.text.split()
    if len(speed_msg) == 1:
        return await message.reply_text(
            "**sᴘᴇᴇᴅ ᴄᴏɴᴛʀᴏʟ:**\n/speed [0.5, 0.75, 1.0, 1.5, 2.0]",
            reply_markup=close_markup(_),
        )
    
    speed = speed_msg[1]
    if speed not in ["0.5", "0.75", "1.0", "1.5", "2.0"]:
        return await message.reply_text("Please specify a valid speed: 0.5, 0.75, 1.0, 1.5, or 2.0")
        
    duration_seconds = int(playing[0].get("seconds", 0))
    if duration_seconds == 0:
        return await message.reply_text("Cannot change speed of a live stream.")

    file_path = playing[0]["file"]
    
    mystic = await message.reply_text(f"Applying {speed}x speed. Please wait a few seconds...")
    try:
        await Nand.speedup_stream(
            chat_id,
            file_path,
            speed,
            playing
        )
    except Exception as e:
        return await mystic.edit_text(f"Failed to change speed: {e}")
        
    await mystic.edit_text(
        f"**Sᴘᴇᴇᴅ Mᴏᴅɪғɪᴇᴅ ᴛᴏ {speed}x 🚀**\n\n_Note: Speed changes are broadcasted to the WebApp as well._",
        reply_markup=close_markup(_)
    )
