import asyncio
import os
import time
from datetime import datetime, timedelta
from typing import Union

from pyrogram import Client
from pyrogram.enums import ChatType, ChatMemberStatus
from pyrogram.errors import PeerIdInvalid, ChatWriteForbidden, UserNotParticipant
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
IS_V3 = False
IS_LEGACY = False

try:
    # --- Modern Era (v1, v2, v3) ---
    from pytgcalls import PyTgCalls, StreamType
    from pytgcalls.types.input_stream import AudioPiped, AudioVideoPiped
    from pytgcalls.types.input_stream.quality import HighQualityAudio, MediumQualityVideo
    from pytgcalls.types import Update
    try:
        from pytgcalls.types.stream import StreamAudioEnded, StreamVideoEnded, StreamDeleted
        IS_V3 = True
    except ImportError:
        # Fallback for earlier v1/v2
        class StreamAudioEnded: pass
        class StreamVideoEnded: pass
        class StreamDeleted: pass
except ImportError:
    # --- Legacy Era (v0.9.x) ---
    IS_LEGACY = True
    try:
        from pytgcalls import PyTgCalls
    except ImportError:
        try:
            from pytgcalls import GroupCallFactory as PyTgCalls
        except ImportError:
            LOGGER.critical("No PyTgCalls found. Please install it.")
            raise
    # Legacy dummies/shims
    class AudioPiped: 
        def __init__(self, p, **kwargs): self.path = p
    class AudioVideoPiped(AudioPiped): pass
    class HighQualityAudio: pass
    class MediumQualityVideo: pass
    class Update: pass
    class StreamAudioEnded: pass
    class StreamVideoEnded: pass
    class StreamDeleted: pass
    class StreamType:
        pulse_stream = "pulse"
        pulse = "pulse"

# Ensure all types are at least defined to prevent NameError
if "StreamAudioEnded" not in globals():
    class StreamAudioEnded: pass
if "StreamVideoEnded" not in globals():
    class StreamVideoEnded: pass
if "StreamDeleted" not in globals():
    class StreamDeleted: pass
if "Update" not in globals():
    class Update: pass
if "StreamType" not in globals():
    class StreamType:
        pulse_stream = "pulse"
        pulse = "pulse"

from pytgcalls.exceptions import (
    AlreadyJoinedError,
    NoActiveGroupCall,
    TelegramServerError,
)

