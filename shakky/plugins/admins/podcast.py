from pyrogram import filters
from pyrogram.types import Message
from shakky import app
from shakky.utils.database import is_podcast, podcast_on, podcast_off
from shakky.utils.decorators import AdminRightsCheck
from config import BANNED_USERS

@app.on_message(filters.command(["podcast"]) & filters.group & ~BANNED_USERS)
@AdminRightsCheck
async def podcast_mode_command(client, message: Message, _, chat_id):
    """
    Toggle the AI Podcast Host mode.
    """
    if await is_podcast(chat_id):
        await podcast_off(chat_id)
        await message.reply_text(
            "<blockquote>🎙️ <b>AI Podcast Host: OFF</b></blockquote>\n"
            "➲ <i>The Radio Host has left the studio. Music will now play normally.</i>"
        )
    else:
        await podcast_on(chat_id)
        await message.reply_text(
            "<blockquote>🎙️ <b>AI Podcast Host: ON</b></blockquote>\n"
            "➲ <i>Welcome to Shakky FM! Your AI Host will now introduce your tracks live.</i>"
        )
