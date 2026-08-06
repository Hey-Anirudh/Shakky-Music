import asyncio
import re
from typing import Dict, List, Union

from pyrogram import filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    CallbackQuery,
)

from config import BANNED_USERS, SERVER_PLAYLIST_LIMIT
from shakky import app, YouTube
from shakky.core.mongo import mongodb
from shakky.utils.stream.stream import stream

playlistdb = mongodb.playlist


# ─── Storage helpers ─────────────────────────────────────────
async def _get_playlists(chat_id: int) -> Dict[str, dict]:
    _notes = await playlistdb.find_one({"chat_id": chat_id})
    if not _notes:
        return {}
    return _notes.get("notes", {}) or {}


async def get_playlist_names(chat_id: int) -> List[str]:
    return list((await _get_playlists(chat_id)).keys())


async def get_playlist(chat_id: int, name: str) -> Union[bool, dict]:
    return (await _get_playlists(chat_id)).get(name, False)


async def save_playlist(chat_id: int, name: str, note: dict):
    _notes = await _get_playlists(chat_id)
    if len(_notes) >= SERVER_PLAYLIST_LIMIT and name not in _notes:
        raise ValueError(
            f"Playlist limit reached ({SERVER_PLAYLIST_LIMIT} songs)."
        )
    _notes[name] = note
    await playlistdb.update_one(
        {"chat_id": chat_id}, {"$set": {"notes": _notes}}, upsert=True
    )


async def delete_playlist(chat_id: int, name: str) -> bool:
    _notes = await _get_playlists(chat_id)
    if name in _notes:
        del _notes[name]
        await playlistdb.update_one(
            {"chat_id": chat_id},
            {"$set": {"notes": _notes}},
            upsert=True,
        )
        return True
    return False


# ─── Video ID / metadata helpers ─────────────────────────────
def _extract_videoid(text: str) -> str:
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([a-zA-Z0-9_-]{11})", text or "")
    return m.group(1) if m else (text if re.fullmatch(r"[a-zA-Z0-9_-]{11}", text or "") else "")


async def _resolve_duration(dur):
    """Normalize a duration value to a display string."""
    if not dur or dur == "—":
        return "—"
    try:
        return _to_duration(int(dur))
    except (TypeError, ValueError):
        return str(dur)


def _to_duration(seconds) -> str:
    if not seconds:
        return "—"
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ─── /playlist ──────────────────────────────────────────────
@app.on_message(filters.command("playlist") & ~BANNED_USERS)
async def check_playlist(_, message: Message):
    user_id = message.from_user.id
    keys = await get_playlist_names(user_id)
    if not keys:
        return await message.reply_text(
            "➲ **Your playlist is empty.**\n"
            "Add songs with `/addplay`."
        )
    title = f"🎧 <b>Your Playlist</b> — {len(keys)} songs\n━━━━━━━━━━━━━━━━━━\n"
    for i, key in enumerate(keys, 1):
        note = await get_playlist(user_id, key) or {}
        song_title = str(note.get("title", key))[:45]
        duration = note.get("duration", "—")
        title += f"\n<code>{i}.</code> {song_title}\n    ✧ Duration: <code>{duration}</code>"
    await message.reply_text(
        title,
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("▶ Play", callback_data="play_playlist a"),
                    InlineKeyboardButton("▶ Play Video", callback_data="play_playlist v"),
                ],
                [InlineKeyboardButton("🗑 Edit", callback_data="open_playlist")],
                [InlineKeyboardButton("✕", callback_data="close")],
            ]
        ),
    )


# ─── /playplaylist ───────────────────────────────────────────
@app.on_message(filters.command("playplaylist") & ~BANNED_USERS)
async def play_playlist_command(client, message: Message):
    user_id = message.from_user.id
    keys = await get_playlist_names(user_id)
    if not keys:
        return await message.reply_text(
            "➲ **Your playlist is empty.**\nAdd songs with `/addplay`."
        )
    video = len(message.command) > 1 and message.command[1].lower() == "v"
    chat_id = message.chat.id
    user_name = message.from_user.first_name
    mystic = await message.reply_text("➲ **Playing your playlist...**")
    try:
        await stream(
            None, mystic, user_id, keys, chat_id, user_name, chat_id,
            True if video else None, streamtype="playlist",
        )
    except Exception as e:
        await mystic.edit_text(f"❌ **Error:** {e}")