# Implementation selection is now handled via PYTGCALLS_IMPLEMENTATION environment variable
# to maintain compatibility across different dev versions of pytgcalls.

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
        # We rely on defaults or PYTGCALLS_IMPLEMENTATION env var (set in vps_fix.sh)
        # The 'implementation' keyword is NOT supported in some pytgcalls 3.x builds.
        
        self.userbot1 = Client(
            name="Ass1",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING1),
            no_updates=True,
        )
        self.one = PyTgCalls(self.userbot1, cache_duration=100)
        
        self.userbot2 = Client(
            name="Ass2",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING2),
            no_updates=True,
        ) if config.STRING2 else None
        self.two = PyTgCalls(self.userbot2, cache_duration=100) if self.userbot2 else None
        
        self.userbot3 = Client(
            name="Ass3",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING3),
            no_updates=True,
        ) if config.STRING3 else None
        self.three = PyTgCalls(self.userbot3, cache_duration=100) if self.userbot3 else None
        
        self.userbot4 = Client(
            name="Ass4",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING4),
            no_updates=True,
        ) if config.STRING4 else None
        self.four = PyTgCalls(self.userbot4, cache_duration=100) if self.userbot4 else None
        
        self.userbot5 = Client(
            name="Ass5",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING5),
            no_updates=True,
        ) if config.STRING5 else None
        self.five = PyTgCalls(self.userbot5, cache_duration=100) if self.userbot5 else None
        self._locks = {}
        self._last_skip = {}
        self.dj_timer = {}
        # Clean mapping: PyTgCalls instance -> Pyrogram Client
        self._client_map = {
            id(self.one): self.userbot1,
            id(self.two): self.userbot2,
            id(self.three): self.userbot3,
            id(self.four): self.userbot4,
            id(self.five): self.userbot5,
        }

    def get_lock(self, chat_id: int):
        if chat_id not in self._locks:
            self._locks[chat_id] = asyncio.Lock()
        return self._locks[chat_id]

    def _get_userbot(self, assistant) -> Client:
        """Get the Pyrogram Client for a given PyTgCalls instance."""
        return self._client_map.get(id(assistant))

    async def _ensure_joined(self, chat_id: int, assistant) -> bool:
        """Ensure the assistant userbot is a member of the chat.
        Returns True if the assistant is confirmed in the chat.
        """
        userbot = self._get_userbot(assistant)
        if not userbot:
            LOGGER.error(f"[_ensure_joined] No userbot found for assistant")
            return False

        # Make sure we know our own ID
        if not userbot.me:
            try:
                await userbot.get_me()
            except Exception:
                try:
                    await userbot.start()
                    await userbot.get_me()
                except Exception as e:
                    LOGGER.error(f"[_ensure_joined] Cannot start userbot: {e}")
                    return False

        assistant_id = userbot.me.id
        LOGGER.info(f"[_ensure_joined] Checking Assistant {assistant_id} in chat {chat_id}")

        # Step 1: Check if already a member
        try:
            member = await app.get_chat_member(chat_id, assistant_id)
            if member.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
                LOGGER.info(f"[_ensure_joined] Assistant {assistant_id} already in chat {chat_id}")
                return True
            elif member.status == ChatMemberStatus.BANNED:
                LOGGER.warning(f"[_ensure_joined] Assistant {assistant_id} is BANNED in {chat_id}, unbanning...")
                try:
                    await app.unban_chat_member(chat_id, assistant_id)
                    await asyncio.sleep(1)
                except Exception as e:
                    LOGGER.error(f"[_ensure_joined] Unban failed: {e}")
                    return False
        except UserNotParticipant:
            LOGGER.info(f"[_ensure_joined] Assistant {assistant_id} not in chat {chat_id}, will join")
        except Exception as e:
            LOGGER.warning(f"[_ensure_joined] Membership check failed: {e}")

        # Step 2: Join via invite link
        try:
            chat = await app.get_chat(chat_id)
            invite_link = chat.invite_link
            if not invite_link:
                try:
                    invite_link = await app.export_chat_invite_link(chat_id)
                except Exception as e:
                    LOGGER.warning(f"[_ensure_joined] Cannot export invite link: {e}")
            if invite_link:
                LOGGER.info(f"[_ensure_joined] Joining via invite link...")
                await userbot.join_chat(invite_link)
                await asyncio.sleep(1)
                LOGGER.info(f"[_ensure_joined] Assistant {assistant_id} joined chat {chat_id} successfully")
                return True
            else:
                LOGGER.error(f"[_ensure_joined] No invite link available for {chat_id}")
        except Exception as e:
            err = str(e).lower()
            if "already" in err or "user_already_participant" in err:
                LOGGER.info(f"[_ensure_joined] Assistant already a participant (from join_chat)")
                return True
            LOGGER.error(f"[_ensure_joined] join_chat failed: {e}")

        # Step 3: Try adding directly via bot
        try:
            await app.add_chat_members(chat_id, assistant_id)
            await asyncio.sleep(1)
            LOGGER.info(f"[_ensure_joined] Added assistant via add_chat_members")
            return True
        except Exception as e:
            LOGGER.warning(f"[_ensure_joined] add_chat_members failed: {e}")

        # Final check: maybe one of the methods worked despite throwing
        try:
            member = await app.get_chat_member(chat_id, assistant_id)
            if member.status not in (ChatMemberStatus.BANNED, ChatMemberStatus.LEFT):
                return True
        except:
            pass

        LOGGER.error(f"[_ensure_joined] ALL methods failed for Assistant {assistant_id} in chat {chat_id}")
        return False

    async def _refresh_vc_state(self, userbot, chat_id: int):
        """Refresh the VC metadata cache so pytgcalls can see the active group call."""
        if not userbot:
            LOGGER.warning(f"[_refresh_vc_state] No userbot provided, skipping")
            return
        LOGGER.info(f"[_refresh_vc_state] Refreshing VC state for {chat_id}...")
        try:
            chat = await asyncio.wait_for(userbot.get_chat(chat_id), timeout=10)
            if chat.type in (ChatType.CHANNEL, ChatType.SUPERGROUP):
                from pyrogram.raw.functions.channels import GetFullChannel
                peer = await asyncio.wait_for(userbot.resolve_peer(chat_id), timeout=10)
                await asyncio.wait_for(userbot.invoke(GetFullChannel(channel=peer)), timeout=10)
            else:
                from pyrogram.raw.functions.messages import GetFullChat
                await asyncio.wait_for(userbot.invoke(GetFullChat(chat_id=chat_id)), timeout=10)
            LOGGER.info(f"[_refresh_vc_state] Done for {chat_id}")
        except asyncio.TimeoutError:
            LOGGER.warning(f"[_refresh_vc_state] Timed out for {chat_id}")
        except Exception as e:
            LOGGER.warning(f"[_refresh_vc_state] Failed for {chat_id}: {e}")

    async def pause_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        try:
            if not IS_LEGACY:
                await assistant.pause_stream(chat_id)
        except Exception as e:
            LOGGER.warning(f"PyTgCalls pause_stream failed (non-critical): {e}")
        try:
            current_song = db.get(chat_id, [{}])[0] if db.get(chat_id) else None
            queue = db.get(chat_id, [])[1:6] if db.get(chat_id) else []
            await notify_webapp(chat_id, current_song=current_song, queue=queue, is_playing=False, action="pause")
        except: pass

    async def resume_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        try:
            if not IS_LEGACY:
                await assistant.resume_stream(chat_id)
        except Exception as e:
            LOGGER.warning(f"PyTgCalls resume_stream failed (non-critical): {e}")
        try:
            current_song = db.get(chat_id, [{}])[0] if db.get(chat_id) else None
            queue = db.get(chat_id, [])[1:6] if db.get(chat_id) else []
            await notify_webapp(chat_id, current_song=current_song, queue=queue, is_playing=True, action="play")
        except: pass

    async def stop_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        try:
            await _clear_(chat_id)
            if IS_LEGACY:
                await assistant.leave(chat_id)
            else:
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
            try:
                await assistant.change_stream(chat_id, stream)
            except Exception as e:
                LOGGER.error(f"speedup_stream failed: {e}")
        else:
            raise AssistantErr("➲ **Cannot change speed, file mismatch.**")
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
        try:
            await assistant.change_stream(chat_id, stream)
            # Ensure ntgcalls pipeline restart safely
            try:
                await asyncio.sleep(0.5)
                await assistant.resume_stream(chat_id)
            except:
                pass
        except Exception as e:
            LOGGER.error(f"skip_stream failed: {e}")

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
        try:
            await assistant.change_stream(chat_id, stream)
            try:
                await asyncio.sleep(0.5)
                await assistant.resume_stream(chat_id)
            except:
                pass
        except Exception as e:
            LOGGER.error(f"seek_stream failed: {e}")

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
        **kwargs,
    ):
        assistant = await group_assistant(self, chat_id)
        language = await get_lang(chat_id)
        _ = get_string(language)

        payload = kwargs.get("payload") or {}
        af = payload.get("af", "")
        ff_params = f"-af {af}" if af else None

        if video:
            stream = AudioVideoPiped(
                link,
                audio_parameters=HighQualityAudio(),
                video_parameters=MediumQualityVideo(),
                additional_ffmpeg_parameters=ff_params
            )
        else:
            stream = AudioPiped(
                link,
                audio_parameters=HighQualityAudio(),
                additional_ffmpeg_parameters=ff_params
            )

        userbot = self._get_userbot(assistant)

        # --- Step 1: Ensure assistant is a MEMBER of the chat ---
        LOGGER.info(f"[join_call] Step 1: Ensuring Assistant membership for {chat_id}...")
        is_member = await asyncio.wait_for(self._ensure_joined(chat_id, assistant), timeout=30)
        LOGGER.info(f"[join_call] Step 1 complete. is_member={is_member}")
        
        if not is_member:
            LOGGER.error(f"[join_call] Assistant could not join chat {chat_id}. Raising error.")
            raise AssistantErr(
                "➲ **Assistant could not join the chat.**\n"
                "Please make sure:\n"
                "• The bot is admin with invite permissions\n"
                "• The assistant is not banned\n"
                "• The group allows adding members"
            )

        # --- Step 2: Refresh VC metadata cache ---
        LOGGER.info(f"[join_call] Step 2: Refreshing VC state for {chat_id}...")
        await self._refresh_vc_state(userbot, chat_id)

        # --- Step 3: Join the Voice Chat ---
        LOGGER.info(f"[join_call] Step 3: Attempting to join VC for {chat_id}...")
        joined = False
        last_err = None

        # 🔄 Clean slate attempt: Leave first to clear any ghost sessions
        try:
            LOGGER.info(f"[join_call] Pre-join: Attempting to leave ghost session for {chat_id}...")
            if IS_LEGACY:
                await assistant.leave(chat_id)
            else:
                await assistant.leave_group_call(chat_id)
            await asyncio.sleep(1)
        except:
            pass

        for attempt in range(3):
            try:
                if attempt > 0:
                    LOGGER.info(f"[join_call] Retry attempt {attempt} for {chat_id}...")
                    await self._refresh_vc_state(userbot, chat_id)
                    await asyncio.sleep(1.5)

                if IS_LEGACY:
                    LOGGER.info(f"[join_call] Legacy Mode: Joining via join() and start_audio() for {chat_id}...")
                    # 1. Join the chat
                    try:
                        await asyncio.wait_for(assistant.join(chat_id), timeout=20)
                    except AlreadyJoinedError:
                        pass
                    except Exception as e:
                        if "ALREADY_JOINED" in str(e): pass
                        else: raise e
                    
                    # 2. Start the audio stream
                    # In 0.9.x, link is usually the file path or a specific input stream
                    audio_path = link if isinstance(link, str) else getattr(stream, 'path', link)
                    await asyncio.wait_for(assistant.start_audio(audio_path), timeout=20)
                    LOGGER.info(f"[join_call] Legacy SUCCESS for {chat_id}")
                else:
                    LOGGER.info(f"[join_call] Executing join_group_call (attempt {attempt}) for {chat_id}...")
                    await asyncio.wait_for(
                        assistant.join_group_call(
                            chat_id,
                            stream,
                            stream_type=StreamType().pulse_stream,
                        ),
                        timeout=30
                    )
                joined = True
                LOGGER.info(f"[join_call] SUCCESS: Joined VC in {chat_id}")
                break
            except AlreadyJoinedError:
                LOGGER.info(f"[join_call] AlreadyJoinedError for {chat_id}, checking stream...")
                joined = True
                break
            except NoActiveGroupCall:
                last_err = "No active voice chat found. Please start a voice chat first."
                LOGGER.warning(f"[join_call] NoActiveGroupCall in {chat_id}")
                break
            except Exception as e:
                import traceback
                last_err = e
                err_name = type(e).__name__
                LOGGER.error(f"[join_call] Attempt {attempt} failed ({err_name}): {e}")
                if "join_group_call" in str(e) and IS_LEGACY:
                    LOGGER.warning("[join_call] Legacy assistant does not have join_group_call. Check detection.")
                await asyncio.sleep(1)

        if not joined:
            LOGGER.error(f"[join_call] Failed to join VC in {chat_id}. Error: {last_err}")
            try:
                webapp_url = f"{config.WEBAPP_URL}?room={chat_id}"
                btn = InlineKeyboardMarkup([[InlineKeyboardButton("🎧 Open Web Player", url=webapp_url)]])
                await app.send_message(
                    original_chat_id,
                    text=f"⚠️ **Could not join Voice Chat!**\n\n➲ **Reason:** `{str(last_err)[:100]}`\n➲ **Click below to listen via WebApp.**",
                    reply_markup=btn,
                )
            except Exception as e:
                LOGGER.error(f"Failed to send VC off warning: {e}")

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
            except:
                pass
        

    async def change_stream(self, client, chat_id, mention=None, skip_pop: bool = False):
        lock = self.get_lock(chat_id)
        async with lock:
            # 🩹 FIX: Anti-Double-Skip Logic
            # Prevents watchdog and on_stream_end events from skipping twice in < 2s
            now = time.time()
            if not skip_pop:
                if chat_id in self._last_skip:
                    if now - self._last_skip[chat_id] < 1.5:
                        LOGGER.info(f"[change_stream] Ignoring duplicate skip for {chat_id}")
                        return
                self._last_skip[chat_id] = now

            check = db.get(chat_id)
            if not check:
                # --- Smart Auto-DJ Hook ---
                from shakky.utils.database import is_autodj
                if await is_autodj(chat_id):
                    asyncio.create_task(self._autodj_next(chat_id))
                    return
                await _clear_(chat_id)
                try:
                    return await client.leave_group_call(chat_id)
                except:
                    return

            if not skip_pop:
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
                        # --- Smart Auto-DJ Hook ---
                        from shakky.utils.database import is_autodj
                        if await is_autodj(chat_id):
                            asyncio.create_task(self._autodj_next(chat_id))
                            return
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

            # --- Update Last Played Context for AI Recommendations ---
            from shakky.misc import last_played
            last_played[chat_id] = title
            
            streamtype = check[0]["streamtype"]
            videoid = check[0]["vidid"]
            
            is_intro = False
            # --- AI CO-HOST LOGIC ---
            from shakky.utils.database import is_cohost
            if await is_cohost(chat_id) and not check[0].get("cohost_played") and "live_" not in queued:
                from shakky.utils.cohost import generate_cohost_script, text_to_speech
                check[0]["cohost_played"] = True
                try:
                    script = await generate_cohost_script(title, user)
                    intro_file = await text_to_speech(script, chat_id)
                    if intro_file and os.path.exists(intro_file):
                        queued = intro_file
                        streamtype = "audio"
                        is_intro = True
                        LOGGER.info(f"Playing AI Co-Host intro for {chat_id}: {script}")
                except Exception as e:
                    LOGGER.error(f"Co-Host activation failed: {e}")

            if is_intro:
                if video:
                    stream = AudioVideoPiped(queued, HighQualityAudio(), MediumQualityVideo())
                else:
                    stream = AudioPiped(queued, HighQualityAudio())
                try:
                    await client.change_stream(chat_id, stream)
                    return
                except Exception as e:
                    LOGGER.error(f"Intro stream failed: {e}")
                    # If intro fails, continue to play the real song
            
            db[chat_id][0]["played"] = 0
            exis = (check[0]).get("old_dur")
            if exis:
                db[chat_id][0]["dur"] = exis
                db[chat_id][0]["seconds"] = check[0]["old_second"]
                db[chat_id][0]["speed_path"] = None
                db[chat_id][0]["speed"] = 1.0
            video = True if str(streamtype) == "video" else False

            # --- JIT Download for vid_ references (with 30s timeout) ---
            if "vid_" in queued:
                # Resolve Spotify tracks first if needed
                if "vid_sp_" in queued and not videoid:
                    try:
                        from shakky import YouTube as YT
                        # Clean title: remove hashtags and extra junk for better search accuracy
                        search_query = re.sub(r'#\w+', '', title).strip()
                        search_res = await YT.search(search_query or title)
                        if search_res:
                            videoid = search_res["vidid"]
                            db[chat_id][0]["vidid"] = videoid
                            db[chat_id][0]["dur"] = search_res["duration"]
                    except: pass


                if not os.path.exists(queued) and videoid:
                    try:
                        from shakky.platforms import YouTube as YT
                        file_path, direct = await asyncio.wait_for(
                            YT.download(videoid, video=video, raw_query=title),
                            timeout=60 # Increased timeout for VPS stability
                        )

                        if file_path and os.path.exists(file_path):
                            queued = file_path
                            db[chat_id][0]["file"] = file_path
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
                    except asyncio.TimeoutError:
                        LOGGER.error(f"JIT download timed out for {videoid}")
                        queued = None
                    except Exception as e:
                        LOGGER.error(f"Failed JIT Download in change_stream: {e}")
                        queued = None
                else:
                    queued = queued if os.path.exists(queued) else None

            elif "live_" in queued:
                n, link = await YouTube.video(videoid, True)
                if n == 0:
                    return await app.send_message(original_chat_id, text="Error fetching live stream.")
                queued = link

            # --- Build stream object ---
            if not queued:
                LOGGER.error(f"No valid file to stream for chat {chat_id} (Track: {title}). Skipping to next...")
                try:
                    # Notify user about failure
                    await app.send_message(original_chat_id, text=f"❌ **Failed to play:** `{title}`\n➲ **Skipping to next track...**")
                except:
                    pass
                
                # Check if we still have more songs in queue
                if len(db[chat_id]) > 0:
                    # Pop the track that just failed
                    db[chat_id].pop(0)
                    if len(db[chat_id]) > 0:
                        # Recursive call with skip_pop=True
                        # Add a small delay to prevent "Skipping Loop" from wiping the queue instantly
                        await asyncio.sleep(1.5)
                        return await self.change_stream(client, chat_id, skip_pop=True)

                
                # If we get here, no playable songs left
                await _clear_(chat_id)
                try: return await client.leave_group_call(chat_id)
                except: return

            if video:
                stream = AudioVideoPiped(queued, HighQualityAudio(), MediumQualityVideo())
            else:
                stream = AudioPiped(queued, HighQualityAudio())

            # --- Change the VC stream ---
            try:
                db[chat_id][0]["start_time"] = time.time()
                await client.change_stream(chat_id, stream)

                # --- Pro-DJ Mode Logic ---
                from shakky.utils.database import is_prodj
                
                # Cancel existing DJ timer
                if chat_id in self.dj_timer:
                    try:
                        self.dj_timer[chat_id].cancel()
                        del self.dj_timer[chat_id]
                    except: pass
                
                # Start new DJ timer if enabled
                if await is_prodj(chat_id):
                    async def dj_wait():
                        # 1. At 20 seconds, start pre-fetching the next vibe
                        await asyncio.sleep(20)
                        LOGGER.info(f"[Pro-DJ] Pre-fetching next vibe for {chat_id}...")
                        # Fire and forget the recommendation (adds to queue)
                        asyncio.create_task(self._autodj_next(chat_id, prefetch=True))
                        
                        # 2. At 40 seconds, perform the instant switch
                        await asyncio.sleep(20) 
                        LOGGER.info(f"[Pro-DJ] Performing instant transition in {chat_id}")
                        # Use the correct assistant client for the skip
                        assistant = await group_assistant(self, chat_id)
                        await self.change_stream(assistant, chat_id)
                    
                    self.dj_timer[chat_id] = asyncio.create_task(dj_wait())

            except Exception as e:
                import traceback
                err_msg = str(e)
                err_full = traceback.format_exc()
                LOGGER.error(f"change_stream failed for {chat_id}: {err_msg}")
                
                err_msg_lower = err_msg.lower()
                # Whitelist common VC-is-off errors to allow WebApp playback to continue
                if any(x in err_msg_lower for x in ["noactivegroupcall", "notincall", "call", "group call", "isn't in a"]):
                    LOGGER.warning(f"Ignoring change_stream error for WebApp playback: {err_msg}")
                    # Allow execution to continue for WebApp notifications, don't skip track.
                else:
                    # Log the FULL error for permanent fix diagnosis
                    with open("last_error.txt", "w", encoding="utf-8") as f:
                        from datetime import datetime
                        f.write(f"Timestamp: {datetime.now()}\nChat ID: {chat_id}\nTitle: {title}\nError: {err_msg}\n\nTraceback:\n{err_full}")
                    
                    try:
                        await app.send_message(original_chat_id, text=f"⚠️ **Streaming Error:** `{title}`\n**Reason:** `{err_msg[:100]}`\n➲ **Skipping to next track...**")
                    except:
                        pass
                    
                    if len(db[chat_id]) > 0:
                        # Pop failed track
                        db[chat_id].pop(0)
                        if len(db[chat_id]) > 0:
                            asyncio.create_task(self.change_stream(client, chat_id, skip_pop=True))
                            return
                    
                    await _clear_(chat_id)
                    try: return await client.leave_group_call(chat_id)
                    except: return

            # --- Fire-and-forget WebApp notification (non-blocking) ---
            asyncio.create_task(self._notify_webapp_safe(chat_id))

            # --- Generate thumbnail + send Now Playing (background) ---
            asyncio.create_task(
                self._send_now_playing(
                    chat_id, videoid, title, user, original_chat_id, _, mention
                )
            )

            # --- Pre-download next track in queue (background) ---
            asyncio.create_task(self._predownload_next(chat_id))

    async def _autodj_next(self, chat_id, prefetch: bool = False):
        """Find and play a related track when the queue is empty (Smart Auto-DJ)."""
        from shakky.misc import last_played
        from shakky.utils.stream.recommend_logic import start_ai_recommendation
        
        last_song = last_played.get(chat_id)
        if not last_song:
            # Fallback if no last_played context
            if not prefetch:
                try:
                    await app.send_message(chat_id, text="✨ **Smart Auto-DJ:** Queue is empty and no playback context found. Stopping.")
                except: pass
                return await self.stop_stream(chat_id)
            return
            
        try:
            # Re-use the existing AI recommendation logic
            # Passing prefetch as silent ensures it doesn't try to force-start if we just want to queue it
            await start_ai_recommendation(chat_id, user_name="Smart Auto-DJ", silent=prefetch)
        except Exception as e:
            if not prefetch:
                LOGGER.error(f"Auto-DJ failed for {chat_id}: {e}")
                await self.stop_stream(chat_id)

    async def _notify_webapp_safe(self, chat_id):
        """Fire-and-forget webapp notification."""
        try:
            await notify_webapp(
                chat_id,
                current_song=db[chat_id][0],
                queue=db[chat_id][1:6],
                action="skip",
                is_playing=True,
            )
        except Exception as e:
            LOGGER.warning(f"WebApp notify failed: {e}")
            
        # --- Stats Update for Wrapped ---
        try:
            from shakky.utils.database import update_stats
            u_id = db[chat_id][0].get("user_id")
            d_sec = db[chat_id][0].get("seconds", 0)
            if u_id:
                asyncio.create_task(update_stats(u_id, chat_id, videoid, title, d_sec))
        except:
            pass

    async def _send_now_playing(self, chat_id, videoid, title, user, original_chat_id, _, mention):
        """Generate thumbnail and send Now Playing message in background."""
        try:
            duration_min = db[chat_id][0].get("dur", "0:00")
            try:
                thumb_path = await get_thumb(videoid, title, duration_min, user, chat_id)
                db[chat_id][0]["thumbnail_url"] = f"/thumbs/{os.path.basename(thumb_path)}"
            except Exception as e:
                LOGGER.error(f"Thumbnail generation error: {e}")
                thumb_path = config.STREAM_IMG_URL

            button = stream_markup(_, chat_id)
            msg_text = (
                f"▷ **Now Playing**\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"✧ **Track:** `{title[:28]}`\n"
                f"✧ **Duration:** `{duration_min}`\n"
                f"✧ **By:** {user}"
            )
            if mention:
                msg_text += f"\n✧ **Skipped By:** {mention}"
            
            try:
                run = await app.send_photo(
                    original_chat_id,
                    photo=thumb_path,
                    caption=msg_text,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            except Exception as e:
                LOGGER.error(f"Thumbnail send failed in call.py, sending message instead: {e}")
                run = await app.send_message(
                    original_chat_id,
                    text=msg_text,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"
        except Exception as e:
            LOGGER.error(f"Failed to send Now Playing msg: {e}")

    async def _predownload_next(self, chat_id):
        """Pre-download the next track in queue so it's ready instantly."""
        try:
            check = db.get(chat_id)
            if not check or len(check) < 2:
                return
            next_track = check[1]
            next_file = next_track.get("file", "")
            next_vid = next_track.get("vidid", "")
            if "vid_" in next_file and not os.path.exists(next_file) and next_vid:
                from shakky.platforms import YouTube as YT
                LOGGER.info(f"Pre-downloading next track: {next_track.get('title', next_vid)}")
                file_path, _ = await asyncio.wait_for(
                    YT.download(next_vid, raw_query=next_track.get("title")),
                    timeout=45
                )
                if file_path and os.path.exists(file_path):
                    next_track["file"] = file_path
                    LOGGER.info(f"Pre-download complete: {file_path}")
        except asyncio.TimeoutError:
            LOGGER.warning(f"Pre-download timed out for chat {chat_id}")
        except Exception as e:
            LOGGER.debug(f"Pre-download failed (non-critical): {e}")

    async def apply_audio_filter(self, chat_id: int, filter_key, playing):
        """Apply a spatial audio filter to the current stream, or reset to original.

        Args:
            chat_id: The chat to apply the filter in.
            filter_key: One of 'bass_boost', '8d_audio', 'nightcore', 'slowed_reverb', or None to reset.
            playing: The current db[chat_id] list.
        """
        from shakky.plugins.admins.filters import AUDIO_FILTERS

        assistant = await group_assistant(self, chat_id)
        current = playing[0]

        # Resolve the *original* file path (before any speed/filter modifications)
        original_file = current.get("original_file") or current.get("file")
        if not original_file or not os.path.exists(original_file):
            raise AssistantErr("➲ **Cannot apply filter — original file not found.**")

        # Store the original file reference if not already saved
        if not current.get("original_file"):
            db[chat_id][0]["original_file"] = original_file

        # Calculate current playback position
        start_time = current.get("start_time", time.time())
        played_seconds = int(time.time() - start_time)
        total_seconds = current.get("seconds", 0)
        if played_seconds < 0:
            played_seconds = 0
        if total_seconds > 0 and played_seconds > total_seconds:
            played_seconds = total_seconds

        if filter_key is None:
            # Reset to original
            out = original_file
            db[chat_id][0]["active_filter"] = None
        else:
            if filter_key not in AUDIO_FILTERS:
                raise AssistantErr("➲ **Unknown filter.**")

            ffmpeg_filter = AUDIO_FILTERS[filter_key]["ffmpeg"]

            # Build cached output path: playback/filters/<filter_key>/<filename>
            base = os.path.basename(original_file)
            filter_dir = os.path.join(os.getcwd(), "playback", "filters", filter_key)
            if not os.path.isdir(filter_dir):
                os.makedirs(filter_dir)
            out = os.path.join(filter_dir, base)

            if not os.path.isfile(out):
                LOGGER.info(f"[filter] Rendering {filter_key} for {base}...")
                proc = await asyncio.create_subprocess_shell(
                    cmd=(
                        f'ffmpeg -y -i "{original_file}" '
                        f'-af "{ffmpeg_filter}" '
                        f'-c:v copy '
                        f'"{out}"'
                    ),
                    stdin=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
                if proc.returncode != 0:
                    LOGGER.error(f"[filter] FFmpeg error: {stderr.decode()[:300]}")
                    raise AssistantErr("➲ **FFmpeg failed to process filter.**")
                LOGGER.info(f"[filter] Rendered: {out}")

            db[chat_id][0]["active_filter"] = filter_key

        # Recalculate duration of filtered file
        dur = await asyncio.get_event_loop().run_in_executor(None, check_duration, out)
        dur = int(dur)
        duration_str = seconds_to_min(dur)

        # Build the new stream object, seeking to current position
        streamtype = current.get("streamtype", "audio")
        if streamtype == "video":
            stream = AudioVideoPiped(
                out,
                audio_parameters=HighQualityAudio(),
                video_parameters=MediumQualityVideo(),
                additional_ffmpeg_parameters=f"-ss {played_seconds} -to {duration_str}",
            )
        else:
            stream = AudioPiped(
                out,
                audio_parameters=HighQualityAudio(),
                additional_ffmpeg_parameters=f"-ss {played_seconds} -to {duration_str}",
            )

        try:
            await assistant.change_stream(chat_id, stream)
        except Exception as e:
            LOGGER.error(f"[filter] change_stream failed: {e}")
            raise AssistantErr(f"➲ **Failed to swap stream:** `{e}`")

        # Update db metadata to reflect filtered playback
        db[chat_id][0]["file"] = out
        db[chat_id][0]["start_time"] = time.time() - played_seconds
        db[chat_id][0]["seconds"] = dur
        db[chat_id][0]["dur"] = duration_str

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

    async def stop(self):
        LOGGER.info("Stopping PyTgCalls Clients...")
        try:
            for ass in [self.one, self.two, self.three, self.four, self.five]:
                if not ass: continue
                if IS_LEGACY:
                    # In legacy, you might need to call leave_all or just stop
                    try: await ass.stop()
                    except: pass
                else:
                    await ass.stop()
            LOGGER.info("PyTgCalls Clients stopped.")
        except Exception as e:
            LOGGER.warning(f"Error while stopping PyTgCalls: {e}")

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
        # Helper to safely register decorators
        def register_handler(client, event_name, handler):
            if not client: return
            try:
                method = getattr(client, event_name, None)
                if method:
                    method()(handler)
                else:
                    LOGGER.debug(f"[decorators] {event_name} not supported by this pytgcalls version.")
            except Exception as e:
                LOGGER.warning(f"[decorators] Failed to register {event_name}: {e}")

        async def stream_services_handler(_, chat_id: int):
            await self.stop_stream(chat_id)

        # Register service handlers
        for ass in [self.one, self.two, self.three, self.four, self.five]:
            if not ass: continue
            register_handler(ass, "on_kicked", stream_services_handler)
            register_handler(ass, "on_closed_voice_chat", stream_services_handler)
            register_handler(ass, "on_left", stream_services_handler)

        async def stream_end_handler1(client, update: Update):
            update_type = type(update).__name__
            chat_id = getattr(update, 'chat_id', None)
            LOGGER.info(f"[on_stream_end] Received update type={update_type} chat={chat_id}")

            if not chat_id:
                return

            # Check for end of stream
            is_end = False
            if IS_V3:
                if isinstance(update, (StreamAudioEnded, StreamVideoEnded, StreamDeleted)):
                    is_end = True
            else:
                # In legacy versions, we might need to check update properties or specific classes
                if update_type in ["StreamAudioEnded", "StreamVideoEnded", "StreamDeleted"]:
                    is_end = True
            
            if not is_end:
                return

            LOGGER.info(f"[on_stream_end] Processing stream end for chat {chat_id}")
            try:
                asyncio.create_task(self.change_stream(client, chat_id))
            except Exception as e:
                LOGGER.error(f"[on_stream_end] change_stream failed: {e}")
                await self.stop_stream(chat_id)

        # Register stream end handlers
        for ass in [self.one, self.two, self.three, self.four, self.five]:
            if not ass: continue
            register_handler(ass, "on_stream_end", stream_end_handler1)



Nand = Call()
ani = Nand
