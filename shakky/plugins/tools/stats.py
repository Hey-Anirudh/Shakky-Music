from pyrogram import filters
from shakky import app
from shakky.utils.mongo import get_top_contributors
import config

@app.on_message(filters.command(["stats", "top", "contributors"]) & filters.user(config.OWNER_ID))
async def stats_handler(_, message):
    mystic = await message.reply_text("➲ **Fetching Smash Music Stats...**")
    
    try:
        # Load the Top Contributors (Old Stats Data)
        top_list = await get_top_contributors(10)
        
        if not top_list:
            return await mystic.edit_text("➲ **No contributors found yet! Start adding songs with /addsong.**")
        
        caption = "➲ **BOT STATISTICS**\n━━━━━━━━━━━━━━━━━━━━\n"
        
        stats_data = ""
        for i, user_stats in enumerate(top_list, 1):
            user_id = user_stats["user_id"]
            count = user_stats["count"]
            
            try:
                user = await app.get_users(user_id)
                name = user.first_name if user.first_name else "Anonymous"
            except:
                name = f"User {user_id}"
            
            # Medal for top 3
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "✧"
            stats_data += f"{medal} **{name}** — <code>{count}</code> songs\n"
            
        caption += f"<blockquote>{stats_data}</blockquote>\n"
        caption += "━━━━━━━━━━━━━━━━━━━━\n"
        caption += "✧ **Status:** <code>Stable & Optimized</code>"
        await mystic.edit_text(caption)

        
    except Exception as e:
        await mystic.edit_text(f"➲ **Failed to load stats:** `{str(e)}`")
