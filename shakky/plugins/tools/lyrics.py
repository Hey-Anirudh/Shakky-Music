from pyrogram import filters
from pyrogram.types import Message
import asyncio
import time
from shakky import app
from shakky.misc import db
from shakky.utils.lyrics import fetch_lrc
from config import BANNED_USERS

@app.on_message(filters.command(["lyrics", "lrc"]) & filters.group & ~BANNED_USERS)
async def lyrics_command(client, message: Message):
    chat_id = message.chat.id
    if not db.get(chat_id):
        return await message.reply_text("➲ **No music is currently playing.**")
    
    current_song = db[chat_id][0]
    title = current_song.get("title")
    start_time = current_song.get("start_time")
    
    if not start_time:
        return await message.reply_text("➲ **Could not determine song progress. Restart the song.**")
    
    status_msg = await message.reply_text(f"➲ **Searching lyrics for:** `{title}`...")
    
    lyrics = await fetch_lrc(title)
    if not lyrics:
        return await status_msg.edit(f"➲ **No synchronized lyrics found for:** `{title}`")
    
    await status_msg.edit("➲ **Synced Lyrics Started!**")
    
    # Sync loop
    try:
        last_index = -1
        while db.get(chat_id) and db[chat_id][0].get("title") == title:
            current_pos = time.time() - db[chat_id][0].get("start_time", time.time())
            
            # Find the current line
            current_index = -1
            for i, (lrc_time, text) in enumerate(lyrics):
                if lrc_time <= current_pos:
                    current_index = i
                else:
                    break
            
            if current_index != last_index and current_index != -1:
                # Build the lyrics display (current line highlighted)
                display = []
                start = max(0, current_index - 2)
                end = min(len(lyrics), current_index + 3)
                
                for i in range(start, end):
                    lrc_time, text = lyrics[i]
                    if i == current_index:
                        display.append(f"▶️ **{text}**")
                    else:
                        display.append(f"   {text}")
                
                lyrics_text = "\n".join(display)
                text_to_send = (
                    f"✨ **𝓢𝔂𝓷𝓬𝓮𝓭 𝓛𝔂𝓻𝓲𝓬𝓼** ✨\n"
                    f"🎧 `{title[:30]}`\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"{lyrics_text}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"➲ *Powered by Shakky Music*"
                )
                try:
                    await status_msg.edit(text_to_send)
                except:
                    pass
                last_index = current_index
            
            await asyncio.sleep(1) # Refresh every second
            
    except Exception as e:
        print(f"Lyrics Error: {e}")
