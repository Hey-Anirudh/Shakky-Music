# Ani/utils/stream/stream.py
import os
import time
import asyncio
import logging
from typing import Union
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

import config
from shakky import YouTube, app
from shakky.misc import db
from shakky.core.call import ani
from shakky.utils.webapp import notify_webapp
from shakky.utils.formatters import time_to_seconds
from shakky.utils.database import add_active_chat, remove_active_chat

logger = logging.getLogger("Stream")

# Track active pre-fetchers to avoid duplicates
_prefetch_tasks = {}

async def stream(
    _,
    mystic,
    user_id,
    result,
    chat_id,
    user_name,
    original_chat_id,
    video: Union[bool, str] = None,
    streamtype: Union[bool, str] = None,
    spotify: Union[bool, str] = None,
    forceplay: Union[bool, str] = None,
    raw_query: str = None,
):
    """
    Standard Stream Engine.
    Downloads audio, updates db[chat_id], starts PyTgCalls VC stream, notifies WebApp.
    """
    if not result:
        return await mystic.edit_text("❌ Error: No result found.")

    if forceplay:
        # ⚡ Playforce: Clear queue and notify WebApp to stop current playback immediately
        db[chat_id] = []
        await notify_webapp(chat_id, is_playing=False, action="stop")

    if chat_id not in db:
        db[chat_id] = []

    # Prepare metadata
    vidid = result.get("vidid")
    title = str(result.get("title", "Unknown")).title()
    dur = result.get("duration", "0:00")
    
    # Consistent thumbnail logic with WebApp (prefer HQ YouTube thumbnail)
    thumb = result.get("thumbnail_url")
    if vidid and not thumb:
        thumb = f"https://img.youtube.com/vi/{vidid}/hqdefault.jpg"
    if not thumb:
        thumb = config.STREAM_IMG_URL
    
    # Send loading message if mystic exists
    if mystic:
        await mystic.edit_text(f"🔍 **Searching Track**\n╰ `{title}`...")

    # Step 2: Download song (Uses new 2A -> 2B logic in YouTube.py)
    # Step 2: Download song
    file_path = await YouTube.download_song(vidid or title, raw_query=title)
    if not file_path:
        if mystic:
            return await mystic.edit_text("❌ Failed to acquire audio.")
        return

    # Add to queue
    song_info = {
        "file": file_path,
        "title": title,
        "dur": dur,
        "by": user_name,
        "vidid": vidid,
        "thumb": thumb,
        "user_id": user_id,
        "chat_id": chat_id,
        "start_time": 0,
    }
    db[chat_id].append(song_info)

    # If first song, start playback
    if len(db[chat_id]) == 1:
        await start_playback(chat_id)
        
    # UI Feedback
    is_first = len(db[chat_id]) == 1
    webapp_url = f"https://t.me/{app.me.username if app.me else config.BOT_USERNAME.replace('@', '')}/join?startapp={abs(chat_id)}"
    
    # Buttons updated as per user request (Step 2)
    buttons = [
        [
            InlineKeyboardButton(text="🎧 Join Room", url=webapp_url)
        ],
        [
            InlineKeyboardButton(text="✖ Close", callback_data="close")
        ]
    ]

    if is_first:
        # Now Playing Message
        text = (
            f"✦ **NOW STREAMING**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"✧ **Track:** `{title}`\n"
            f"✧ **Time:** `{dur}`\n"
            f"✧ **Requested By:** {user_name}"
        )
    else:
        # Queued Message
        pos = len(db[chat_id]) - 1
        text = (
            f"✦ **ADDED TO QUEUE** ❲#{pos}❳\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"✧ **Track:** `{title}`\n"
            f"✧ **Time:** `{dur}`\n"
            f"✧ **Requested By:** {user_name}"
        )

    # Post final message with thumbnail (with robust fallbacks)
    sent_msg = None
    try:
        # Try primary thumbnail
        sent_msg = await app.send_photo(
            chat_id,
            photo=thumb,
            caption=text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        logger.warning(f"Primary thumbnail failed for {title}: {e}")
        try:
            # Try default config image
            sent_msg = await app.send_photo(
                chat_id,
                photo=config.STREAM_IMG_URL,
                caption=text,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except Exception as e2:
            logger.error(f"All photo attempts failed for {title}: {e2}")
            # Final fallback: Text only
            sent_msg = await app.send_message(
                chat_id,
                text=text,
                reply_markup=InlineKeyboardMarkup(buttons)
            )

    # Only delete mystic AFTER we have successfully sent the final message
    if mystic:
        try:
            await mystic.delete()
        except:
            pass


async def start_playback(chat_id):
    """Start streaming the current song in VC and notify WebApp (Step 3)"""
    if chat_id not in db or not db[chat_id]:
        return

    current = db[chat_id][0]
    vidid = current.get("vidid")
    title = current.get("title")
    
    # 🩹 IF file path is missing (happens with pre-fetched queue tracks), resolve it now
    if not current.get("file") or not os.path.exists(current.get("file")):
        logger.info(f"Resolving file for {chat_id}: {title}")
        file_path = await YouTube.download_song(vidid or title, raw_query=title)
        if file_path:
            current["file"] = file_path
        else:
            logger.error(f"Could not resolve file for {title}, skipping...")
            await skip_and_play(chat_id)
            return

    # Start logic
    file_path = current["file"]
    await ani.join_group_call(chat_id, file_path)
    
    # Track logic
    current["start_time"] = time.time()
    await add_active_chat(chat_id)
    
    # Notify WebApp
    await notify_webapp(chat_id, current_song=current, queue=db[chat_id][1:], action="play")
    
    # Track for recommendations
    from shakky.misc import last_played
    last_played[chat_id] = current["title"]
    
    # Start Pre-fetch and End-check task
    if chat_id in _prefetch_tasks:
        _prefetch_tasks[chat_id].cancel()
    _prefetch_tasks[chat_id] = asyncio.create_task(playback_monitor(chat_id))


async def playback_monitor(chat_id):
    """Monitors playback for pre-fetching and auto-advancing queue (Step 5)"""
    try:
        prefetched = False
        while chat_id in db and db[chat_id]:
            current = db[chat_id][0]
            if current.get("paused"):
                await asyncio.sleep(2)
                continue
                
            try:
                duration_sec = time_to_seconds(current["dur"])
            except:
                duration_sec = 0
            
            # If duration is Unknown or too short, don't auto-skip based on time
            if duration_sec <= 0:
                await asyncio.sleep(10)
                continue

            elapsed = time.time() - current["start_time"]
            
            # 1. Pre-fetch check (10s before end)
            if not prefetched and duration_sec > 15 and (duration_sec - elapsed) <= 15:
                if len(db[chat_id]) > 1:
                    next_song = db[chat_id][1]
                    # Only download if we don't have the file yet
                    if not next_song.get("file") or not os.path.exists(next_song.get("file")):
                        logger.info(f"Pre-fetching next song for {chat_id}: {next_song['title']}")
                        # Trigger download in background to not block monitor
                        asyncio.create_task(YouTube.download_song(next_song['vidid'] or next_song['title'], raw_query=next_song['title']))
                prefetched = True
            
            # 2. Auto-skip check (Duration reached)
            if elapsed >= duration_sec + 2: # 2s buffer for network lag
                logger.info(f"Song ended in {chat_id}, auto-skipping...")
                await skip_and_play(chat_id)
                return # Exit this monitor as skip_and_play starts a NEW one
            
            await asyncio.sleep(2)
            
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Error in playback_monitor for {chat_id}: {e}")


async def skip_and_play(chat_id):
    """Logic to auto-advance queue (Step 5)"""
    if chat_id not in db or not db[chat_id]:
        await ani.stop_stream(chat_id)
        return

    # Clean up old file
    old_song = db[chat_id].pop(0)
    if old_song.get("file") and os.path.exists(old_song["file"]):
        try:
            os.remove(old_song["file"])
        except:
            pass

    if not db[chat_id]:
        # [NEW] Check for AI Mode first
        from shakky.misc import last_played, ai_mode
        if ai_mode.get(chat_id):
            # 🚀 AI Auto-Pilot: Automatically trigger next recommendation!
            from .recommend_logic import start_ai_recommendation
            asyncio.create_task(start_ai_recommendation(chat_id))
            return

        # Queue empty, stop
        await remove_active_chat(chat_id)
        await ani.stop_stream(chat_id)
        await notify_webapp(chat_id, is_playing=False, action="stop")

        # [NEW] Send Stream Ended message with AI Control Button
        last_song = last_played.get(chat_id, "the last track")
        buttons = [
            [
                InlineKeyboardButton(text="🪄 Give Control to AI", callback_data="play_recommendation")
            ],
            [
                InlineKeyboardButton(text="✖ Close", callback_data="close")
            ]
        ]
        await app.send_message(
            chat_id,
            text=(
                f"✦ **STREAM ENDED**\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"✧ **Queue is now empty.**\n"
                f"✧ **Last Song:** `{last_song}`\n\n"
                f"**Tap below to let AI take control and play similar songs continuously!**"
            ),
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:
        # Start next
        await start_playback(chat_id)
