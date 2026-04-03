import asyncio
import random
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, WebAppInfo

from shakky import YouTube, app
from shakky.misc import SUDOERS, db
from shakky.utils.database import (
    get_active_chats,
    get_lang,
    get_upvote_count,
    is_active_chat,
    is_music_playing,
    is_nonadmin_chat,
    music_off,
    music_on,
    set_loop,
    remove_active_chat,
)
from shakky.utils.decorators.language import languageCB
from shakky.utils.formatters import seconds_to_min
from shakky.utils.inline import close_markup, stream_markup, stream_markup_timer
from shakky.utils.inline.play import panel_markup_1
from shakky.utils.stream.autoclear import auto_clean
from shakky.utils.thumbnails import get_thumb
from config import BANNED_USERS, adminlist, confirmer, votemode
from strings import get_string
import config

checker = {}
upvoters = {}

@app.on_callback_query(filters.regex("PanelMarkup") & ~BANNED_USERS)
@languageCB
async def markup_panel(client, CallbackQuery: CallbackQuery, _):
    await CallbackQuery.answer()
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    videoid, chat_id = callback_request.split("|")
    buttons = panel_markup_1(_, videoid, chat_id)
    try:
        await CallbackQuery.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        print(f"Error in markup_panel: {e}")
        return

@app.on_callback_query(filters.regex("MainMarkup") & ~BANNED_USERS)
@languageCB
async def main_markup_handler(client, CallbackQuery, _):
    await CallbackQuery.answer()
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    videoid, chat_id = callback_request.split("|")
    buttons = stream_markup(_, chat_id)
    try:
        await CallbackQuery.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        print(f"Error in main_markup_handler: {e}")
        return

@app.on_callback_query(filters.regex("Pages") & ~BANNED_USERS)
@languageCB
async def pages_handler(client, CallbackQuery, _):
    await CallbackQuery.answer()
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    state, pages, videoid, chat = callback_request.split("|")
    chat_id = int(chat)
    pages = int(pages)
    if state == "Forw":
        buttons = panel_markup_1(_, videoid, chat_id)
    else:
        buttons = stream_markup(_, chat_id)
    try:
        await CallbackQuery.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        print(f"Error in pages_handler: {e}")
        return