# ─── /addplay ────────────────────────────────────────────────
@app.on_message(filters.command(["addplay", "addplaylist", "ap"]) & ~BANNED_USERS)
async def add_playlist(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "➲ **Usage:** `/addplay <song name or YouTube link>`\n"
            "Supports song names, single YouTube links, playlists and channel links.",
        )

    query = " ".join(message.command[1:]).strip()
    user_id = message.from_user.id
    mystic = await message.reply_text("➲ **Processing...**")

    # 1) YouTube playlist link
    if "youtube.com/playlist" in query or "list=" in query:
        try:
            results = await YouTube.playlist(query, limit=SERVER_PLAYLIST_LIMIT)
        except Exception as e:
            return await mystic.edit_text(f"❌ **Playlist fetch failed:** {e}")
        if not results:
            return await mystic.edit_text("➲ **No songs found in that playlist.**")
        added = 0
        for track in results:
            vidid = track.get("vidid") or _extract_videoid(track.get("url", ""))
            if not vidid:
                continue
            try:
                await save_playlist(
                    user_id, vidid,
                    {"videoid": vidid, "title": track.get("title", vidid)[:50],
                     "duration": _resolve_duration(track.get("duration"))},
                )
                added += 1
            except ValueError:
                break
        await mystic.delete()
        return await message.reply_text(
            f"✅ **Added {added} song(s) to your playlist!**\n\n🎧 Check: /playlist"
        )

    # 2) YouTube channel link
    if "youtube.com/@" in query or "youtube.com/channel/" in query:
        entries = await _fetch_channel_videos(query)
        if not entries:
            return await mystic.edit_text("➲ **No videos found on that channel.**")
        added = 0
        for vidid, vtitle in entries:
            try:
                await save_playlist(
                    user_id, vidid,
                    {"videoid": vidid, "title": vtitle[:50], "duration": "—"},
                )
                added += 1
            except ValueError:
                break
        await mystic.delete()
        return await message.reply_text(
            f"✅ **Added {added} songs from the channel to your playlist!**\n\n🎧 Check: /playlist"
        )

    # 3) Single YouTube video link or raw ID
    videoid = _extract_videoid(query)
    if videoid:
        try:
            title, duration = await _details(videoid)
        except Exception as e:
            return await mystic.edit_text(f"❌ **Error:** {e}")
        try:
            await save_playlist(
                user_id, videoid,
                {"videoid": videoid, "title": title, "duration": duration},
            )
        except ValueError as e:
            return await mystic.edit_text(f"❌ {e}")
        await mystic.delete()
        return await message.reply_text(
            f"✅ **Added:** <code>{title}</code>\n\n🎧 Check: /playlist"
        )

    # 4) Song name → YouTube search
    try:
        result = await YouTube.search(query)
        if not result or not result.get("vidid"):
            return await mystic.edit_text("➲ **No results found on YouTube.**")
        await save_playlist(
            user_id, result["vidid"],
            {"videoid": result["vidid"], "title": str(result.get("title"))[:50],
             "duration": result.get("duration", "—")},
        )
    except Exception as e:
        return await mystic.edit_text(f"❌ **Error:** {e}")
    await mystic.delete()
    await message.reply_text(
        f"✅ **Added:** <code>{result.get('title', '')[:40]}</code>\n\n🎧 Check: /playlist"
    )


async def _details(vidid: str):
    """Return (title, duration) for a video ID."""
    try:
        title, dur_min, _, _, vid = await YouTube.details(vidid, True)
        return (title or vidid)[:50], (dur_min or "—")
    except Exception:
        return vidid, "—"


async def _fetch_channel_videos(channel_url: str) -> List[tuple]:
    """Fetch recent video entries from a YouTube channel via yt-dlp."""
    try:
        import yt_dlp

        opts = {
            "quiet": True,
            "extract_flat": True,
            "playlist_items": "1-50",
            "noplaylist": False,
        }
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = await loop.run_in_executor(
                None, lambda: ydl.extract_info(channel_url, download=False)
            )
        entries = info.get("entries", []) or []
        return [
            (e.get("id"), e.get("title", ""))
            for e in entries
            if e.get("id") and e.get("title")
        ]
    except Exception:
        return []


