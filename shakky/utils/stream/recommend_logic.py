import asyncio
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from shakky import app, YouTube, LOGGER
from shakky.misc import last_played, db
from shakky.utils.groq import get_song_recommendation
from .stream import stream as start_stream

async def start_ai_recommendation(chat_id, user_id=None, user_name="AI"):
    """
    Utility to get a recommendation and start playing it.
    Can be called from both the callback and automatically.
    """
    last_song = last_played.get(chat_id)
    if not last_song:
        return
    
    # 🧠 Get Recommendation
    rec_title = await get_song_recommendation(last_song)
    if not rec_title:
        LOGGER("AI").error(f"Groq failed for recommendation in {chat_id}")
        return
    
    # Notify chat that AI is choosing
    mystic = await app.send_message(
        chat_id, 
        text=f"✦ **AI AUTO-PILOT**\n━━━━━━━━━━━━━━━━━━\n✧ **Context:** `{last_song}`\n✧ **Choosing:** `{rec_title}`"
    )
    
    # 🔍 Search & Stream
    try:
        results = await YouTube.search(rec_title)
        if not results:
             return await mystic.edit_text(f"❌ AI suggested '{rec_title}' but it was not found.")
        
        # We need a user_id for the stream engine, use bot's or provided
        final_user_id = user_id or (app.me.id if app.me else 0)

        await start_stream(
            None,
            mystic,
            final_user_id,
            results,
            chat_id,
            user_name,
            chat_id,
            streamtype="youtube"
        )
            
    except Exception as e:
        LOGGER("AI").error(f"Error in auto-recommendation: {e}")
        await app.send_message(chat_id, text=f"❌ AI Error: {e}")
