from pyrogram import filters
from pyrogram.types import Message
from pyrogram.errors import PeerIdInvalid, FloodWait
from shakky import app, YouTube
import config
import asyncio
import time
import random
import re
import logging

logger = logging.getLogger(__name__)

# Use the same group settings as in the YouTube platform
GROUP_USERNAME = getattr(config, "GROUP_USERNAME", "shadowmusicbase")

@app.on_message(filters.command(["find", "get"], prefixes=["/", "", "!", "."]))
async def find_song(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("➲ **Please provide a song name to find.**\n\n**Example:** `find tum hi ho`")

    query = message.text.split(None, 1)[1].strip()
    mystic = await message.reply_text(f"➲ **Searching for** `{query}` **in the database...**")

    # Access the assistant (app for API calls)
    assistant = YouTube._youmusic_app
    if not assistant:
        return await mystic.edit_text("➲ **Assistant not ready. Refreshing...**")

    # 1. SEARCH LOCAL DATABASE FIRST (Super Fast)
    try:
        db_channel = getattr(config, "CHANNEL_USERNAME", "@smashmusicdb")
        async for db_msg in assistant.search_messages(db_channel, query=query, limit=1):
            if db_msg.audio or db_msg.document:
                return await send_file_to_user(message, db_msg, query, mystic)
    except Exception as e:
        logger.error(f"Local DB search failed: {e}")

    try:
        # 2. EXTERNAL SEARCH VIA @shadowmusicbase
        await mystic.edit_text(f"➲ **Searching in External DB...**")
        
        # Send search command
        sent_msg = await assistant.send_message(GROUP_USERNAME, f"find {query}")
        
        start_time = time.time()
        timeout = 35 # Reduced timeout for snappy feel
        audio_msg = None
        
        # Super fast polling loop
        while time.time() - start_time < timeout:
            try:
                # Check very few recent messages for maximum speed
                async for res_msg in assistant.get_chat_history(GROUP_USERNAME, limit=12):
                    if res_msg.id <= sent_msg.id:
                        continue
                    
                    # Target: Any audio response
                    is_audio = res_msg.audio or (res_msg.document and res_msg.document.mime_type and res_msg.document.mime_type.startswith('audio/'))
                    
                    if is_audio:
                        # Success detection: check reply or recent timing
                        is_reply = (res_msg.reply_to_message and res_msg.reply_to_message.id == sent_msg.id)
                        time_diff = (res_msg.date - sent_msg.date).total_seconds()
                        
                        # If it's a reply or arrived within 30s of our request
                        if is_reply or (0 < time_diff < 30):
                            audio_msg = res_msg
                            break
                
                if audio_msg:
                    break
            except:
                pass
            
            await asyncio.sleep(0.7) # SUPER FAST polling

        if audio_msg:
            # BRIDGE FORWARDING (No download to disk)
            db_channel = getattr(config, "CHANNEL_USERNAME", "@smashmusicdb")
            
            try:
                # Direct forward to bridge to let main bot 'see' it
                bridge_msg = await audio_msg.forward(db_channel)
                
                # Main Bot (app) takes over and copies with new caption to the user
                # This ensures the Bot account is the sender
                await send_file_by_bot(message, bridge_msg.id, db_channel, query, mystic)
                
                # Cleanup
                try:
                    await asyncio.gather(
                        assistant.delete_messages(db_channel, [bridge_msg.id]),
                        assistant.delete_messages(GROUP_USERNAME, [sent_msg.id])
                    )
                except:
                    pass
            except Exception as e:
                logger.error(f"Forward bridge failed: {e}")
                # Fallback to direct assistant copy if bridge fails
                await send_file_to_user(message, audio_msg, query, mystic)
        else:
            await mystic.edit_text("➲ **Could not find any file for** `{query}`.")

    except Exception as e:
        await mystic.edit_text(f"➲ **Error finding song:** `{str(e)}`")

async def send_file_by_bot(original_message, message_id, channel_id, query, mystic):
    """Bridge pickup: Main bot copies media to user with custom caption"""
    try:
        file_msg = await app.get_messages(channel_id, message_ids=message_id)
        if not file_msg or not (file_msg.audio or file_msg.document):
            raise Exception("File message not found by bot")

        title = (file_msg.audio.file_name if file_msg.audio else file_msg.document.file_name) or query.title()
        if "." in title: title = title.rsplit(".", 1)[0]
        title = title.replace("_", " ").title()

        bot_username = getattr(config, "BOT_USERNAME", "@Smash_MusicBot").replace("@", "")
        caption = f"➲ **{title}**\n\n✨ **Downloaded By :** @{bot_username}\n🌷"

        # COPY = Direct transfer with caption change (Telegram side)
        await file_msg.copy(
            chat_id=original_message.chat.id,
            caption=caption,
            reply_to_message_id=original_message.id
        )
        await mystic.delete()
    except Exception as e:
        logger.error(f"Bot delivery failed: {e}")
        raise e

async def send_file_to_user(original_message, file_message, query, mystic):
    """Direct Assistant Delivery Fallback"""
    try:
        assistant = file_message._client
        try: await assistant.get_chat(original_message.chat.id)
        except: pass
        
        title = (file_message.audio.file_name if file_message.audio else file_message.document.file_name) or query.title()
        if "." in title: title = title.rsplit(".", 1)[0]
        title = title.replace("_", " ").title()

        bot_username = getattr(config, "BOT_USERNAME", "@Smash_MusicBot").replace("@", "")
        caption = f"➲ **{title}**\n\n✨ **Downloaded By :** @{bot_username}\n🌷"

        await file_message.copy(
            chat_id=original_message.chat.id,
            caption=caption,
            reply_to_message_id=original_message.id
        )
        await mystic.delete()
    except Exception as e:
        await mystic.edit_text(f"➲ **Failed to deliver file:** `{e}`")