# ─── /delplaylist ────────────────────────────────────────────
async def _make_del_keyboard(uid: int):
    keys = await get_playlist_names(uid)
    rows = []
    for name in keys:
        note = await get_playlist(uid, name) or {}
        title = str(note.get("title", name))[:30]
        rows.append([InlineKeyboardButton(f"🗑 {title}", callback_data=f"del_playlist {uid}|{name}")])
    rows.append(
        [
            InlineKeyboardButton("🗑 Delete All", callback_data="delete_warning"),
            InlineKeyboardButton("✕", callback_data="close"),
        ]
    )
    return InlineKeyboardMarkup(rows)


@app.on_message(filters.command(["delplaylist", "rp"]) & ~BANNED_USERS)
async def del_plist_msg(client, message: Message):
    user_id = message.from_user.id
    keys = await get_playlist_names(user_id)
    if not keys:
        return await message.reply_text("➲ **Your playlist is empty.**")
    await message.reply_text(
        f"➲ <b>Delete songs</b> — {len(keys)}\nTap a song to remove it.",
        reply_markup=await _make_del_keyboard(user_id),
    )


# ─── Callbacks ───────────────────────────────────────────────
@app.on_callback_query(filters.regex("del_playlist") & ~BANNED_USERS)
async def del_plist_cb(client, cb: CallbackQuery):
    try:
        user_id, name = cb.data.replace("del_playlist ", "").split("|")
    except ValueError:
        return await cb.answer("Invalid selection.", show_alert=True)
    ok = await delete_playlist(int(user_id), name)
    if ok:
        await cb.answer("Song removed from playlist.")
        try:
            await cb.message.edit_text(
                "➲ <b>Delete songs</b>\nTap a song to remove it.",
                reply_markup=await _make_del_keyboard(int(user_id)),
            )
        except Exception:
            pass


@app.on_callback_query(filters.regex("open_playlist") & ~BANNED_USERS)
async def open_plist_cb(client, cb: CallbackQuery):
    user_id = cb.from_user.id
    keys = await get_playlist_names(user_id)
    if not keys:
        return await cb.message.edit_text("🎉 **Your playlist is empty.**")
    await cb.message.edit_text(
        f"➲ <b>Delete songs</b> — {len(keys)}\nTap a song to remove it.",
        reply_markup=await _make_del_keyboard(user_id),
    )


@app.on_callback_query(filters.regex("play_playlist") & ~BANNED_USERS)
async def cb_play_playlist(client, cb: CallbackQuery):
    try:
        mode = cb.data.split(None, 1)[1]
    except IndexError:
        mode = "a"
    user_id = cb.from_user.id
    keys = await get_playlist_names(user_id)
    if not keys:
        return await cb.answer("Your playlist is empty.", show_alert=True)
    chat_id = cb.message.chat.id
    user_name = cb.from_user.first_name
    mystic = await cb.message.reply("➲ **Loading playlist...**")
    try:
        await stream(
            None, mystic, user_id, keys, chat_id, user_name, chat_id,
            True if mode == "v" else None, streamtype="playlist",
        )
    except Exception as e:
        await mystic.edit_text(f"❌ **Error:** {e}")


@app.on_callback_query(filters.regex("delete_warning") & ~BANNED_USERS)
async def cb_delete_warning(client, cb: CallbackQuery):
    await cb.message.edit_text(
        "⚠️ <b>Delete your entire playlist?</b>\n\nThis cannot be undone.",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🗑 Yes, delete all", callback_data="delete_whole_playlist")],
                [InlineKeyboardButton("✕ Cancel", callback_data="close")],
            ]
        ),
    )


@app.on_callback_query(filters.regex("delete_whole_playlist") & ~BANNED_USERS)
async def cb_delete_whole(client, cb: CallbackQuery):
    for name in await get_playlist_names(cb.from_user.id):
        await delete_playlist(cb.from_user.id, name)
    await cb.message.edit_text("🗑 **Playlist deleted successfully.**")


@app.on_callback_query(filters.regex("del_back_playlist") & ~BANNED_USERS)
async def cb_del_back(client, cb: CallbackQuery):
    await cb.message.edit_text(
        "➲ <b>Delete songs</b>",
        reply_markup=await _make_del_keyboard(cb.from_user.id),
    )


# Compatibility: remove_playlist / recover_playlist legacy buttons
@app.on_callback_query(filters.regex("remove_playlist|recover_playlist") & ~BANNED_USERS)
async def cb_remove_recover(client, cb: CallbackQuery):
    try:
        name = cb.data.split(None, 1)[1]
    except Exception:
        return
    if "remove" in cb.data:
        await delete_playlist(cb.from_user.id, name)
    await cb.answer("Done.", show_alert=False)