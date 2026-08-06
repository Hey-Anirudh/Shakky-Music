import os

from pyrogram import filters

from shakky import app
from shakky.utils.database import get_served_chats, get_served_users
from shakky.utils.sys import bot_sys_stats
from shakky.utils.mongo import get_top_contributors
import config

@app.on_message(filters.command(["stats", "dbstats", "database"]) & filters.user(config.OWNER_ID))
async def stats_handler(_, message):
    mystic = await message.reply_text("➲ **Fetching Bot Database Stats...**")

    try:
        users = await get_served_users()
        chats = await get_served_chats()

        song_count = 0
        for folder in ("downloads", "playback"):
            if os.path.isdir(folder):
                for item in os.listdir(folder):
                    if os.path.isfile(os.path.join(folder, item)) and not item.startswith("."):
                        song_count += 1

        cache_count = 0
        for cache_file in ("song_cache.json", "keyword_cache.json", "url_cache.json"):
            if os.path.isfile(cache_file):
                try:
                    import json
                    with open(cache_file, "r", encoding="utf-8") as f:
                        cache_count += len(json.load(f))
                except Exception:
                    pass

        top_list = await get_top_contributors(5)
        contributors_data = ""
        for i, user_stats in enumerate(top_list, 1):
            user_id = user_stats["user_id"]
            count = user_stats["count"]
            try:
                user = await app.get_users(user_id)
                name = user.first_name if user.first_name else "Anonymous"
            except Exception:
                name = f"User {user_id}"
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "✧"
            contributors_data += f"{medal} {name} — <code>{count}</code> songs\n"

        up, cpu, ram, disk = await bot_sys_stats()

        caption = (
            "➲ **BOT DATABASE STATS**\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 **Served Users:** <code>{len(users)}</code>\n"
            f"💬 **Served Chats:** <code>{len(chats)}</code>\n"
            f"🎵 **Cached Songs:** <code>{song_count}</code>\n"
            f"🗃️ **Cache Entries:** <code>{cache_count}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🖥️ **Uptime:** <code>{up}</code>\n"
            f"⚙️ **CPU:** <code>{cpu}</code> | **RAM:** <code>{ram}</code> | **Disk:** <code>{disk}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
        )
        if contributors_data:
            caption += f"<blockquote>{contributors_data}</blockquote>\n"
            caption += "━━━━━━━━━━━━━━━━━━━━\n"
        caption += "✧ **Status:** <code>Stable & Optimized</code>"
        await mystic.edit_text(caption)

    except Exception as e:
        await mystic.edit_text(f"➲ **Failed to load stats:** `{str(e)}`")