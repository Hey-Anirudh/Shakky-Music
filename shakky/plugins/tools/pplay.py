import asyncio
import logging
import random
from pyrogram import filters
from shakky import app
from shakky.utils.database import get_lang, is_active_chat
from shakky.utils.stream.stream import stream
from shakky.platforms.Youtube import youtube
from shakky.utils.groq import get_groq_playlist
from shakky.utils.stream.queue import put_queue
from config import BANNED_USERS
from strings import get_string

logger = logging.getLogger(__name__)

# Cleaned up background task code

@app.on_message(
    filters.command(["pplay", "pmusic"]) & filters.group & ~BANNED_USERS
)
async def pplay_command(client, message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_name = message.from_user.first_name

    # Extract query
    if len(message.command) < 2:
        return await message.reply_text(
            "➲ **Usage:** `/pplay [mood]`\n*Try: /pplay sad, /pplay romantic, /pplay party*"
        )

    query = message.text.split(None, 1)[1].strip()
    if not query:
        return await message.reply_text("➲ **Please provide a mood or genre.**")

    try:
        await message.delete()
    except:
        pass

    language = await get_lang(chat_id)
    _ = get_string(language)

    mystic = await message.reply_text(
        f"➲ **AI Mood Search Started...**\n*Curating 50 bangers for:* `{query}`..."
    )

    try:
        # Get AI playlist from Groq
        songs_list = await get_groq_playlist(query)

        if not songs_list or not isinstance(songs_list, list):
            return await mystic.edit_text("➲ **AI curation failed. Fallback to normal play or try again.**")

        # Start with a random song from the list to keep it fresh
        playlist = songs_list.copy()
        random.shuffle(playlist)
        
        # Just-In-Time resolution for the first song too (avoids double search spam)
        first_song = playlist[0]
        details = {
            "title": first_song.title(),
            "link": first_song,
            "vidid": first_song,
            "duration_min": "3:30",
            "thumb": "https://files.catbox.moe/5ni0on.jpg", # Default YouTube placeholder
            "raw_query": first_song,
        }

        # Stream first song (this will trigger the ONLY 'find' request needed)
        await stream(
            _,
            mystic,
            user_id,
            details,
            chat_id,
            user_name,
            message.chat.id,
            video=False,
            streamtype="youtube",
            forceplay=True,
            raw_query=first_song,
        )

        # Fast-queue the rest of the playlist
        for song in playlist[1:]:

            await put_queue(
                chat_id,
                message.chat.id,
                f"vid_{song}",
                song,
                "3:30",
                user_name,
                song,
                user_id,
                "audio"
            )

        # Removed background task: Each track resolves naturally JUST IN TIME when its turn comes.

        # Notify success (stream() already sent the main card)
        try:
            await mystic.delete()
        except:
            pass

    except Exception as e:
        logger.error(f"PPlay Error: {e}", exc_info=True)
        try:
            await mystic.edit_text(f"➲ **Premium Play Failed:** `{str(e)}`")
        except:
            pass
