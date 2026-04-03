import asyncio
import os
from datetime import datetime, timedelta
from typing import Union

from pyrogram import Client
from pyrogram.enums import ChatType
from pyrogram.errors import PeerIdInvalid, ChatWriteForbidden
from pyrogram.types import InlineKeyboardMarkup
from pytgcalls import PyTgCalls, StreamType
from pytgcalls.exceptions import (
    AlreadyJoinedError,
    NoActiveGroupCall,
    TelegramServerError,
)
from pytgcalls.types import Update
from pytgcalls.types.input_stream import AudioPiped, AudioVideoPiped
from pytgcalls.types.input_stream.quality import HighQualityAudio, MediumQualityVideo
from pytgcalls.types.stream import StreamAudioEnded

import config
from shakky import YouTube, app
from shakky.misc import db
from shakky.utils.database import (
    add_active_chat,
    add_active_video_chat,
    get_lang,
    get_loop,
    group_assistant,
    is_autoend,
    music_on,
    remove_active_chat,
    remove_active_video_chat,
    set_loop,
)
from shakky.utils.exceptions import AssistantErr
from shakky.utils.formatters import check_duration, seconds_to_min, speed_converter
from shakky.utils.inline.play import stream_markup
from shakky.utils.stream.autoclear import auto_clean
from shakky.utils.webapp import notify_webapp
from shakky.utils.thumbnails import get_thumb
from strings import get_string

autoend = {}
counter = {}

import logging

# Configure basic logging so messages actually appear
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

LOGGER = logging.getLogger(__name__)

async def _clear_(chat_id):
    db[chat_id] = []
    await remove_active_video_chat(chat_id)
    await remove_active_chat(chat_id)


