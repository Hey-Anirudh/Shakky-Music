import asyncio
import random
from pyrogram import filters
from pyrogram.types import Message
from shakky import app
from shakky.core.call import Nand
from shakky.misc import db
from shakky.utils.database import is_active_chat
from shakky.utils.groq import get_synced_lyrics_from_groq
from config import BANNED_USERS

# Simple Game State
GAME_CHALLENGES = {} # chat_id -> {answer, user_id, message_id}

@app.on_message(filters.command(["game", "challenge", "lyrics"]) & filters.group & ~BANNED_USERS)
async def lyrics_challenge_command(client, message: Message):
    """
    Starts a 'Finish the Lyrics' challenge based on the current song.
    """
    chat_id = message.chat.id
    if not await is_active_chat(chat_id):
        return await message.reply_text("➲ **Play a song first to start the game!**")

    playing = db.get(chat_id)
    if not playing: return
    
    title = playing[0]["title"]
    mystic = await message.reply_text(f"🎲 <b>Preparing the 'Finish the Lyrics' challenge for:</b>\n<code>{title}</code>...")
    
    # 1. Fetch Lyrics
    lrc = await get_synced_lyrics_from_groq(title)
    if not lrc or "[" not in lrc:
        return await mystic.edit_text("❌ **Could not find lyrics for this song to start a game.**")
        
    lines = [l.split("]")[-1].strip() for l in lrc.split("\n") if "]" in l and len(l.split("]")[-1].strip()) > 10]
    
    if len(lines) < 10:
        return await mystic.edit_text("❌ **Song lyrics are too short for a challenge.**")

    # 2. Pick a random line (avoiding start and end)
    idx = random.randint(5, len(lines) - 5)
    challenge_line = lines[idx]
    prev_lines = "\n".join(lines[idx-2:idx])
    
    # 3. Store Challenge
    GAME_CHALLENGES[chat_id] = {
        "answer": challenge_line.lower().strip(),
        "title": title,
        "mystic_id": message.id
    }
    
    # 4. Announce
    game_msg = (
        f"<blockquote><b>🎲 FINISH THE LYRICS!</b></blockquote>\n\n"
        f"➲ <b>Song:</b> <code>{title}</code>\n"
        f"➲ <b>Previous Lines:</b>\n"
        f"<i>\"{prev_lines}\"</i>\n\n"
        f"🔥 <b>WHAT COMES NEXT?</b>\n"
        f"➲ <i>First person to type the next line exactly wins!</i>"
    )
    
    await mystic.edit_text(game_msg)
    
    # Optional: Pause music to make it more dramatic
    await Nand.pause_stream(chat_id)
    
    # Wait 45 seconds then end game if no winner
    await asyncio.sleep(45)
    if chat_id in GAME_CHALLENGES:
        challenge = GAME_CHALLENGES.pop(chat_id)
        await client.send_message(
            chat_id, 
            f"⏰ <b>Time's Up!</b>\n\n➲ <b>The answer was:</b>\n<code>{challenge['answer'].capitalize()}</code>\n\n➲ <i>Resuming music...</i>"
        )
        await Nand.resume_stream(chat_id)

@app.on_message(filters.group & ~filters.command(["game", "challenge", "lyrics"]) & ~BANNED_USERS)
async def game_answer_handler(client, message: Message):
    chat_id = message.chat.id
    if chat_id not in GAME_CHALLENGES: return
    
    challenge = GAME_CHALLENGES[chat_id]
    user_answer = message.text.lower().strip()
    
    # Check if answer is close enough (simple match)
    if user_answer == challenge["answer"]:
        GAME_CHALLENGES.pop(chat_id)
        await message.reply_text(
            f"🎊 <b>BINGO!</b> {message.from_user.mention} <b>finished the lyrics!</b>\n\n"
            f"➲ <b>Answer:</b> <code>{challenge['answer'].capitalize()}</code>\n"
            f"➲ <b>Reward:</b> 💎 <b>100 Shakky Gems!</b>\n\n"
            f"➲ <i>Resuming music...</i>"
        )
        await Nand.resume_stream(chat_id)
