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
        f"✨ **MUSIC WRAPPED**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>User:</b> {message.from_user.mention}\n\n"
        f"<blockquote>"
        f"✧ **Tracks Explored:** <code>{total_tracks}</code>\n"
        f"✧ **Time Grooving:** <code>{total_time}</code>\n"
        f"</blockquote>\n"
        f"🔥 **YOUR TOP 5 TRACKS:**\n"
    )
    
    top_data = ""
    for i, (vidid, data) in enumerate(top_songs, 1):
        title = data.get('title', 'Unknown').title()
        count = data.get('count', 0)
        top_data += f"{i}. <code>{title[:28]}</code> ({count} plays)\n"
        
    msg += f"<blockquote>{top_data}</blockquote>\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n"
    msg += "➲ *Keep smashing tunes to rise through the ranks!*"
    
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
        f"🌐 **GLOBAL STATISTICS**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<blockquote>"
        f"✧ **Total Streamed:** <code>{total_calls}</code>\n"
        f"✧ **Listening Time:** <code>{total_time}</code>\n"
        f"</blockquote>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"➲ *Powered by Smash Music Engine*"
    )
    
    await message.reply_text(msg)

