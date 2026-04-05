import random
import string
import asyncio
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InputMediaPhoto, Message
import config
import logging
from shakky import Apple, Resso, SoundCloud, Spotify, Telegram, YouTube, app
logger = logging.getLogger("shakky.play")
from shakky.utils import seconds_to_min, time_to_seconds
from shakky.utils.channelplay import get_channeplayCB
from shakky.utils.decorators.language import languageCB
from shakky.utils.decorators.play import PlayWrapper
from shakky.utils.formatters import formats
from shakky.utils.inline import (
    botplaylist_markup,
    livestream_markup,
    playlist_markup,
    slider_markup,
    track_markup,
)
from shakky.utils.logger import play_logs
from shakky.utils.stream.stream import stream
from config import BANNED_USERS, lyrical, AYU


import random
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from shakky import YouTube, app
from shakky.utils.decorators.language import language
from config import BANNED_USERS

async def _animate_loader(mystic: Message, sticker: Message = None):
    """Animates the searching dots until message is deleted/edited."""
    frames = [
        "➲ **Searching.**", 
        "➲ **Searching..**", 
        "➲ **Searching...**",
        "➲ **Searching..**"
    ]
    i = 0
    while True:
        try:
            await asyncio.sleep(3.5) # Even slower to be safe
            await mystic.edit_text(frames[i % len(frames)])
            i += 1
        except Exception:
            # If the main message is gone, try to delete the sticker too
            if sticker:
                try: await sticker.delete()
                except: pass
            break

@app.on_message(
    filters.command(["play", "vplay", "cplay", "cvplay", "playforce", "vplayforce", "cplayforce", "cvplayforce"], prefixes=["/", "!", ""])
    & filters.group
    & ~BANNED_USERS
)
@language
async def play_commnd(client, message: Message, _):
    """
    Entry point for playback (Step 1 & 2)
    1. Send loading message
    2. Search YouTube
    3. Call stream engine
    """
    query = message.text.split(None, 1)[1] if len(message.command) > 1 else None
    
    # Common variables needed for all play types
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    chat_id = message.chat.id
    forceplay = "force" in message.command[0]

    # --- Sticker-only loading indicator helper ---
    async def send_loader():
        try:
            from config import START_STICKER
            return await message.reply_sticker(START_STICKER)
        except: return await message.reply_text("➲ **Searching.**")

    # --- Telegram Media (Reply) Detection ---
    if message.reply_to_message:
        rm = message.reply_to_message
        if rm.audio or rm.voice or rm.video or rm.document:
            # If it's a document, check if it's an audio/video file
            if rm.document and not (rm.document.mime_type.startswith("audio") or rm.document.mime_type.startswith("video")):
                 pass # Not a playable document
            else:
                mystic = await send_loader()
                asyncio.create_task(_animate_loader(mystic))
                
                try:
                    await stream(
                        _, mystic, user_id, rm, chat_id, user_name, chat_id,
                        streamtype="telegram", forceplay=forceplay
                    )
                    return
                except Exception as e:
                    # In case of error, the loader will be auto-deleted by stream or _animate_loader
                    return await message.reply_text(f"❌ Telegram Media Error: {e}")

    if not query and not message.reply_to_message:
        return await message.reply_text("➲ **Please provide a song name or reply to an audio file.**")

    # Sticker-only loading indicator
    mystic = None
    try:
        from config import START_STICKER
        # Try sending as file_id first (user provided specifics)
        try:
            mystic = await message.reply_sticker(START_STICKER)
        except Exception:
            # Fallback to random pick from set if file_id fails
            import random
            sticker_set = await client.get_sticker_set(START_STICKER)
            if sticker_set and sticker_set.stickers:
                sticker = random.choice(sticker_set.stickers)
                mystic = await message.reply_sticker(sticker.file_id)
    except Exception as e:
        logger.debug(f"Failed to send sticker: {e}")

    # Fallback to text only if EVERYTHING fails
    if not mystic:
        mystic = await message.reply_text("➲ **Searching.**")

    asyncio.create_task(_animate_loader(mystic))

    # --- Spotify Link Detection ---
    from shakky import Spotify
    if await Spotify.valid(query):
        if "track" in query:
            try:
                res, vidid = await Spotify.track(query)
                await stream(
                    _, mystic, user_id, res, chat_id, user_name, chat_id,
                    streamtype="spotify", spotify=True, forceplay=forceplay
                )
                return
            except Exception as e:
                return await mystic.edit_text(f"❌ Spotify Error: {e}")
        elif "playlist" in query or "album" in query or "artist" in query:
             try:
                 # Fetch metadata first to know if we even have tracks
                 if "playlist" in query:
                     result, spotify_id = await Spotify.playlist(query)
                 elif "album" in query:
                     result, spotify_id = await Spotify.album(query)
                 else:
                     result, spotify_id = await Spotify.artist(query)
                 
                 # Optimization: Delete the loader early for playlists since processing result takes time
                 try: await mystic.delete()
                 except: pass
                 
                 await stream(
                     _, mystic, user_id, result, chat_id, user_name, chat_id,
                     streamtype="spotify", spotify=True, forceplay=forceplay
                 )
                 return
             except Exception as e:
                 return await mystic.edit_text(f"❌ Spotify Batch Error: {e}")

    # --- YouTube Logic ---
    try:
        # Step 1: YouTube Search (metadata only)
        result = await YouTube.search(query)
        if not result:
            return await mystic.edit_text("❌ No results found on YouTube.")
            
        # Step 2: Handoff to stream engine (Already handled user_id, chat_id above)
        
        await stream(
            _,
            mystic,
            user_id,
            result,
            chat_id,
            user_name,
            chat_id,
            streamtype="youtube",
            forceplay=forceplay,
            raw_query=query
        )
        
    except Exception as e:
        logger.error(f"Error in play_commnd: {e}")
        try:
            from pyrogram.errors import FloodWait
            try:
                await mystic.edit_text(f"❌ Error: {str(e)}")
            except FloodWait as fw:
                await asyncio.sleep(fw.value)
                await mystic.edit_text(f"❌ Error: {str(e)}")
            except Exception:
                await message.reply_text(f"❌ Error: {str(e)}")
        except Exception:
            pass

