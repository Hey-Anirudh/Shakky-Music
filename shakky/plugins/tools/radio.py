import random
import asyncio
from pyrogram import filters
from shakky import app
from shakky.core.call import ani
from shakky.misc import db
from shakky.utils.database import is_active_chat, get_lang
from shakky.utils.stream.stream import stream
from shakky.utils.stream.queue import put_queue
from strings import get_string
import config

async def fill_radio_queue(chat_id, original_chat_id, user_id, user_name, messages):
    """Background task: shuffle all DB songs and fill the queue for non-stop radio"""
    random.shuffle(messages)
    for msg in messages:
        try:
            await asyncio.sleep(1)
            title = (msg.audio.title if msg.audio and msg.audio.title else
                     (msg.audio.file_name if msg.audio else "Smash Radio Hit"))
            duration = "3:30"
            if msg.audio and msg.audio.duration:
                m = msg.audio.duration // 60
                s = msg.audio.duration % 60
                duration = f"{m}:{s:02d}"

            # file MUST use "vid_" prefix so change_stream calls YouTube.download()
            # vidid uses "db_" prefix so our download_song fetches from the DB channel
            await put_queue(
                chat_id,
                original_chat_id,
                f"vid_db_{msg.id}",   # vid_ prefix → change_stream takes correct branch
                title,
                duration,
                user_name,
                f"db_{msg.id}",       # vidid → download_song fetches from DB channel
                user_id,
                "audio",
            )
        except Exception as e:
            continue

@app.on_message(filters.command(["radio", "smashradio"]) & filters.group)
async def smash_radio_handler(client, message):
    mystic = await message.reply_text("➲ **Initializing Smash Radio...**\n*Tuning into your database...*")

    chat_id = message.chat.id
    user_id = message.from_user.id
    user_name = message.from_user.first_name

    if await is_active_chat(chat_id):
        return await mystic.edit_text("➲ **Smash Radio is already live! Use /skip to change the song or /end to stop.**")

    # Get language for stream()
    language = await get_lang(chat_id)
    _ = get_string(language)

    channel_username = getattr(config, "CHANNEL_USERNAME", "@smashmusicdb")

    try:
        # Pick the correct Pyrogram userbot (not PyTgCalls instance)
        userbot = None
        for attr, string_attr in [
            ("userbot1", "STRING1"), ("userbot2", "STRING2"),
            ("userbot3", "STRING3"), ("userbot4", "STRING4"), ("userbot5", "STRING5"),
        ]:
            if getattr(config, string_attr, None):
                userbot = getattr(ani, attr)
                break

        if not userbot:
            return await mystic.edit_text("➲ **No assistant session configured.**")

        # Fetch up to 200 audio messages from DB channel via userbot
        messages = []
        async for msg in userbot.get_chat_history(channel_username, limit=200):
            if msg.audio or msg.document:
                messages.append(msg)

        if not messages:
            return await mystic.edit_text("➲ **Smash Radio is offline — DB channel is empty.**")

        # Pick a random starting song
        random.shuffle(messages)
        first_msg = messages[0]
        remaining = messages[1:]

        title = (first_msg.audio.title if first_msg.audio and first_msg.audio.title
                 else (first_msg.audio.file_name if first_msg.audio else "Smash Radio Hit"))
        duration = "3:30"
        if first_msg.audio and first_msg.audio.duration:
            m = first_msg.audio.duration // 60
            s = first_msg.audio.duration % 60
            duration = f"{m}:{s:02d}"

        details = {
            "title": title,
            "link": f"https://t.me/{channel_username.replace('@', '')}/{first_msg.id}",
            "vidid": f"db_{first_msg.id}",
            "duration_min": duration,
            "thumb": "https://files.catbox.moe/9orx6x.jpg",
        }

        # stream() sends the "Now Playing" message automatically — don't delete mystic yet
        await stream(
            _,         # language dict — MUST be first arg
            mystic,
            user_id,
            details,
            chat_id,
            user_name,
            message.chat.id,
            video=False,
            streamtype="youtube",
            forceplay=True,
        )

        # Delete the loading message (stream() already sent the "now playing" card)
        try:
            await mystic.delete()
        except:
            pass

        # Background: queue all remaining songs for non-stop playback
        asyncio.create_task(
            fill_radio_queue(chat_id, message.chat.id, user_id, user_name, remaining)
        )

    except Exception as e:
        try:
            await mystic.edit_text(f"➲ **Smash Radio failed:** `{str(e)}`")
        except:
            pass
