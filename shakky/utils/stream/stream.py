import os
import asyncio
from random import randint
import logging
import traceback
from typing import Union
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import config
from shakky import app
from shakky.platforms import YouTube, Telegram
from shakky.core.call import ani
from shakky.misc import db
from shakky.utils.database import add_active_chat, is_active_chat, remove_active_chat, update_stats
from shakky.utils.formatters import time_to_seconds
from shakky.utils.exceptions import AssistantErr
from shakky.utils.inline import aq_markup, close_markup, stream_markup
from shakky.utils.thumbnails import get_thumb
from shakky.utils.webapp import notify_webapp
import time

logger = logging.getLogger(__name__)

# Global sequencer to prevent concurrent play requests from overlapping or skipping within a single chat
_play_sequencer = {}

def get_chat_lock(chat_id):
    if chat_id not in _play_sequencer:
        _play_sequencer[chat_id] = asyncio.Lock()
    return _play_sequencer[chat_id]

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
    if not result:
        return await mystic.edit_text("➲ **No results found.**")

    async with get_chat_lock(chat_id):
        if forceplay:
            await ani.stop_stream_force(chat_id)
            db[chat_id] = []
            asyncio.create_task(_notify_safe(chat_id, is_playing=False, action="stop"))

        if streamtype == "youtube":
            vidid = result.get("vidid")
            title = str(result.get("title", "Unknown")).title()
            duration_min = result.get("duration", "0:00")
            thumbnail = result.get("thumbnail_url", result.get("thumb", ""))
            logger.info(f"[stream] Processing YouTube: {title} ({duration_min}) ID={vidid}")
            status = True if video else None
            
            try:
                # 🩹 NOTE: Download is now inside the lock to preserve order
                file_path, direct = await asyncio.wait_for(
                    YouTube.download(
                        vidid, mystic, videoid=True, video=status, raw_query=raw_query or title
                    ),
                    timeout=45
                )
            except asyncio.TimeoutError:
                logger.error(f"Download timed out for {vidid}")
                raise AssistantErr("➲ **Download timed out. Try again.**")
            except Exception as e:
                logger.error(f"Download failed: {e}")
                raise AssistantErr("➲ **Failed to download track.**")

            if await is_active_chat(chat_id):
                await put_queue(
                    chat_id,
                    original_chat_id,
                    file_path if direct else f"vid_{vidid}",
                    title,
                    duration_min,
                    user_name,
                    vidid,
                    user_id,
                    "video" if video else "audio",
                )
                position = len(db.get(chat_id)) - 1
                try:
                    await mystic.delete()
                except:
                    pass

                button = aq_markup(_, chat_id)
                await app.send_message(
                    original_chat_id,
                    text=f"➲ **Added to Queue at #{position}**\n\n**Track:** {title[:28]}\n**Duration:** {duration_min}\n**By:** {user_name}",
                    reply_markup=InlineKeyboardMarkup(button),
                )
                asyncio.create_task(_predownload_queued(chat_id, position))
            else:
                await put_queue(
                    chat_id,
                    original_chat_id,
                    file_path if direct else f"vid_{vidid}",
                    title,
                    duration_min,
                    user_name,
                    vidid,
                    user_id,
                    "video" if video else "audio",
                    forceplay=forceplay,
                )
                
                # --- Stats Update for Wrapped ---
                try:
                    dur_sc = 0
                    try: dur_sc = time_to_seconds(duration_min)
                    except: pass
                    asyncio.create_task(update_stats(user_id, chat_id, vidid, title, dur_sc))
                except:
                    pass
                await ani.join_call(
                    chat_id,
                    original_chat_id,
                    file_path,
                    video=status,
                    image=thumbnail,
                )
                current = db[chat_id][0]
                current["start_time"] = time.time()
                asyncio.create_task(
                    _send_initial_now_playing(
                        chat_id, vidid, title, duration_min, user_name, user_id,
                        original_chat_id, _, mystic
                    )
                )
        
        elif streamtype == "spotify":
            if isinstance(result, list):
                # result is a list of track names (e.g. ['SongArtist', ...])
                await mystic.edit_text(f"➲ **Adding {len(result)} tracks from Spotify Playlist...**")
                
                for i, track_name in enumerate(result):
                    # We queue them as vid_sp_SEARCHTERM to resolve on-play
                    await put_queue(
                        chat_id,
                        original_chat_id,
                        f"vid_sp_{track_name}", 
                        track_name,
                        "0:00",
                        user_name,
                        None,
                        user_id,
                        "audio",
                    )
                    
                    # Optimization: Resolve first song NOW if idle
                    if i == 0 and not await is_active_chat(chat_id):
                         try:
                             search_res = await YouTube.search(track_name)
                             if search_res:
                                 db[chat_id][0].update({
                                     "file": f"vid_{search_res['vidid']}",
                                     "vidid": search_res['vidid'],
                                     "dur": search_res['duration']
                                 })
                         except: pass

                if not await is_active_chat(chat_id):
                    # Start playback if idle
                    first = db[chat_id][0]
                    await ani.join_call(chat_id, original_chat_id, first["file"], video=status)
                    first["start_time"] = time.time()
                    asyncio.create_task(_send_initial_now_playing(chat_id, first.get("vidid"), first["title"], first["dur"], user_name, user_id, original_chat_id, _))
                else:
                    await mystic.edit_text(f"➲ **Queued {len(result)} Spotify tracks at #{len(db[chat_id]) - len(result)}!**")
                return

            else:
                # Single track mode (result is a dict)
                # We leverage the youtube block by rewriting result/streamtype
                vidid = result.get("vidid")
                title = str(result.get("title", "Unknown")).title()
                duration_min = result.get("duration_min", "0:00")
                thumbnail = result.get("thumb", "")
                status = True if video else None
                
                file_path, direct = await YouTube.download(vidid, mystic, video=status, raw_query=title)
                
                if await is_active_chat(chat_id):
                    await put_queue(chat_id, original_chat_id, file_path if direct else f"vid_{vidid}", title, duration_min, user_name, vidid, user_id, "audio")
                    position = len(db.get(chat_id)) - 1
                    try:
                        await mystic.delete()
                    except:
                        pass
                    button = aq_markup(_, chat_id)
                    await app.send_message(
                        original_chat_id, 
                        text=f"➲ **Added to Queue at #{position}**\n\n**Track:** {title[:28]}\n**By:** {user_name}",
                        reply_markup=InlineKeyboardMarkup(button)
                    )
                else:
                    await put_queue(chat_id, original_chat_id, file_path if direct else f"vid_{vidid}", title, duration_min, user_name, vidid, user_id, "audio")
                    await ani.join_call(chat_id, original_chat_id, file_path, video=status, image=thumbnail)
                    db[chat_id][0]["start_time"] = time.time()
                    asyncio.create_task(_send_initial_now_playing(chat_id, vidid, title, duration_min, user_name, user_id, original_chat_id, _, mystic))
                return

        elif streamtype == "telegram":
            audio = result.audio or result.voice
            video = result.video
            status = True if video else None
            
            file_name = await Telegram.get_filepath(audio=audio, video=video)
            title = await Telegram.get_filename(audio or video, audio=True if audio else False)
            duration_min = await Telegram.get_duration(audio or video, file_name)
            thumbnail = config.STREAM_IMG_URL

            if not os.path.exists(file_name):
                await mystic.edit_text(f"➲ **Downloading Telegram File...**\n📂 **Track:** {title[:25]}")
                downloaded = await Telegram.download(_, result, mystic, file_name)
                if not downloaded:
                    return await mystic.edit_text("❌ **Failed to download the Telegram file.**")

            if await is_active_chat(chat_id):
                await put_queue(chat_id, original_chat_id, file_name, title, duration_min, user_name, None, user_id, "video" if video else "audio")
                position = len(db.get(chat_id)) - 1
                try:
                    await mystic.delete()
                except:
                    pass
                button = aq_markup(_, chat_id)
                await app.send_message(
                    original_chat_id, 
                    text=f"➲ **Added Telegram File to Queue at #{position}**\n\n**Track:** {title[:28]}\n**By:** {user_name}",
                    reply_markup=InlineKeyboardMarkup(button)
                )
            else:
                await put_queue(chat_id, original_chat_id, file_name, title, duration_min, user_name, None, user_id, "video" if video else "audio")
                await ani.join_call(chat_id, original_chat_id, file_name, video=status, image=thumbnail)
                db[chat_id][0]["start_time"] = time.time()
                asyncio.create_task(_send_initial_now_playing(chat_id, None, title, duration_min, user_name, user_id, original_chat_id, _, mystic))
            return
        
        # NOTE: If adding more streamtypes, they should also stay inside this 'async with lock' block

