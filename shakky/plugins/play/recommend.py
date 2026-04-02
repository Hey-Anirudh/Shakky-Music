from pyrogram import filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from shakky import app, YouTube, LOGGER
from shakky.misc import last_played, ai_mode
from config import BANNED_USERS

@app.on_callback_query(filters.regex("play_recommendation") & ~BANNED_USERS)
async def play_rec_callback(client, callback_query: CallbackQuery):
    chat_id = callback_query.message.chat.id

    if not last_played.get(chat_id):
         return await callback_query.answer("No context found for recommendations.", show_alert=True)
         
    # 🧬 Turn on AI Mode (Continuous Playback)
    ai_mode[chat_id] = True
    
    await callback_query.answer("🚀 AI Pilot: Active!", show_alert=False)
    
    # Start the engine
    from shakky.utils.stream.recommend_logic import start_ai_recommendation
    await start_ai_recommendation(
        chat_id,
        user_id=callback_query.from_user.id,
        user_name=callback_query.from_user.first_name
    )
    
    # Delete the prompt message
    try:
        await callback_query.message.delete()
    except:
        pass