@app.on_callback_query(filters.regex("ADMIN") & ~BANNED_USERS)
@languageCB
async def del_back_playlist(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    command, chat = callback_request.split("|")
    if "_" in str(chat):
        bet = chat.split("_")
        chat = bet[0]
        counter = bet[1]
    chat_id = int(chat)
    if not await is_active_chat(chat_id):
        return await CallbackQuery.answer(_["general_5"], show_alert=True)
    mention = CallbackQuery.from_user.mention

    # Admin Check
    is_non_admin = await is_nonadmin_chat(CallbackQuery.message.chat.id)
    if not is_non_admin:
        if CallbackQuery.from_user.id not in SUDOERS:
            admins = adminlist.get(CallbackQuery.message.chat.id)
            if not admins:
                return await CallbackQuery.answer(_["admin_13"], show_alert=True)
            else:
                if CallbackQuery.from_user.id not in admins:
                    return await CallbackQuery.answer(_["admin_14"], show_alert=True)

    from shakky.core.call import ani
    from shakky.utils.webapp import notify_webapp
    from shakky.utils.stream.stream import skip_and_play
    from shakky.utils.formatters import time_to_seconds

    if command == "Pause":
        if chat_id not in db or not db[chat_id]:
            return await CallbackQuery.answer("➲ Nothing is playing.", show_alert=True)
        await CallbackQuery.answer("Paused ⏸")
        await ani.pause_stream(chat_id)
        db[chat_id][0]["paused"] = True
        await notify_webapp(chat_id, is_playing=False, action="pause")
        await CallbackQuery.message.reply_text(f"⏸ **Paused** by {mention}")

    elif command == "Resume":
        if chat_id not in db or not db[chat_id]:
            return await CallbackQuery.answer("➲ Nothing is paused.", show_alert=True)
        await CallbackQuery.answer("Resumed ▶")
        await ani.resume_stream(chat_id)
        db[chat_id][0]["paused"] = False
        await notify_webapp(chat_id, is_playing=True, action="resume")
        await CallbackQuery.message.reply_text(f"▶ **Resumed** by {mention}")

    elif command == "Stop" or command == "End":
        await CallbackQuery.answer("Stopped ⏹")
        db[chat_id] = []
        await remove_active_chat(chat_id)
        await ani.stop_stream(chat_id)
        await notify_webapp(chat_id, is_playing=False, action="stop")
        await CallbackQuery.message.reply_text(f"⏹ **Stopped** by {mention}")
        try:
            await CallbackQuery.message.delete()
        except:
            pass

    elif command == "Shuffle":
        check = db.get(chat_id)
        if not check or len(check) < 2:
            return await CallbackQuery.answer("➲ Not enough songs to shuffle.", show_alert=True)
        await CallbackQuery.answer("Shuffled 🔀")
        current = check.pop(0)
        random.shuffle(check)
        check.insert(0, current)
        await notify_webapp(chat_id, current_song=current, queue=check[1:], action="shuffle")
        await CallbackQuery.message.reply_text(f"🔀 **Shuffled** by {mention}")

    elif command == "Skip" or command == "Replay":
        if chat_id not in db or not db[chat_id]:
            return await CallbackQuery.answer("➲ Queue is empty.", show_alert=True)
        await CallbackQuery.answer("Skipped ⏭")
        await skip_and_play(chat_id)
        
        if not db.get(chat_id):
            await CallbackQuery.edit_message_text(f"⏭ **Skipped** by {mention}\n\n✧ Queue is now empty.")
        else:
            current = db[chat_id][0]
            from shakky.utils.inline.play import stream_markup as sm
            buttons = sm(_, chat_id)
            try:
                await CallbackQuery.edit_message_text(
                    f"✦ **NOW PLAYING**\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"✧ **Track:** `{current['title']}`\n"
                    f"✧ **Duration:** `{current.get('dur', '0:00')}`\n"
                    f"✧ **Skipped By:** {mention}",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            except Exception:
                await CallbackQuery.message.reply_text(
                    f"⏭ **Skipped** by {mention}\n🎵 Now playing: **{current['title']}**"
                )

    elif command == "Loop":
        await CallbackQuery.answer("Loop set ↺")
        await set_loop(chat_id, 10)
        await CallbackQuery.message.reply_text(f"↺ **Loop On (10x)** by {mention}")

    elif command.isdigit():  # Seek (1=10s back, 2=10s fwd)
        if chat_id not in db or not db[chat_id]:
            return await CallbackQuery.answer("➲ Nothing is playing.", show_alert=True)
        
        current = db[chat_id][0]
        duration_sec = time_to_seconds(current["dur"])
        played_sec = int(time.time() - current["start_time"])
        
        if command == "1": # 10s back
            to_seek = max(0, played_sec - 10)
        elif command == "2": # 10s fwd
            to_seek = min(duration_sec - 1, played_sec + 10)
        else:
            return await CallbackQuery.answer()

        await CallbackQuery.answer(f"Seeked to {seconds_to_min(to_seek)}")
        await ani.seek_stream(chat_id, to_seek)
        current["start_time"] = time.time() - to_seek
        await notify_webapp(chat_id, is_playing=True, action="seek", seek_to=to_seek)
        await CallbackQuery.message.reply_text(f"⏩ **Seeked** to {seconds_to_min(to_seek)} by {mention}")

@app.on_callback_query(filters.regex("close") & ~BANNED_USERS)
async def close_handler(client, CallbackQuery: CallbackQuery):
    await CallbackQuery.answer()
    try:
        await CallbackQuery.message.delete()
    except:
        pass

async def markup_timer():
    while True:
        await asyncio.sleep(5)
        active_chats = await get_active_chats()
        for chat_id in active_chats:
            try:
                playing = db.get(chat_id)
                if not playing or not await is_music_playing(chat_id):
                    continue
                
                mystic = playing[0].get("mystic")
                if not mystic:
                    continue
                    
                try:
                    language = await get_lang(chat_id)
                    _ = get_string(language)
                except:
                    _ = get_string("en")
                    
                buttons = stream_markup_timer(
                    _,
                    chat_id,
                    seconds_to_min(playing[0]["played"]),
                    playing[0]["dur"],
                )
                await mystic.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
            except:
                continue

asyncio.create_task(markup_timer())