async def _notify_safe(chat_id, **kwargs):
    """Fire-and-forget webapp notification."""
    try:
        await notify_webapp(chat_id, **kwargs)
    except Exception as e:
        logger.warning(f"WebApp notify failed: {e}")

async def _send_initial_now_playing(chat_id, vidid, title, duration_min, user_name, user_id, original_chat_id, _, mystic=None):
    """Generate thumbnail and send Now Playing for initial play (background)."""
    try:
        # Delete the original mystic (Searching...) message first if it exists
        if mystic:
            try:
                await mystic.delete()
            except:
                pass

        current = db[chat_id][0]
        
        # Generate custom thumbnail
        try:
            thumb_path = await get_thumb(vidid, title, duration_min, user_name, chat_id, user_id=user_id)
            current["thumbnail_url"] = f"/thumbs/{os.path.basename(thumb_path)}"
        except Exception as e:
            logger.error(f"Thumbnail generation error: {e}")
            thumb_path = config.STREAM_IMG_URL
            
        # Notify webapp in background
        asyncio.create_task(_notify_safe(chat_id, current_song=current, queue=db[chat_id][1:], action="play"))
        
        button = stream_markup(_, chat_id)
        msg_text = (
            f"▷ **Now Playing**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"✧ **Track:** `{title[:28]}`\n"
            f"✧ **Duration:** `{duration_min}`\n"
            f"✧ **By:** {user_name}"
        )
        try:
            run = await app.send_photo(
                original_chat_id,
                photo=thumb_path,
                caption=msg_text,
                reply_markup=InlineKeyboardMarkup(button),
            )
        except Exception as e:
            logger.error(f"Thumbnail send failed, sending message instead: {e}")
            run = await app.send_message(
                original_chat_id,
                text=msg_text,
                reply_markup=InlineKeyboardMarkup(button),
            )
        db[chat_id][0]["mystic"] = run
        db[chat_id][0]["markup"] = "stream"
    except Exception as e:
        logger.error(f"Failed to send initial Now Playing: {e}")