class Call(PyTgCalls):
    def __init__(self):
        self.userbot1 = Client(
            name="Ass1",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING1),
        )
        self.one = PyTgCalls(
            self.userbot1,
            cache_duration=100,
        )
        
        self.userbot2 = Client(
            name="Ass2",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING2),
        )
        self.two = PyTgCalls(
            self.userbot2,
            cache_duration=100,
        )
        self.userbot3 = Client(
            name="Ass3",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING3),
        )
        self.three = PyTgCalls(
            self.userbot3,
            cache_duration=100,
        )
        self.userbot4 = Client(
            name="Ass4",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING4),
        )
        self.four = PyTgCalls(
            self.userbot4,
            cache_duration=100,
        )
        self.userbot5 = Client(
            name="Ass5",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING5),
        )
        self.five = PyTgCalls(
            self.userbot5,
            cache_duration=100,
        )
        self._locks = {}

    def get_lock(self, chat_id: int):
        if chat_id not in self._locks:
            self._locks[chat_id] = asyncio.Lock()
        return self._locks[chat_id]

    async def pause_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.pause_stream(chat_id)
        try:
            await notify_webapp(chat_id, action="pause")
        except: pass

    async def resume_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.resume_stream(chat_id)
        try:
            await notify_webapp(chat_id, action="play")
        except: pass

    async def stop_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        try:
            await _clear_(chat_id)
            await assistant.leave_group_call(chat_id)
        except:
            pass
        try:
            await notify_webapp(chat_id, action="stop")
        except: pass

    async def stop_stream_force(self, chat_id: int):
        try:
            if config.STRING1:
                await self.one.leave_group_call(chat_id)
        except:
            pass
        try:
            if config.STRING2:
                await self.two.leave_group_call(chat_id)
        except:
            pass
        try:
            if config.STRING3:
                await self.three.leave_group_call(chat_id)
        except:
            pass
        try:
            if config.STRING4:
                await self.four.leave_group_call(chat_id)
        except:
            pass
        try:
            if config.STRING5:
                await self.five.leave_group_call(chat_id)
        except:
            pass
        try:
            await _clear_(chat_id)
        except:
            pass

    async def speedup_stream(self, chat_id: int, file_path, speed, playing):
        assistant = await group_assistant(self, chat_id)
        if str(speed) != str("1.0"):
            base = os.path.basename(file_path)
            chatdir = os.path.join(os.getcwd(), "playback", str(speed))
            if not os.path.isdir(chatdir):
                os.makedirs(chatdir)
            out = os.path.join(chatdir, base)
            if not os.path.isfile(out):
                if str(speed) == str("0.5"):
                    vs = 2.0
                if str(speed) == str("0.75"):
                    vs = 1.35
                if str(speed) == str("1.5"):
                    vs = 0.68
                if str(speed) == str("2.0"):
                    vs = 0.5
                proc = await asyncio.create_subprocess_shell(
                    cmd=(
                        "ffmpeg "
                        "-i "
                        f"{file_path} "
                        "-filter:v "
                        f"setpts={vs}*PTS "
                        "-filter:a "
                        f"atempo={speed} "
                        f"{out}"
                    ),
                    stdin=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
            else:
                pass
        else:
            out = file_path
        dur = await asyncio.get_event_loop().run_in_executor(None, check_duration, out)
        dur = int(dur)
        played, con_seconds = speed_converter(playing[0]["played"], speed)
        duration = seconds_to_min(dur)
        stream = (
            AudioVideoPiped(
                out,
                audio_parameters=HighQualityAudio(),
                video_parameters=MediumQualityVideo(),
                additional_ffmpeg_parameters=f"-ss {played} -to {duration}",
            )
            if playing[0]["streamtype"] == "video"
            else AudioPiped(
                out,
                audio_parameters=HighQualityAudio(),
                additional_ffmpeg_parameters=f"-ss {played} -to {duration}",
            )
        )
        if str(db[chat_id][0]["file"]) == str(file_path):
            await assistant.change_stream(chat_id, stream)
        else:
            raise AssistantErr("Umm")
        if str(db[chat_id][0]["file"]) == str(file_path):
            exis = (playing[0]).get("old_dur")
            if not exis:
                db[chat_id][0]["old_dur"] = db[chat_id][0]["dur"]
                db[chat_id][0]["old_second"] = db[chat_id][0]["seconds"]
            db[chat_id][0]["played"] = con_seconds
            db[chat_id][0]["dur"] = duration
            db[chat_id][0]["seconds"] = dur
            db[chat_id][0]["speed_path"] = out
            db[chat_id][0]["speed"] = speed

    async def force_stop_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        try:
            check = db.get(chat_id)
            check.pop(0)
        except:
            pass
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        try:
            await assistant.leave_group_call(chat_id)
        except:
            pass

    async def skip_stream(
        self,
        chat_id: int,
        link: str,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        assistant = await group_assistant(self, chat_id)
        if video:
            stream = AudioVideoPiped(
                link,
                audio_parameters=HighQualityAudio(),
                video_parameters=MediumQualityVideo(),
            )
        else:
            stream = AudioPiped(link, audio_parameters=HighQualityAudio())
        await assistant.change_stream(
            chat_id,
            stream,
        )

    async def seek_stream(self, chat_id, file_path, to_seek, duration, mode):
        assistant = await group_assistant(self, chat_id)
        # Convert to_seek to int seconds if it's a string (e.g. "01:30")
        try:
            if isinstance(to_seek, str) and ":" in to_seek:
                from shakky.utils.formatters import time_to_seconds
                to_seek_seconds = time_to_seconds(to_seek)
            else:
                to_seek_seconds = int(to_seek)
        except:
            to_seek_seconds = 0

        stream = (
            AudioVideoPiped(
                file_path,
                audio_parameters=HighQualityAudio(),
                video_parameters=MediumQualityVideo(),
                additional_ffmpeg_parameters=f"-ss {to_seek_seconds} -to {duration}",
            )
            if mode == "video"
            else AudioPiped(
                file_path,
                audio_parameters=HighQualityAudio(),
                additional_ffmpeg_parameters=f"-ss {to_seek_seconds} -to {duration}",
            )
        )
        await assistant.change_stream(chat_id, stream)

    async def stream_call(self, link):
        assistant = await group_assistant(self, config.LOG_GROUP_ID)
        await assistant.join_group_call(
            config.LOG_GROUP_ID,
            AudioVideoPiped(link),
            stream_type=StreamType().pulse_stream,
        )
        await asyncio.sleep(0.2)
        await assistant.leave_group_call(config.LOG_GROUP_ID)

    async def join_call(
        self,
        chat_id: int,
        original_chat_id: int,
        link,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        assistant = await group_assistant(self, chat_id)
        language = await get_lang(chat_id)
        _ = get_string(language)
        if video:
            stream = AudioVideoPiped(
                link,
                audio_parameters=HighQualityAudio(),
                video_parameters=MediumQualityVideo(),
            )
        else:
            stream = (
                AudioVideoPiped(
                    link,
                    audio_parameters=HighQualityAudio(),
                    video_parameters=MediumQualityVideo(),
                )
                if video
                else AudioPiped(link, audio_parameters=HighQualityAudio())
            )
        # --- JIT Assistant Metadata Sync ---
        userbot = None
        if assistant == self.one: userbot = self.userbot1
        elif assistant == self.two: userbot = self.userbot2
        elif assistant == self.three: userbot = self.userbot3
        elif assistant == self.four: userbot = self.userbot4
        elif assistant == self.five: userbot = self.userbot5

        async def refresh_vc_state():
            if not userbot: return
            try:
                # get_chat is more robust than resolve_peer for populating local cache
                chat = await userbot.get_chat(chat_id)
                # If it's a channel, we need the FullChannel info for VC detection
                if chat.type in [ChatType.CHANNEL, ChatType.SUPERGROUP]:
                    from pyrogram.raw.functions.channels import GetFullChannel
                    peer = await userbot.resolve_peer(chat_id)
                    await userbot.invoke(GetFullChannel(channel=peer))
                else:
                    from pyrogram.raw.functions.messages import GetFullChat
                    await userbot.invoke(GetFullChat(chat_id=chat_id))
            except Exception as e:
                LOGGER.warning(f"[join_call] VC state sync failed for {chat_id}: {e}")

        await refresh_vc_state()

        # --- Joining Logic with Robust Retries ---
        joined = False
        last_err = None
        for attempt in range(3):
            try:
                await assistant.join_group_call(chat_id, stream)
                joined = True
                break
            except AlreadyJoinedError:
                joined = True
                break
            except NoActiveGroupCall as e:
                last_err = e
                # Maybe the assistant was just added or the VC just started
                LOGGER.warning(f"[join_call] Attempt {attempt+1}: NoActiveGroupCall. Refreshing...")
                await refresh_vc_state()
                await asyncio.sleep(2)
                try:
                    # Retry with pulse_stream which is sometimes more aggressive
                    await assistant.join_group_call(
                        chat_id, stream, stream_type=StreamType().pulse_stream
                    )
                    joined = True
                    break
                except AlreadyJoinedError:
                    joined = True
                    break
                except Exception as e2:
                    last_err = e2
                    LOGGER.warning(f"[join_call] pulse_stream failed after refresh on attempt {attempt+1}: {e2}")
            except (PeerIdInvalid, ChatWriteForbidden):
                # Assistant might NOT be in the group!
                LOGGER.info(f"Assistant {assistant} not in chat {chat_id}. Attempting to join...")
                try:
                    invitelink = (await app.get_chat(chat_id)).invite_link
                    if invitelink:
                        await userbot.join_chat(invitelink)
                        await refresh_vc_state()
                    else:
                        LOGGER.error("No invite link found to join assistant.")
                except Exception as join_err:
                    LOGGER.error(f"Assistant join failed: {join_err}")
                last_err = PeerIdInvalid
            except Exception as e:
                last_err = e
                LOGGER.error(f"[join_call] Attempt {attempt+1} unexpected: {e}")
            
            if not joined and attempt < 2:
                await asyncio.sleep(2)

        if not joined:
            LOGGER.error(f"[join_call] All 3 attempts failed completely. Last error: {last_err}")
            raise AssistantErr("➲ **Failed to join the Voice Chat. Ensure it's active or use /reboot ᴛᴏ ʀᴇғʀᴇsʜ.**")


        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video:
            await add_active_video_chat(chat_id)
        if await is_autoend():
            counter[chat_id] = {}
            try:
                users = len(await assistant.get_participants(chat_id))
                if users == 1:
                    autoend[chat_id] = datetime.now() + timedelta(minutes=1)
            except: pass
        

    async def change_stream(self, client, chat_id):
        lock = self.get_lock(chat_id)
        async with lock:
            check = db.get(chat_id)
            if not check:
                await _clear_(chat_id)
                try:
                    return await client.leave_group_call(chat_id)
                except:
                    return

            popped = None
            loop = await get_loop(chat_id)
            try:
                if loop == 0:
                    popped = check.pop(0)
                else:
                    loop = loop - 1
                    await set_loop(chat_id, loop)
                
                if popped:
                    await auto_clean(popped)
                
                if not check:
                    await _clear_(chat_id)
                    try:
                        return await client.leave_group_call(chat_id)
                    except:
                        return
            except Exception as e:
                LOGGER.error(f"Error in change_stream: {e}")
                try:
                    await _clear_(chat_id)
                    return await client.leave_group_call(chat_id)
                except:
                    return

            queued = check[0]["file"]
            language = await get_lang(chat_id)
            _ = get_string(language)
            title = (check[0]["title"]).title()
            user = check[0]["by"]
            original_chat_id = check[0]["chat_id"]
            streamtype = check[0]["streamtype"]
            videoid = check[0]["vidid"]
            
            db[chat_id][0]["played"] = 0
            exis = (check[0]).get("old_dur")
            if exis:
                db[chat_id][0]["dur"] = exis
                db[chat_id][0]["seconds"] = check[0]["old_second"]
                db[chat_id][0]["speed_path"] = None
                db[chat_id][0]["speed"] = 1.0
            video = True if str(streamtype) == "video" else False

            # --- JIT Download for vid_ references ---
            if "vid_" in queued:
                if not os.path.exists(queued) and videoid:
                    try:
                        from shakky.platforms import YouTube as YT
                        file_path, direct = await YT.download(
                            videoid, video=video, raw_query=title
                        )
                        if file_path and os.path.exists(file_path):
                            queued = file_path
                            db[chat_id][0]["file"] = file_path
                            # Update duration from downloaded file
                            try:
                                dur = await asyncio.get_event_loop().run_in_executor(
                                    None, check_duration, file_path
                                )
                                dur = int(dur)
                                db[chat_id][0]["seconds"] = dur
                                db[chat_id][0]["dur"] = seconds_to_min(dur)
                            except:
                                pass
                        else:
                            LOGGER.error(f"JIT download returned no file for {videoid}")
                            queued = None
                    except Exception as e:
                        LOGGER.error(f"Failed JIT Download in change_stream: {e}")
                        queued = None
                else:
                    # vid_ prefix but file exists or no videoid
                    queued = queued if os.path.exists(queued) else None

            elif "live_" in queued:
                n, link = await YouTube.video(videoid, True)
                if n == 0:
                    return await app.send_message(original_chat_id, text="Error fetching live stream.")
                queued = link

            # --- Build stream object ---
            if not queued:
                LOGGER.error(f"No valid file to stream for chat {chat_id}")
                await _clear_(chat_id)
                try:
                    return await client.leave_group_call(chat_id)
                except:
                    return

            if video:
                stream = AudioVideoPiped(queued, HighQualityAudio(), MediumQualityVideo())
            else:
                stream = AudioPiped(queued, HighQualityAudio())

            # --- Change the VC stream ---
            try:
                import time
                db[chat_id][0]["start_time"] = time.time()
                await client.change_stream(chat_id, stream)
            except Exception as e:
                LOGGER.error(f"change_stream failed: {e}")
                return

            # --- Notify WebApp (sync skip to web player) ---
            try:
                await notify_webapp(
                    chat_id,
                    current_song=db[chat_id][0],
                    queue=db[chat_id][1:6],
                    action="skip",
                    is_playing=True,
                )
            except Exception as e:
                LOGGER.warning(f"WebApp notify failed after change_stream: {e}")

            # --- Generate thumbnail for the new track ---
            duration_min = db[chat_id][0].get("dur", "0:00")
            try:
                thumb_path = await get_thumb(videoid, title, duration_min, user, chat_id)
                db[chat_id][0]["thumbnail_url"] = f"/thumbs/{os.path.basename(thumb_path)}"
            except Exception as e:
                LOGGER.error(f"Thumbnail generation error in change_stream: {e}")
                thumb_path = config.STREAM_IMG_URL

            # --- SEND NOW PLAYING MESSAGE TO TELEGRAM ---
            try:
                button = stream_markup(_, chat_id)
                msg_text = (
                    f"▷ **Now Playing**\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"✧ **Track:** `{title[:28]}`\n"
                    f"✧ **Duration:** `{duration_min}`\n"
                    f"✧ **By:** {user}"
                )
                
                if str(thumb_path).startswith("http"):
                    run = await app.send_message(
                        original_chat_id,
                        text=msg_text,
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                else:
                    run = await app.send_photo(
                        original_chat_id,
                        photo=thumb_path,
                        caption=msg_text,
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"
            except Exception as e:
                LOGGER.error(f"Failed to send Now Playing msg in change_stream: {e}")

    async def ping(self):
        pings = []
        if config.STRING1:
            pings.append(await self.one.ping)
        if config.STRING2:
            pings.append(await self.two.ping)
        if config.STRING3:
            pings.append(await self.three.ping)
        if config.STRING4:
            pings.append(await self.four.ping)
        if config.STRING5:
            pings.append(await self.five.ping)
        return str(round(sum(pings) / len(pings), 3))

    async def start(self):
        LOGGER.info("Starting PyTgCalls Client...\n")
        if config.STRING1:
            await self.one.start()
        if config.STRING2:
            await self.two.start()
        if config.STRING3:
            await self.three.start()
        if config.STRING4:
            await self.four.start()
        if config.STRING5:
            await self.five.start()

    async def decorators(self):
        @self.one.on_kicked()
        @self.two.on_kicked()
        @self.three.on_kicked()
        @self.four.on_kicked()
        @self.five.on_kicked()
        @self.one.on_closed_voice_chat()
        @self.two.on_closed_voice_chat()
        @self.three.on_closed_voice_chat()
        @self.four.on_closed_voice_chat()
        @self.five.on_closed_voice_chat()
        @self.one.on_left()
        @self.two.on_left()
        @self.three.on_left()
        @self.four.on_left()
        @self.five.on_left()
        async def stream_services_handler(_, chat_id: int):
            await self.stop_stream(chat_id)

        @self.one.on_stream_end()
        @self.two.on_stream_end()
        @self.three.on_stream_end()
        @self.four.on_stream_end()
        @self.five.on_stream_end()
        async def stream_end_handler1(client, update: Update):
            if not isinstance(update, StreamAudioEnded):
                return
            await self.change_stream(client, update.chat_id)


Nand = Call()
ani = Nand
