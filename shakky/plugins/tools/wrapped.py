from pyrogram import filters
from pyrogram.types import Message
from shakky import app
from shakky.utils.database import get_user_stats, get_global_stats
from shakky.utils.formatters import seconds_to_min
from config import BANNED_USERS

@app.on_message(filters.command(["wrap", "mywrap"]) & ~BANNED_USERS)
async def wrapped_command(client, message: Message):
    """
    Personalized playback statistics for the user.
    """
    user_id = message.from_user.id
    stats = await get_user_stats(user_id)
    
    if not stats or not stats.get("total_tracks"):
        return await message.reply_text("➲ **No music history found for you yet! Start listening to generate your Wrapped.**")
    
    total_tracks = stats.get("total_tracks", 0)
    total_secs = stats.get("total_seconds", 0)
    total_time = seconds_to_min(total_secs)
    
    history = stats.get("history", {})
    # Sort history by play count
    top_songs = sorted(history.items(), key=lambda x: x[1].get('count', 0), reverse=True)[:5]
    
    msg = (
        f"🏆 **{message.from_user.first_name}'s Music Wrapped** 🏆\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✧ **Tracks Explored:** `{total_tracks}`\n"
        f"✧ **Time Grooving:** `{total_time}`\n\n"
        f"🔥 **Your All-Time Top 5:**\n"
    )
    
    for i, (vidid, data) in enumerate(top_songs, 1):
        title = data.get('title', 'Unknown').title()
        count = data.get('count', 0)
        msg += f"{i}. `{title[:28]}` ({count} plays)\n"
        
    msg += f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "➲ *Keep smashing regular tunes to rise through the ranks!*"
    
    await message.reply_text(msg)

@app.on_message(filters.command(["globalstats", "serverstats"]) & ~BANNED_USERS)
async def global_stats_command(client, message: Message):
    """
    Global platform statistics.
    """
    stats = await get_global_stats()
    
    if not stats:
        return await message.reply_text("➲ **Platform statistics are currently being initialized.**")
        
    total_calls = stats.get("total_calls", 0)
    total_secs = stats.get("total_seconds", 0)
    total_time = seconds_to_min(total_secs)
    
    msg = (
        f"🌐 **Smash Music Global Stats** 🌐\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✧ **Total Songs Streamed:** `{total_calls}`\n"
        f"✧ **Global Listening Time:** `{total_time}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"➲ *Powered by Smash Music Engine*"
    )
    
    await message.reply_text(msg)
