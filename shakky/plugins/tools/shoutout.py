import asyncio
import os
import time
from pyrogram import filters
from pyrogram.types import Message
from shakky import app
from shakky.core.call import Nand
from shakky.misc import SUDOERS
from shakky.utils.database import is_active_chat, group_assistant
import config
from config import BANNED_USERS

# ─── TTS Engine ───────────────────────────────────────────
try:
    import edge_tts
except ImportError:
    edge_tts = None

# DJ Voices (Premium Edge-TTS Voices)
DJ_VOICES = [
    "en-US-GuyNeural",
    "en-US-AriaNeural",
    "en-GB-RyanNeural",
    "en-AU-WilliamNeural"
]

async def generate_shoutout(text: str, file_path: str):
    """Generate high-quality TTS using edge-tts."""
    if not edge_tts:
        return False
    
    voice = random.choice(DJ_VOICES)
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(file_path)
    return True

import random

@app.on_message(
    filters.command(["shoutout", "dj", "announce"])
    & filters.group
    & ~BANNED_USERS
)
async def shoutout_command(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "<blockquote>🔊 <b>Instant DJ Shoutout</b></blockquote>\n\n"
            "➲ <b>Usage:</b> <code>/shoutout [your message]</code>\n"
            "➲ <b>Example:</b> <code>/shoutout Happy Birthday Anirudh!</code>",
        )

    chat_id = message.chat.id
    if not await is_active_chat(chat_id):
        return await message.reply_text("➲ <b>Bot is not playing anything in VC.</b>")

    shoutout_text = message.text.split(None, 1)[1]
    if len(shoutout_text) > 200:
        return await message.reply_text("➲ <b>Shoutout message is too long (max 200 chars).</b>")

    mystic = await message.reply_text("🎙️ <b>Preparing your DJ Shoutout...</b>")
    
    # Generate TTS
    file_name = f"shoutout_{chat_id}_{int(time.time())}.mp3"
    file_path = os.path.join("downloads", file_name)
    
    success = await generate_shoutout(shoutout_text, file_path)
    if not success:
        return await mystic.edit_text("❌ <b>Failed to generate shoutout (edge-tts not installed).</b>")

    # Pick a SECOND assistant to avoid interrupting the music
    main_ass = await group_assistant(Nand, chat_id)
    
    # Logic to find a free assistant
    secondary_ass = None
    all_ass = [Nand.one, Nand.two, Nand.three, Nand.four, Nand.five]
    for ass in all_ass:
        if ass and ass != main_ass:
            secondary_ass = ass
            break
            
    if not secondary_ass:
        # Fallback: Use the main assistant if only one is configured (this will interrupt music)
        secondary_ass = main_ass
        await mystic.edit_text("🎙️ <b>DJ is stepping into the booth (Music will pause briefly)...</b>")
    else:
        await mystic.edit_text("🎙️ <b>DJ Shoutout coming up live!</b>")

    try:
        # Build a temporary stream for the shoutout
        # We use a simple path for the shoutout
        from shakky.core.call import IS_LEGACY
        
        # Join and Play via Secondary Assistant
        # Note: join_group_call or start_audio depends on legacy state
        if IS_LEGACY:
            # For Legacy, we just start the audio. 
            # We don't want to 'join' again if they are already in, 
            # but usually assistants are in separate accounts.
            try:
                # If it's a different account, it needs to join
                if secondary_ass != main_ass:
                    try: await secondary_ass.join(chat_id)
                    except: pass
                await secondary_ass.start_audio(file_path)
            except Exception as e:
                return await mystic.edit_text(f"❌ <b>DJ Booth Error:</b> `{e}`")
        else:
            # Modern Pytgcalls
            from pytgcalls.types.input_stream import AudioPiped
            from pytgcalls.types.input_stream.quality import HighQualityAudio
            
            stream = AudioPiped(file_path, HighQualityAudio())
            try:
                # If it's a different account, it needs to join
                if secondary_ass != main_ass:
                    await secondary_ass.join_group_call(chat_id, stream)
                else:
                    # If same assistant, we have to change_stream (interrupts music)
                    await secondary_ass.change_stream(chat_id, stream)
            except Exception as e:
                 return await mystic.edit_text(f"❌ <b>DJ Booth Error:</b> `{e}`")

        # Wait for the shoutout to finish (assume ~10 seconds max or calculate)
        # For simplicity, we'll wait 8 seconds then leave (if secondary) or resume (if main)
        await asyncio.sleep(8)
        
        if secondary_ass != main_ass:
            try:
                if IS_LEGACY: await secondary_ass.leave(chat_id)
                else: await secondary_ass.leave_group_call(chat_id)
            except: pass
        else:
            # Resume music if it was the same assistant
            playing = Nand.misc.db.get(chat_id)
            if playing:
                await Nand._sync_stream(chat_id, playing)

        await mystic.edit_text("✅ <b>Shoutout delivered successfully!</b>")
        
        # Cleanup
        if os.path.exists(file_path):
            os.remove(file_path)
            
    except Exception as e:
        await mystic.edit_text(f"❌ <b>Error delivering shoutout:</b> `{e}`")