# Anonymous Admin handler
@app.on_callback_query(filters.regex("AnonymousAdmin") & ~BANNED_USERS)
async def Anonymous_check(client, CallbackQuery):
    try:
        await CallbackQuery.answer(
            "» Please use a real account to manage playback.",
            show_alert=True,
        )
    except:
        pass


@app.on_callback_query(filters.regex("aniPlaylists") & ~BANNED_USERS)
@languageCB
async def play_playlists_command(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    (
        videoid,
        user_id,
        ptype,
        mode,
        cplay,
        fplay,
    ) = callback_request.split("|")
    if CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)
        except:
            return
    try:
        chat_id, channel = await get_channeplayCB(_, cplay, CallbackQuery)
    except:
        return
    user_name = CallbackQuery.from_user.first_name
    await CallbackQuery.message.delete()
    try:
        await CallbackQuery.answer()
    except:
        pass
    mystic = await CallbackQuery.message.reply_text(
        _["play_2"].format(channel) if channel else random.choice(AYU)
    )
    videoid = lyrical.get(videoid)
    video = True if mode == "v" else None
    ffplay = True if fplay == "f" else None
    spotify = True
    if ptype == "yt":
        spotify = False
        try:
            result = await YouTube.playlist(
                videoid,
                config.PLAYLIST_FETCH_LIMIT,
                CallbackQuery.from_user.id,
                True,
            )
        except:
            return await mystic.edit_text(_["play_3"])
    if ptype == "spplay":
        try:
            result, spotify_id = await Spotify.playlist(videoid)
        except:
            return await mystic.edit_text(_["play_3"])
    if ptype == "spalbum":
        try:
            result, spotify_id = await Spotify.album(videoid)
        except:
            return await mystic.edit_text(_["play_3"])
    if ptype == "spartist":
        try:
            result, spotify_id = await Spotify.artist(videoid)
        except:
            return await mystic.edit_text(_["play_3"])
    if ptype == "apple":
        try:
            result, apple_id = await Apple.playlist(videoid, True)
        except:
            return await mystic.edit_text(_["play_3"])
    try:
        await stream(
            _,
            mystic,
            user_id,
            result,
            chat_id,
            user_name,
            CallbackQuery.message.chat.id,
            video,
            streamtype="playlist",
            spotify=spotify,
            forceplay=ffplay,
        )
    except Exception as e:
        ex_type = type(e).__name__
        err = str(e) if ex_type == "AssistantErr" else _["general_2"].format(ex_type)
        return await mystic.edit_text(err)
    return


@app.on_callback_query(filters.regex("slider") & ~BANNED_USERS)
@languageCB
async def slider_queries(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    (
        what,
        rtype,
        query,
        user_id,
        cplay,
        fplay,
    ) = callback_request.split("|")
    if CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)
        except:
            return
    what = str(what)
    rtype = int(rtype)
    if what == "F":
        if rtype == 9:
            query_type = 0
        else:
            query_type = int(rtype + 1)
        try:
            await CallbackQuery.answer(_["playcb_2"])
        except:
            pass
        title, duration_min, thumbnail, vidid = await YouTube.slider(query, query_type)
        buttons = slider_markup(_, vidid, user_id, query, query_type, cplay, fplay)
        return await CallbackQuery.edit_message_text(
            text=_["play_10"].format(
                title.title(),
                duration_min,
            ),
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    if what == "B":
        if rtype == 0:
            query_type = 9
        else:
            query_type = int(rtype - 1)
        try:
            await CallbackQuery.answer(_["playcb_2"])
        except:
            pass
        title, duration_min, thumbnail, vidid = await YouTube.slider(query, query_type)
        buttons = slider_markup(_, vidid, user_id, query, query_type, cplay, fplay)
        return await CallbackQuery.edit_message_text(
            text=_["play_10"].format(
                title.title(),
                duration_min,
            ),
            reply_markup=InlineKeyboardMarkup(buttons)
        )