async def _predownload_queued(chat_id, position):
    """Pre-download a queued track in background so it's ready when needed."""
    try:
        check = db.get(chat_id)
        if not check or position >= len(check):
            return
        track = check[position]
        track_file = track.get("file", "")
        track_vid = track.get("vidid", "")
        if "vid_" in track_file and not os.path.exists(track_file) and track_vid:
            logger.info(f"Pre-downloading queued track #{position}: {track.get('title', track_vid)}")
            file_path, _ = await asyncio.wait_for(
                YouTube.download(track_vid, raw_query=track.get("title")),
                timeout=45
            )
            if file_path and os.path.exists(file_path):
                track["file"] = file_path
                logger.info(f"Pre-download complete for queue #{position}: {file_path}")
    except asyncio.TimeoutError:
        logger.warning(f"Pre-download timed out for queue #{position}")
    except Exception as e:
        logger.debug(f"Pre-download failed (non-critical): {e}")

async def put_queue(
    chat_id,
    original_chat_id,
    file,
    title,
    duration,
    user_name,
    vidid,
    user_id,
    streamtype,
    forceplay: Union[bool, str] = None,
):
    title = title.title()
    if chat_id not in db:
        db[chat_id] = []
    
    try:
        from shakky.utils.formatters import time_to_seconds
        if duration and ":" in str(duration):
            duration_in_seconds = time_to_seconds(duration)
        else:
            duration_in_seconds = int(duration) if str(duration).isdigit() else 0
    except:
        duration_in_seconds = 0

    song_info = {
        "chat_id": chat_id,
        "file": os.path.abspath(file) if os.path.exists(file) else file,
        "title": title,
        "dur": duration or "0:00",
        "by": user_name,
        "vidid": vidid,
        "user_id": user_id,
        "streamtype": streamtype,
        "start_time": 0,
        "seconds": max(0, duration_in_seconds),
        "played": 0,
    }
    
    if forceplay:
        db[chat_id].insert(0, song_info)
    else:
        db[chat_id].append(song_info)

async def skip_and_play(chat_id, mention=None):
    if chat_id not in db or not db[chat_id]:
        await ani.stop_stream(chat_id)
        return

    # Call change_stream - it automatically pops the current song, 
    # handles loop logic, and starts the next stream in queue.
    try:
        from shakky.utils.database import group_assistant
        assistant = await group_assistant(ani, chat_id)
        await ani.change_stream(assistant, chat_id, mention=mention)
    except Exception as e:
        logger.error(f"Error in skip_and_play: {e}")
        await ani.stop_stream(chat_id)

