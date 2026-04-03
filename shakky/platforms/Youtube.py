import asyncio
import os
import re
import json
import random
import shutil
import hashlib
import fnmatch
import time
import logging
from typing import Union, Optional, Dict, List, Tuple
from datetime import datetime, timedelta

import aiohttp
import yt_dlp
from pyrogram import Client, filters
from pyrogram.enums import MessageEntityType, MessagesFilter
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from youtubesearchpython.__future__ import VideosSearch
from shakky.utils.groq import get_enhanced_metadata

import config
from shakky.utils.formatters import seconds_to_min

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API URLs
API_URL = getattr(config, "API_URL", "")
VIDEO_API_URL = getattr(config, "VIDEO_API_URL", "")
API_KEY = getattr(config, "API_KEY", "")

# Telegram settings
CHANNEL_USERNAME = getattr(config, "CHANNEL_USERNAME", "@smashmusicdb")
GROUP_USERNAME = getattr(config, "GROUP_USERNAME", "shadowmusicbase")
SESSION_STRING = getattr(config, "SESSION_STRING", os.environ.get("SESSION_STRING"))
YOU_MUSIC_SESSION = getattr(config, "YOU_MUSIC_SESSION", os.environ.get("YOU_MUSIC_SESSION"))

# Owner ID for /addsong command
OWNER_ID = getattr(config, "OWNER_ID", None)

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.download_folder = "downloads"
        self.cache_file = "song_cache.json"
        self.keyword_cache_file = "keyword_cache.json"
        self.cache = {}
        self.keyword_cache = {}  # New cache for keyword-based songs
        self._cleanup_task = None
        self._app = None
        self._youmusic_app = None
        self._initialized = False
        self._channel_id = None
        
        # --- Performance: Concurrency Controls ---
        self._download_semaphore = asyncio.Semaphore(10)  # Max 10 concurrent downloads
        self._search_semaphore = asyncio.Semaphore(15)    # Max 15 concurrent searches
        self._inflight_downloads = {}  # video_id -> asyncio.Lock (dedup)
        self._inflight_lock = asyncio.Lock()  # Protects _inflight_downloads dict
        
        # Ensure directories exist
        os.makedirs(self.download_folder, exist_ok=True)
    
    async def initialize(self):
        """Initialize the API asynchronously"""
        if self._initialized:
            return True
            
        try:
            # Load caches
            self.cache = self._load_cache(self.cache_file)
            self.keyword_cache = self._load_cache(self.keyword_cache_file)
            
            # Start cleanup scheduler
            self._cleanup_task = asyncio.create_task(self._cleanup_scheduler())
            
            # Initialize Telegram clients
            await self._init_telegram_clients()
            
            self._initialized = True
            logger.info("YouTube API initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize YouTube API: {e}")
            return False
    
    async def _init_telegram_clients(self):
        """Initialize Telegram clients"""
        # Main app
        if SESSION_STRING:
            try:
                api_id = getattr(config, "API_ID", None)
                api_hash = getattr(config, "API_HASH", "")
                
                if api_id and api_hash:
                    self._app = Client(
                        "youtube_api_client",
                        session_string=SESSION_STRING,
                        api_id=api_id,
                        api_hash=api_hash,
                        in_memory=True,
                        no_updates=True
                    )
                    await self._app.start()
                    logger.info("Main Pyrogram client started")
                    
                    # Get channel ID if username is provided
                    if CHANNEL_USERNAME:
                        await self._get_channel_info()
                    
                    # Add message handler for /addsong command
                    self._setup_handlers()
            except Exception as e:
                logger.error(f"Failed to start main Pyrogram app: {e}")
        
        # YouMusicRobot app
        if YOU_MUSIC_SESSION:
            try:
                api_id = getattr(config, "API_ID", None)
                api_hash = getattr(config, "API_HASH", "")
                
                if api_id and api_hash:
                    self._youmusic_app = Client(
                        "you_music_bot",
                        session_string=YOU_MUSIC_SESSION,
                        api_id=api_id,
                        api_hash=api_hash,
                        in_memory=True,
                        no_updates=True
                    )
                    await self._youmusic_app.start()
                    logger.info("YouMusicRobot client started")
            except Exception as e:
                logger.error(f"Failed to start YouMusicRobot app: {e}")
    
    def _setup_handlers(self):
        """Setup message handlers for commands"""
        @self._app.on_message(filters.command("addsong") & filters.private)
        async def addsong_handler(client, message: Message):
            """Handle /addsong command from owner"""
            # Check if user is owner
            if not OWNER_ID or message.from_user.id != OWNER_ID:
                await message.reply_text("⚠️ This command is only for bot owner.")
                return
            
            # Check if replying to a file
            if not message.reply_to_message or not (
                message.reply_to_message.audio or 
                message.reply_to_message.document or
                message.reply_to_message.video
            ):
                await message.reply_text(
                    "⚠️ Please reply to an audio/document/video file with the command.\n"
                    "Usage: `/addsong keyword` (reply to file)",
                    parse_mode="markdown"
                )
                return
            
            # Get keyword from command
            if len(message.command) < 2:
                await message.reply_text(
                    "⚠️ Please provide a keyword.\n"
                    "Usage: `/addsong keyword` (reply to file)",
                    parse_mode="markdown"
                )
                return
            
            keyword = message.text.split(None, 1)[1].lower().strip()
            
            # Validate keyword
            if not keyword or len(keyword) < 2:
                await message.reply_text("❌ Keyword must be at least 2 characters long.")
                return
            
            if not re.match(r'^[a-z0-9_\- ]+$', keyword, re.IGNORECASE):
                await message.reply_text(
                    "❌ Keyword can only contain letters, numbers, spaces, hyphens, and underscores."
                )
                return
            
            # Upload to channel
            result = await self._add_song_to_channel(
                keyword=keyword,
                reply_message=message.reply_to_message
            )
            
            await message.reply_text(result)
    
    async def _add_song_to_channel(self, keyword: str, reply_message: Message) -> str:
        """Add a song to channel with keyword"""
        try:
            # Check if keyword already exists
            if keyword in self.keyword_cache:
                # Check if we want to overwrite
                return f"⚠️ Keyword '{keyword}' already exists. Use a different keyword."
            
            # Upload to channel
            chat_id = self._channel_id if self._channel_id else CHANNEL_USERNAME
            
            # Prepare caption
            caption = f"Keyword: #{keyword}\n\nAdded via /addsong command"
            
            # Send the file to channel
            if reply_message.audio:
                msg = await self._app.send_audio(
                    chat_id=chat_id,
                    audio=reply_message.audio.file_id,
                    caption=caption
                )
                file_type = "audio"
                file_name = reply_message.audio.file_name or f"audio_{int(time.time())}.mp3"
                
            elif reply_message.document:
                msg = await self._app.send_document(
                    chat_id=chat_id,
                    document=reply_message.document.file_id,
                    caption=caption
                )
                file_type = "document"
                file_name = reply_message.document.file_name or f"document_{int(time.time())}"
                
            elif reply_message.video:
                msg = await self._app.send_video(
                    chat_id=chat_id,
                    video=reply_message.video.file_id,
                    caption=caption
                )
                file_type = "video"
                file_name = reply_message.video.file_name or f"video_{int(time.time())}.mp4"
                
            else:
                return "❌ Unsupported file type. Only audio, document, and video files are supported."
            
            # Update caption with ID to "look like others"
            try:
                final_caption = f"Keyword: #{keyword}\n\nAdded via /addsong command\n\nID: db_{msg.id}"
                await self._app.edit_message_caption(
                    chat_id=chat_id,
                    message_id=msg.id,
                    caption=final_caption
                )
            except Exception as e:
                logger.error(f"Failed to update caption with ID: {e}")
            
            # Save to keyword cache
            self.keyword_cache[keyword] = {
                'message_id': msg.id,
                'channel_id': chat_id,
                'timestamp': time.time(),
                'file_type': file_type,
                'file_name': file_name,
                'added_by': reply_message.from_user.id if reply_message.from_user else OWNER_ID
            }
            
            # Save cache
            self._save_cache(self.keyword_cache_file, self.keyword_cache)
            
            logger.info(f"Added song with keyword '{keyword}' (message_id: {msg.id})")
            
            return f"✅ Successfully added song with keyword: `{keyword}`\n\n📁 File: {file_name}\n📍 Channel: {CHANNEL_USERNAME}\n📎 Message ID: {msg.id}"
            
        except Exception as e:
            logger.error(f"Error adding song to channel: {e}")
            return f"❌ Error adding song: {str(e)}"
    
    async def _get_song_by_keyword(self, keyword: str) -> Optional[Message]:
        """Get song by keyword from channel"""
        if not self._app:
            logger.debug("Client not initialized, trying to initialize...")
            await self.initialize()
            if not self._app:
                return None
            
        keyword = keyword.lower().strip()
        
        # Check cache first
        if keyword in self.keyword_cache:
            cache_info = self.keyword_cache[keyword]
            try:
                channel_id = cache_info.get('channel_id', CHANNEL_USERNAME)
                message = await self._app.get_messages(
                    channel_id,
                    cache_info['message_id']
                )
                if message and (message.audio or message.document or message.video):
                    logger.info(f"Found in keyword cache: {keyword}")
                    return message
            except Exception as e:
                logger.debug(f"Keyword cache entry invalid: {e}")
                # Remove invalid cache entry
                self.keyword_cache.pop(keyword, None)
                self._save_cache(self.keyword_cache_file, self.keyword_cache)
        
        # Search in channel if not in cache (DEBUG LOGS ONLY)
        try:
            # Robust identifier for the channel (ID first, then Username)
            search_id = self._channel_id if self._channel_id else CHANNEL_USERNAME
            
            # 1. Search with hashtag (Priority)
            async for message in self._app.search_messages(
                chat_id=search_id,
                query=f"#{keyword}",
                limit=1
            ):
                if message and (message.audio or message.document or message.video):
                    msg = message
                    break
            else:
                # 2. Search without hashtag if not found (Fallback)
                async for message in self._app.search_messages(
                    chat_id=search_id,
                    query=keyword,
                    limit=1
                ):
                    if message and (message.audio or message.document or message.video):
                        msg = message
                        break
                else:
                    return None

            # Cache found message
            file_type = "audio" if msg.audio else ("document" if msg.document else "video")
            file_name = (msg.audio.file_name if msg.audio else (msg.document.file_name if msg.document else msg.video.file_name)) or "Unknown"
            
            self.keyword_cache[keyword] = {
                'message_id': msg.id,
                'channel_id': search_id if isinstance(search_id, int) else None,
                'timestamp': time.time(),
                'file_type': file_type,
                'file_name': file_name
            }
            self._save_cache(self.keyword_cache_file, self.keyword_cache)
            return msg

        except Exception as e:
            # Handle Peer ID Invalid automatically
            if "peer_id_invalid" in str(e).lower() or "PEER_ID_INVALID" in str(e):
                try:
                    # Final attempt using username only
                    async for message in self._app.search_messages(
                        chat_id=CHANNEL_USERNAME,
                        query=keyword,
                        limit=1
                    ):
                        if message and (message.audio or message.document or message.video):
                            return message
                except:
                    pass
            logger.debug(f"Error searching for keyword '{keyword}': {e}")
        
        return None
    
    async def _search_smash_db(self, query: str) -> Optional[Message]:
        """Search @smashmusicdb channel for audio matching query with high accuracy (2A)"""
        if not self._app or not CHANNEL_USERNAME:
            return None
            
        try:
            query = query.lower().strip()
            # 1. Clean query for better matching
            clean_query = re.sub(r'[^\w\s]', '', query)
            keywords = [w for w in clean_query.split() if len(w) >= 2]
            
            if not keywords:
                keywords = [query]
                
            search_id = self._channel_id if self._channel_id else CHANNEL_USERNAME
            
            # Step 1: Search for the full query string first (Highest Accuracy)
            async for message in self._app.search_messages(
                chat_id=search_id,
                query=query,
                filter=MessagesFilter.AUDIO,
                limit=5
            ):
                if message.caption and query in message.caption.lower():
                    logger.info(f"Exact match found in @smashmusicdb: {message.id}")
                    return message
            
            # Step 2: Multi-keyword matching if exact match fails
            best_match = None
            max_keywords_found = 0
            
            # Use the longest keyword for the initial Telegram search to narrow down results
            lookup_kw = max(keywords, key=len)
            logger.info(f"Searching @smashmusicdb for best match using: {lookup_kw}")
            
            async for message in self._app.search_messages(
                chat_id=search_id,
                query=lookup_kw,
                filter=MessagesFilter.AUDIO,
                limit=20
            ):
                content_to_check = (message.caption or "").lower()
                if message.audio and message.audio.file_name:
                    content_to_check += " " + message.audio.file_name.lower()
                
                # Count how many query keywords are present in this result
                found_count = sum(1 for kw in keywords if kw in content_to_check)
                
                # If all keywords are found, it's a very strong match
                if found_count == len(keywords):
                    logger.info(f"Highly accurate match found in @smashmusicdb: {message.id}")
                    return message
                
                # Otherwise, keep track of the one with the most keyword matches
                if found_count > max_keywords_found:
                    max_keywords_found = found_count
                    best_match = message
            
            # Only return the best match if it contains a significant amount of the query (e.g., > 50%)
            if best_match and max_keywords_found >= (len(keywords) / 2):
                logger.info(f"Best fuzzy match found in @smashmusicdb: {best_match.id} ({max_keywords_found}/{len(keywords)} keywords)")
                return best_match
                
            return None
        except Exception as e:
            logger.error(f"Error in _search_smash_db: {e}")
            return None

    async def _fetch_via_youmusicbot(self, query: str, title: str = None) -> Optional[str]:
        """Request audio via @YouMusicRobot in @shadowmusicbase (2B)"""
        if not self._youmusic_app:
            logger.warning("YouMusicRobot app not available")
            return None
            
        try:
            # 1. Send find request
            logger.info(f"Sending 'find {query}' to @shadowmusicbase...")
            sent_msg = await self._youmusic_app.send_message(GROUP_USERNAME, f"find {query}")
            
            # 2. Wait and poll for reply (60s timeout, 2s check)
            audio_msg = None
            timeout = 60
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                async for msg in self._youmusic_app.get_chat_history(GROUP_USERNAME, limit=3):
                    # Check if it's a direct reply using the safe native ID
                    is_reply = (msg.reply_to_message_id == sent_msg.id)
                    
                    # Or check if it's a bot message with audio that contains our title keywords
                    is_audio = msg.audio or (msg.document and msg.document.mime_type and msg.document.mime_type.startswith('audio/'))
                    
                    if is_audio:
                        from_bot = (msg.from_user and msg.from_user.is_bot) or msg.via_bot
                        
                        if is_reply:
                            audio_msg = msg
                            logger.info(f"Caught DIRECT audio reply for: {query}")
                            break
                        elif from_bot:
                            # Verify content match
                            import re
                            title_meta = (msg.audio.title or "") if msg.audio else ""
                            perf_meta = (msg.audio.performer or "") if msg.audio else ""
                            filename = (msg.audio.file_name if msg.audio else (msg.document.file_name if msg.document else "")) or ""
                            
                            full_content = f"{title_meta} {perf_meta} {filename}".lower()
                            query_words = [re.sub(r'[^\w]', '', w).lower() for w in query.split() if len(w) > 2]
                            query_words = [w for w in query_words if w]
                            
                            if query_words:
                                match_count = sum(1 for w in query_words if w in full_content)
                                if match_count >= min(2, len(query_words)):
                                    logger.info(f"Caught matching bot audio via fuzzy text! ({match_count} matches)")
                                    audio_msg = msg
                                    break
                if audio_msg:
                    break
                    
                await asyncio.sleep(1.5) # Prevent FloodWait locks
            if not audio_msg:
                logger.error(f"Timeout waiting for @YouMusicRobot reply for: {query}")
                return None
                
            # 3. Download audio
            # Extract video ID for naming
            vidid = self._get_video_id(query) or f"ym_{int(time.time())}"
            file_path = await self._download_audio_file(self._youmusic_app, audio_msg, vidid)
            
            # 4. Delete request and reply
            try:
                await self._youmusic_app.delete_messages(GROUP_USERNAME, [sent_msg.id, audio_msg.id])
            except:
                pass
                
            # 5. Upload to @smashmusicdb with specialized caption
            final_title = title or query
            # Sanitize for keyword
            sanitized_kw = "".join(e for e in final_title if e.isalnum() or e == " ").strip().replace(" ", "_").lower()
            caption = f"{final_title} | #{sanitized_kw}\n\nID: {vidid}"
            
            # Use assistant account to upload if possible
            if self._app:
                try:
                    chat_id = self._channel_id if self._channel_id else CHANNEL_USERNAME
                    # Add file_name and title for better UX
                    await self._app.send_audio(
                        chat_id=chat_id,
                        audio=file_path,
                        caption=caption,
                        title=final_title,
                        performer="Smash Music"
                    )
                    logger.info(f"Uploaded new song to cache channel: {final_title}")
                except Exception as ex:
                    logger.warning(f"Failed to upload to cache channel: {ex}")
                    
            return file_path
            
        except Exception as e:
            logger.error(f"Error in _fetch_via_youmusicbot: {e}")
            return None

    async def search(self, query: str):
        """Search YouTube for a query and return metadata with high precision (STEP 1)"""
        try:
            # 1. Enhance query for music if not already present
            search_query = query
            if not any(k in query.lower() for k in ["music", "official", "lyrics", "audio", "video"]):
                search_query = f"{query} music"

            # 2. Fetch multiple candidates (with concurrency control)
            async with self._search_semaphore:
                results = VideosSearch(search_query, limit=5)
                search_result = await results.next()
            
            if search_result.get("result"):
                candidates = search_result["result"]
                
                # 3. Filter and Score Candidates
                best_candidate = None
                max_score = -1
                
                # Keywords that boost score
                boost_words = ["official", "lyrics", "audio", "original", "vevo", "music video"]
                penalty_words = ["karaoke", "instrumental", "cover", "remix", "tiktok", "shorts"]

                for can in candidates:
                    title = can.get("title", "").lower()
                    duration_str = can.get("duration", "0:00")
                    
                    # Convert duration to seconds for filtering
                    try:
                        parts = list(map(int, duration_str.split(':')))
                        dur_sec = 0
                        for i, p in enumerate(reversed(parts)):
                            dur_sec += p * (60 ** i)
                    except: dur_sec = 0
                    
                    # Skip extremely short clips (likely not full songs) if dur_sec < 60 and dur_sec > 0:
                    if 0 < dur_sec < 45: continue
                    
                    # Score based on keyword presence
                    score = 0
                    for word in boost_words:
                        if word in title: score += 10
                    for word in penalty_words:
                        if word in title: score -= 15
                    
                    # Exact word matching boost
                    query_words = set(re.sub(r'[^\w\s]', '', query.lower()).split())
                    title_words = set(re.sub(r'[^\w\s]', '', title).split())
                    shared_words = query_words.intersection(title_words)
                    score += len(shared_words) * 5

                    if score > max_score:
                        max_score = score
                        best_candidate = can
                
                # Fallback to first if all rejected
                if not best_candidate:
                    best_candidate = candidates[0]

                thumbnail = best_candidate['thumbnails'][0]['url'] if best_candidate.get('thumbnails') else config.STREAM_IMG_URL
                
                duration = "0:00"
                if best_candidate.get("duration"):
                    duration = best_candidate["duration"]
                elif best_candidate.get("durationString"):
                    duration = best_candidate["durationString"]
                
                logger.info(f"High-precision search found: {best_candidate.get('title')} (Score: {max_score})")

                return {
                    "title": best_candidate.get("title", query),
                    "duration": duration,
                    "vidid": best_candidate.get("id"),
                    "thumbnail_url": thumbnail
                }
        except Exception as e:
            logger.error(f"YouTube search primary failed ({e}), using yt-dlp fallback...")
            try:
                import yt_dlp
                loop = asyncio.get_event_loop()
                def _ytdlp_search():
                    opts = {'quiet': True, 'extract_flat': True}
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        data = ydl.extract_info(f"ytsearch1:{query}", download=False)
                        if 'entries' in data and len(data['entries']) > 0:
                            return data['entries'][0]
                    return None
                
                info = await loop.run_in_executor(None, _ytdlp_search)
                if info:
                    def _fmt_dur(sec):
                        try:
                            m, s = divmod(int(sec), 60)
                            return f"{m}:{s:02d}"
                        except: return "0:00"
                    return {
                        "title": info.get("title", query),
                        "duration": _fmt_dur(info.get("duration", 0)),
                        "vidid": info.get("id"),
                        "thumbnail_url": info.get("thumbnails", [{"url": config.STREAM_IMG_URL}])[0]["url"] if info.get("thumbnails") else config.STREAM_IMG_URL
                    }
            except Exception as fe:
                logger.error(f"yt-dlp fallback search failed: {fe}")
                
            return {
                "title": query,
                "duration": "0:00",
                "vidid": None,
                "thumbnail_url": config.STREAM_IMG_URL
            }

    async def get_song_by_keyword(self, keyword: str) -> Optional[str]:

        """Get and download song by keyword"""
        await self.initialize()
        
        if not keyword or not self._app:
            return None
        
        try:
            # Get message from channel
            message = await self._get_song_by_keyword(keyword)
            if not message:
                logger.warning(f"Keyword not found: {keyword}")
                return None
            
            # Generate filename
            if message.audio:
                file_name = message.audio.file_name or f"{keyword}_{message.id}.mp3"
            elif message.document:
                file_name = message.document.file_name or f"{keyword}_{message.id}"
            elif message.video:
                file_name = message.video.file_name or f"{keyword}_{message.id}.mp4"
            else:
                file_name = f"{keyword}_{message.id}"
            
            file_path = os.path.join(self.download_folder, file_name)
            
            # Download the file
            logger.info(f"Downloading keyword file: {file_path}")
            await self._app.download_media(message, file_name=file_path)
            
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                logger.info(f"Keyword download successful: {os.path.getsize(file_path)} bytes")
                return file_path
            
        except Exception as e:
            logger.error(f"Error downloading song by keyword: {e}")
        
        return None
    
    async def _get_channel_info(self):
        """Get channel ID and verify access"""
        if not CHANNEL_USERNAME or not self._app:
            return
        
        try:
            chat = await self._app.get_chat(CHANNEL_USERNAME)
            self._channel_id = chat.id
            logger.info(f"Channel info: ID={self._channel_id}, Title={chat.title}, Username={chat.username}")
            
            # Test access
            try:
                async for msg in self._app.get_chat_history(self._channel_id, limit=5):
                    logger.debug(f"Channel test: Found message {msg.id}")
                logger.info(f"Successfully accessed channel {CHANNEL_USERNAME}")
            except Exception as e:
                logger.warning(f"Limited access to channel: {e}")
        except Exception as e:
            logger.error(f"Failed to get channel info for {CHANNEL_USERNAME}: {e}")
            self._channel_id = None
    
    def _load_cache(self, cache_file: str) -> Dict:
        """Load cache from file"""
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    cache = json.load(f)
                    logger.info(f"Loaded cache '{cache_file}' with {len(cache)} entries")
                    return cache
            except Exception as e:
                logger.error(f"Error loading cache {cache_file}: {e}")
                return {}
        return {}
    
    def _save_cache(self, cache_file: str, cache: Dict):
        """Save cache to file"""
        try:
            with open(cache_file, 'w') as f:
                json.dump(cache, f, indent=2)
            logger.debug(f"Cache '{cache_file}' saved with {len(cache)} entries")
        except Exception as e:
            logger.error(f"Error saving cache {cache_file}: {e}")
    
    async def _cleanup_scheduler(self):
        """Schedule cleanup every hour"""
        await asyncio.sleep(60)
        
        while True:
            try:
                await self._cleanup_downloads()
                await asyncio.sleep(3600)
            except Exception as e:
                logger.error(f"Error in cleanup scheduler: {e}")
                await asyncio.sleep(300)
    
    async def _cleanup_downloads(self, max_age_hours: int = 24):
        """Clean up old files in downloads folder"""
        try:
            now = time.time()
            deleted_count = 0
            
            for filename in os.listdir(self.download_folder):
                file_path = os.path.join(self.download_folder, filename)
                try:
                    if os.path.isfile(file_path):
                        file_age = now - os.path.getmtime(file_path)
                        if file_age > max_age_hours * 3600:
                            os.unlink(file_path)
                            deleted_count += 1
                            logger.debug(f"Cleaned up old file: {filename}")
                except Exception as e:
                    logger.error(f"Error deleting {file_path}: {e}")
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old files")
                
        except Exception as e:
            logger.error(f"Error in cleanup: {e}")
    
    def _get_video_id(self, link: str) -> str:
        """Extract video ID from YouTube URL"""
        if not link:
            return ""
        
        if re.match(r'^[a-zA-Z0-9_-]{11}$', link):
            return link
        
        patterns = [
            r'(?:v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
            r'youtube\.com/v/([a-zA-Z0-9_-]{11})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, link)
            if match:
                return match.group(1)
        
        if 'youtube.com/watch?v=' in link:
            parts = link.split('v=')
            if len(parts) > 1:
                return parts[1].split('&')[0]
        elif 'youtu.be/' in link:
            return link.split('youtu.be/')[1].split('?')[0]
        elif 'youtube.com/shorts/' in link:
            return link.split('/shorts/')[1].split('?')[0]
        elif link.startswith("db_"):
            return link
            
        # For non-URL search queries, return a placeholder ID instead of empty string
        if not bool(re.search(self.regex, link)) and len(link.strip()) > 0:
            # Use 'kw_' prefix to distinguish from 'db_' message IDs
            return "kw_" + hashlib.md5(link.encode()).hexdigest()[:8]
        
        return ""
    
    async def _get_song_info(self, link: str, fallback_title: str = None) -> Dict:
        """Get song information using VideosSearch with fallback for unsupported videos"""
        try:
            if '&' in link:
                link = link.split('&')[0]
            
            # Check for keyword in DB channel first
            is_url = bool(re.search(self.regex, link))
            if not is_url:
                keyword_msg = await self._get_song_by_keyword(link)
                if keyword_msg:
                    logger.info(f"Found keyword '{link}' in DB channel")
                    file_name = link
                    duration = "3:30"
                    if keyword_msg.audio:
                        file_name = keyword_msg.audio.file_name or link
                        duration = seconds_to_min(keyword_msg.audio.duration)
                    elif keyword_msg.document:
                        file_name = keyword_msg.document.file_name or link
                        
                    chat_id_str = str(keyword_msg.chat.id)
                    chat_id_short = chat_id_str[4:] if chat_id_str.startswith("-100") else chat_id_str
                        
                    return {
                        'title': file_name,
                        'duration': duration,
                        'thumbnail': 'https://via.placeholder.com/360x202?text=DB+Channel',
                        'video_id': f"db_{keyword_msg.id}",
                        'channel': 'DB Channel',
                        'link': f"https://t.me/c/{chat_id_short}/{keyword_msg.id}",
                        'published_time': '',
                        'view_count': '',
                        'raw_query': link,
                        'from_db': True
                    }
                
                # USER REQUEST: FALLBACK TO GROUP SEARCH (ONLY FOR STREAMING FLOW)
                # We can trigger a dry-run search in the group to see if we can get a file ID
                logger.info(f"Searching for '{link}' in @shadowmusicbase group...")
                group_file = await self._find_in_group_for_streaming(link)
                if group_file:
                    logger.info(f"Found in group for streaming: {link}")
                    # ENHANCE: Use Groq for metadata if possible
                    title, thumbnail = await get_enhanced_metadata(link)
                    return {
                        'title': title,
                        'duration': "4:00",
                        'thumbnail': thumbnail,
                        'video_id': f"gp_{group_file.id}",
                        'channel': 'Group Database',
                        'link': link, # Store original query
                        'published_time': '',
                        'view_count': '',
                        'raw_query': link,
                        'from_gp': True,
                        'gp_msg_id': group_file.id
                    }
            
            try:
                results = VideosSearch(link, limit=1)
                search_result = await results.next()
            except Exception as e:
                logger.error(f"VideosSearch failed, trying yt-dlp info fallback: {e}")
                # Fallback to yt-dlp to get Info
                import yt_dlp
                ydl_opts = {"quiet": True, "no_warnings": True, "format": "bestaudio/best"}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    try:
                        loop = asyncio.get_event_loop()
                        # If it's not a URL, search first
                        if not is_url:
                            search_link = f"ytsearch1:{link}"
                        else:
                            search_link = link
                        info = await loop.run_in_executor(None, lambda: ydl.extract_info(search_link, download=False))
                        if 'entries' in info:
                            info = info['entries'][0]
                        
                        return {
                            'title': info.get('title', 'Unknown'),
                            'duration': seconds_to_min(info.get('duration', 0)),
                            'thumbnail': info.get('thumbnail', 'https://via.placeholder.com/360x202?text=No+Thumbnail'),
                            'video_id': info.get('id', ''),
                            'channel': info.get('uploader', 'Unknown'),
                            'link': info.get('webpage_url', link),
                            'published_time': '',
                            'view_count': '',
                            'raw_query': link if not is_url else None
                        }
                    except Exception as ex:
                        logger.error(f"yt-dlp fallback also failed: {ex}")
                        search_result = {"result": []}

            if not search_result.get("result"):
                # If no results found, use fallback data
                if fallback_title:
                    logger.info(f"Using fallback data for: {fallback_title}")
                    # Generate random duration between 2-5 minutes
                    minutes = random.randint(2, 5)
                    seconds = random.randint(0, 59)
                    duration = f"{minutes}:{seconds:02d}"
                    
                    return {
                        'title': fallback_title,
                        'duration': duration,
                        'thumbnail': 'https://via.placeholder.com/360x202?text=No+Thumbnail',
                        'video_id': self._get_video_id(link),
                        'channel': 'Unknown',
                        'link': link,
                        'published_time': '',
                        'view_count': ''
                    }
                return {}
            
            result = search_result["result"][0]
            
            # Ensure all fields have valid values using .get() to avoid "string indices" error
            title = result.get('title', fallback_title or link or 'Unknown')
                
            duration = result.get('duration', '0:00')
            
            # SAFE THUMBNAIL PARSING
            thumbnail = getattr(config, "STREAM_IMG_URL", 'https://via.placeholder.com/360x202?text=No+Thumbnail')
            if result.get('thumbnails') and isinstance(result['thumbnails'], list) and len(result['thumbnails']) > 0:
                thumb_obj = result['thumbnails'][0]
                if isinstance(thumb_obj, dict):
                    thumbnail = thumb_obj.get('url', thumbnail).split('?')[0]
                
            video_id = result.get('id', '')
                
            channel = result.get('channel', {}).get('name', 'Unknown') if isinstance(result.get('channel'), dict) else 'Unknown'
                
            published_time = result.get('publishedTime', '')
                
            view_count = ''
            if result.get('viewCount') and isinstance(result['viewCount'], dict):
                view_count = result['viewCount'].get('short', '')
            
            # Include raw_query if the input was a search query, not a URL
            is_url = bool(re.search(self.regex, link))
            
            return {
                'title': title,
                'duration': duration,
                'thumbnail': thumbnail,
                'video_id': video_id,
                'channel': channel,
                'link': result.get('link', link),
                'published_time': published_time,
                'view_count': view_count,
                'raw_query': link if not is_url else None
            }
        except Exception as e:
            logger.error(f"Error getting song info: {e}")
            # If an error occurs, use fallback data
            if fallback_title:
                logger.info(f"Using fallback data after error for: {fallback_title}")
                # Generate random duration between 2-5 minutes
                minutes = random.randint(2, 5)
                seconds = random.randint(0, 59)
                duration = f"{minutes}:{seconds:02d}"
                
                return {
                    'title': fallback_title,
                    'duration': duration,
                    'thumbnail': 'https://via.placeholder.com/360x202?text=No+Thumbnail',
                    'video_id': self._get_video_id(link),
                    'channel': 'Unknown',
                    'link': link,
                    'published_time': '',
                    'view_count': ''
                }
            return {}
    
    def _check_local_file(self, video_id: str) -> Optional[str]:
        """Check if file exists locally"""
        if not os.path.exists(self.download_folder):
            return None
            
        patterns = [f"{video_id}.*", f"*{video_id}.*"]
        
        for pattern in patterns:
            for file_path in os.listdir(self.download_folder):
                if fnmatch.fnmatch(file_path.lower(), pattern.lower()):
                    full_path = os.path.join(self.download_folder, file_path)
                    if os.path.exists(full_path):
                        logger.debug(f"Found local file: {full_path}")
                        return full_path
        
        return None
    
    async def _search_in_channel(self, video_id: str) -> Optional[Message]:
        """Search for song in channel using multiple methods"""
        if not self._app or not CHANNEL_USERNAME:
            return None
        
        try:
            # Check cache first
            if video_id in self.cache:
                cache_info = self.cache[video_id]
                try:
                    channel_id = cache_info.get('channel_id', CHANNEL_USERNAME)
                    message = await self._app.get_messages(
                        channel_id,
                        cache_info['message_id']
                    )
                    if message and (message.audio or message.document):
                        logger.info(f"Found in cache: {video_id}")
                        return message
                except Exception as e:
                    logger.debug(f"Cache entry invalid: {e}")
                    self.cache.pop(video_id, None)
                    self._save_cache(self.cache_file, self.cache)
            
            # Search by video ID
            logger.debug(f"Searching for {video_id} in channel")
            
            search_terms = [video_id, f"ID: {video_id}", f"id: {video_id}", 
                          video_id.lower(), video_id.upper()]
            
            found_messages = []
            
            try:
                async with self._search_semaphore:
                    async for message in self._app.search_messages(
                        chat_id=CHANNEL_USERNAME,
                        query=video_id,
                        limit=10,
                        filter=MessagesFilter.AUDIO
                    ):
                        if message and (message.audio or message.document):
                            found_messages.append(message)
                            break  # First match is enough for ID search
                
                    if not found_messages:
                        async for message in self._app.get_chat_history(
                            chat_id=CHANNEL_USERNAME,
                            limit=50
                        ):
                            if message and (message.audio or message.document):
                                if message.caption:
                                    caption_lower = message.caption.lower()
                                    for term in search_terms:
                                        if term.lower() in caption_lower:
                                            found_messages.append(message)
                                            break
                                
                                filename = None
                                if message.audio and message.audio.file_name:
                                    filename = message.audio.file_name.lower()
                                elif message.document and message.document.file_name:
                                    filename = message.document.file_name.lower()
                                
                                if filename and video_id.lower() in filename:
                                    found_messages.append(message)
                            
                                if found_messages:
                                    break  # Stop scanning once found
            
            except Exception as e:
                logger.warning(f"Search limited: {e}")
                try:
                    async for message in self._app.get_chat_history(
                        CHANNEL_USERNAME,
                        limit=100
                    ):
                        if message and (message.audio or message.document):
                            filename = None
                            if message.audio and message.audio.file_name:
                                filename = message.audio.file_name.lower()
                            elif message.document and message.document.file_name:
                                filename = message.document.file_name.lower()
                            
                            if filename and video_id.lower() in filename:
                                found_messages.append(message)
                                break
                except Exception as inner_e:
                    logger.error(f"Even direct history failed: {inner_e}")
            
            if found_messages:
                message = found_messages[0]
                logger.info(f"Found in channel: {video_id} (msg_id: {message.id})")
                
                self.cache[video_id] = {
                    'message_id': message.id,
                    'channel_id': CHANNEL_USERNAME,
                    'timestamp': time.time(),
                    'title': message.caption or (message.audio.file_name if message.audio else "Unknown")
                }
                self._save_cache(self.cache_file, self.cache)
                
                return message
            
            logger.info(f"Not found in channel: {video_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error searching in channel: {e}")
            return None
    
    async def _download_from_youmusic_group(self, link: str, title: str, video_id: str, raw_query: str = None) -> Optional[str]:
        """Download song from YouMusicRobot using group method"""
        if not self._youmusic_app:
            logger.warning("YouMusicRobot app not available")
            return None
        
        try:
            clean_title = re.sub(r'\(.*?\)|\[.*?\]', '', title).strip()
            clean_title = re.sub(r'\s+', ' ', clean_title)
            
            query_id = f"dl_{int(time.time() * 1000)}_{random.randint(10000, 99999)}"
            
            # Use raw query if provided, otherwise use cleaned YouTube title
            search_title = raw_query if raw_query else clean_title
            query = f"find {search_title} | #{query_id}"
            
            logger.info(f"Sending to YouMusicRobot: {search_title}")
            
            sent_message = await self._youmusic_app.send_message(GROUP_USERNAME, query)
            sent_message_id = sent_message.id
            
            audio_message = None
            timeout = 45
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                try:
                    async for message in self._youmusic_app.get_chat_history(
                        GROUP_USERNAME,
                        limit=20
                    ):
                        if message.id == sent_message_id:
                            continue
                        
                        if message.from_user and message.from_user.username == "YouMusicRobot":
                            if message.audio or (message.document and 
                                               message.document.mime_type and 
                                               message.document.mime_type.startswith('audio/')):
                                is_reply = (message.reply_to_message and 
                                          message.reply_to_message.id == sent_message_id)
                                time_diff = (message.date - sent_message.date).total_seconds()
                                is_recent = 0 < time_diff < 30
                                
                                if is_reply or is_recent:
                                    audio_message = message
                                    logger.info(f"Found audio response (ID: {message.id})")
                                if audio_message:
                                    break
                    
                    if audio_message:
                        break
                        
                except Exception as e:
                    logger.debug(f"Error checking messages in group: {e}")
                
                await asyncio.sleep(1) # Faster polling
            
            if audio_message:
                file_path = await self._download_audio_file(self._youmusic_app, audio_message, video_id)
                
                try:
                    await self._youmusic_app.delete_messages(GROUP_USERNAME, [sent_message_id, audio_message.id])
                except:
                    pass
                
                logger.info(f"Group download successful: {file_path}")
                return file_path
            else:
                logger.warning("No audio found in group, trying direct...")
                return await self._download_from_youmusic_direct(clean_title, video_id)
            
        except Exception as e:
            logger.error(f"YouMusicRobot group download failed: {e}")
            return None
    
    async def _find_in_group_for_streaming(self, query: str) -> Optional[Message]:
        """A faster dry-run search for streaming only"""
        if not self._youmusic_app:
            return None
        try:
            query_id = f"stream_{int(time.time())}"
            sent = await self._youmusic_app.send_message(GROUP_USERNAME, f"find {query}")
            
            start_time = time.time()
            while time.time() - start_time < 20: # Shorter timeout for streaming flow
                async for message in self._youmusic_app.get_chat_history(GROUP_USERNAME, limit=10):
                    if message.id <= sent.id: continue
                    is_audio = message.audio or (message.document and message.document.mime_type and message.document.mime_type.startswith('audio/'))
                    if is_audio:
                        is_reply = (message.reply_to_message and message.reply_to_message.id == sent.id)
                        time_diff = (message.date - sent.date).total_seconds()
                        if is_reply or (0 < time_diff < 15):
                            return message
                await asyncio.sleep(1)
            return None
        except:
            return None

    async def _download_from_youmusic_direct(self, query: str, video_id: str) -> Optional[str]:
        """Try downloading directly from YouMusicRobot bot"""
        if not self._youmusic_app:
            return None
        
        try:
            sent_message = await self._youmusic_app.send_message("YouMusicRobot", query)
            
            await asyncio.sleep(5)
            
            async for message in self._youmusic_app.get_chat_history(
                "YouMusicRobot",
                limit=10
            ):
                if message.id > sent_message.id and message.from_user:
                    if message.audio or (message.document and 
                                       message.document.mime_type and 
                                       message.document.mime_type.startswith('audio/')):
                        file_path = await self._download_audio_file(self._youmusic_app, message, video_id)
                        
                        try:
                            await self._youmusic_app.delete_messages("YouMusicRobot", [sent_message.id, message.id])
                        except:
                            pass
                        
                        return file_path
            
            return None
        except Exception as e:
            logger.error(f"Direct YouMusicRobot download failed: {e}")
            return None
    
    async def _download_audio_file(self, app: Client, message: Message, video_id: str) -> str:
        """Download audio file from message"""
        if message.audio:
            file_name = message.audio.file_name or f"{video_id}.mp3"
            file_ext = os.path.splitext(file_name)[1]
            if not file_ext:
                file_ext = ".mp3"
        elif message.document:
            file_name = message.document.file_name or f"{video_id}.mp3"
            file_ext = os.path.splitext(file_name)[1]
            if not file_ext:
                file_ext = ".mp3"
        else:
            file_name = f"{video_id}.mp3"
            file_ext = ".mp3"
        
        file_name = f"{video_id}{file_ext}"
        file_path = os.path.join(self.download_folder, file_name)
        
        logger.info(f"Downloading audio file: {file_path}")
        await app.download_media(message, file_name=file_path)
        
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            logger.info(f"Download successful: {os.path.getsize(file_path)} bytes")
            return file_path
        else:
            raise Exception("Downloaded file is empty or doesn't exist")
    
    async def _upload_to_channel(self, file_path: str, title: str, video_id: str) -> Optional[Message]:
        """Upload song to channel"""
        if not self._app or not CHANNEL_USERNAME or not os.path.exists(file_path):
            return None
        
        try:
            clean_title = re.sub(r'[^\w\s\-\.]', ' ', title)
            clean_title = re.sub(r'\s+', ' ', clean_title).strip()
            
            if len(clean_title) > 100:
                clean_title = clean_title[:97] + "..."
            
            caption = f"{clean_title}\n\nID: {video_id}"
            
            logger.info(f"Uploading to channel {CHANNEL_USERNAME}: {clean_title}")
            
            chat_id = self._channel_id if self._channel_id else CHANNEL_USERNAME
            
            message = await self._app.send_audio(
                chat_id=chat_id,
                audio=file_path,
                caption=caption,
                file_name=f"{video_id}.mp3",
                thumb=None,
                duration=0,
                performer="YouTube",
                title=clean_title
            )
            
            self.cache[video_id] = {
                'message_id': message.id,
                'channel_id': chat_id,
                'timestamp': time.time(),
                'title': clean_title,
                'file_size': os.path.getsize(file_path) if os.path.exists(file_path) else 0
            }
            self._save_cache(self.cache_file, self.cache)
            
            logger.info(f"Uploaded to channel (message_id: {message.id})")
            return message
            
        except Exception as e:
            logger.error(f"Error uploading to channel: {e}")
            return None
    
    async def download_song(self, link: str, raw_query: str = None) -> Optional[str]:
        """Main method to download song following Step 2 logic: 2A -> 2B
        With concurrency controls and download deduplication."""
        await self.initialize()
        
        try:
            # 1. Resolve query
            query = raw_query if raw_query else link
            video_id = self._get_video_id(link)
            
            # 2. Local check (instant, no lock needed)
            if video_id:
                local_file = self._check_local_file(video_id)
                if local_file:
                    logger.info(f"Using local file: {local_file}")
                    return local_file
            
            # --- Download Deduplication ---
            # If another task is already downloading this exact video_id,
            # wait for it instead of starting a duplicate download.
            dedup_key = video_id or query
            async with self._inflight_lock:
                if dedup_key in self._inflight_downloads:
                    logger.info(f"Waiting for in-flight download: {dedup_key}")
                    existing_lock = self._inflight_downloads[dedup_key]
                else:
                    existing_lock = asyncio.Lock()
                    self._inflight_downloads[dedup_key] = existing_lock
            
            async with existing_lock:
                # Re-check local after acquiring lock (another task may have finished)
                if video_id:
                    local_file = self._check_local_file(video_id)
                    if local_file:
                        logger.info(f"Using local file (post-dedup): {local_file}")
                        return local_file
                
                result = await self._do_download(link, query, video_id, raw_query)
                return result
            
        except Exception as e:
            logger.error(f"Error in download_song: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
        finally:
            # Cleanup inflight entry
            try:
                async with self._inflight_lock:
                    self._inflight_downloads.pop(dedup_key, None)
            except:
                pass
    
    async def _do_download(self, link, query, video_id, raw_query):
        """Actual download logic, called under dedup lock + semaphore."""
        async with self._download_semaphore:
            if video_id:
                # PRE-STEP 2A: Search by ID (Highest Precision)
                logger.info(f"Checking DB channel for ID: {video_id}")
                id_msg = await self._search_in_channel(video_id)
                if id_msg:
                    file_path = await self._download_audio_file(self._app, id_msg, video_id)
                    if file_path:
                        logger.info(f"Acquired via ID match: {file_path}")
                        return file_path
            
            # STEP 2A - Search @smashmusicdb (CHANNEL_USERNAME) by Title
            logger.info(f"Step 2A: Searching @smashmusicdb for: {query}")
            msg = await self._search_smash_db(query)
            if msg:
                vidid_db = video_id if video_id else f"db_{msg.id}"
                file_path = await self._download_audio_file(self._app, msg, vidid_db)
                if file_path:
                    logger.info(f"Acquired from Step 2A by title: {file_path}")
                    return file_path
            
            # STEP 2B - Request via @YouMusicRobot
            if not raw_query or bool(re.search(self.regex, query)) or len(query) == 11:
                logger.debug(f"Resolving title for external search: {query}")
                info = await self._get_song_info(link, fallback_title=raw_query)
                if info and info.get('title'):
                    query = info['title']
                    logger.info(f"Using resolved title for Step 2B search: {query}")

            logger.info(f"Step 2B: Fetching via @YouMusicRobot for: {query}")
            title = raw_query or query
            file_path = await self._fetch_via_youmusicbot(query, title=title)
            if file_path:
                logger.info(f"Acquired from Step 2B: {file_path}")
                return file_path
                
            # Final fallback
            logger.warning("Acquisition failed in both 2A and 2B. Final fallback attempt...")
            return await self._download_fallback(link, video_id or "unknown")
    
    async def _download_fallback(self, link: str, video_id: str) -> Optional[str]:
        """Fallback download methods"""
        if API_URL and API_KEY:
            try:
                api_url = f"{API_URL}/song/{video_id}?api={API_KEY}"
                logger.info(f"Trying API: {api_url}")
                
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                    async with session.get(api_url) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get("status", "").lower() == "done":
                                download_url = data.get("link")
                                if download_url:
                                    file_ext = data.get("format", "mp3").lower()
                                    file_path = os.path.join(self.download_folder, f"{video_id}.{file_ext}")
                                    
                                    async with session.get(download_url) as file_response:
                                        with open(file_path, 'wb') as f:
                                            async for chunk in file_response.content.iter_chunked(8192):
                                                f.write(chunk)
                                    
                                    if os.path.exists(file_path):
                                        logger.info(f"API download successful: {file_path}")
                                        return file_path
            except Exception as e:
                logger.debug(f"API fallback failed: {e}")
        
        try:
            logger.info("Trying yt-dlp...")
            file_path = os.path.join(self.download_folder, f"{video_id}.mp3")
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': file_path.replace('.mp3', '') + '.%(ext)s',
                'quiet': True,
                'no_warnings': True,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }
            
            def _ytdlp_audio():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([link])
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _ytdlp_audio)
            
            for ext in ["mp3", "m4a", "opus", "webm"]:
                possible_path = os.path.join(self.download_folder, f"{video_id}.{ext}")
                if os.path.exists(possible_path):
                    logger.info(f"yt-dlp download successful: {possible_path}")
                    return possible_path
                    
        except Exception as e:
            logger.debug(f"yt-dlp fallback failed: {e}")
        
        return None
    
    async def download_video(self, link: str) -> Optional[str]:
        """Download video"""
        await self.initialize()
        
        try:
            video_id = self._get_video_id(link)
            if not video_id:
                return None
            
            for ext in ["mp4", "webm", "mkv"]:
                file_path = os.path.join(self.download_folder, f"{video_id}.{ext}")
                if os.path.exists(file_path):
                    return file_path
            
            if VIDEO_API_URL and API_KEY:
                try:
                    video_url = f"{VIDEO_API_URL}/video/{video_id}?api={API_KEY}"
                    
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
                        async with session.get(video_url) as response:
                            if response.status == 200:
                                data = await response.json()
                                if data.get("status", "").lower() == "done":
                                    download_url = data.get("link")
                                    if download_url:
                                        file_ext = data.get("format", "mp4").lower()
                                        file_path = os.path.join(self.download_folder, f"{video_id}.{file_ext}")
                                        
                                        async with session.get(download_url) as file_response:
                                            with open(file_path, 'wb') as f:
                                                async for chunk in file_response.content.iter_chunked(65536):
                                                    f.write(chunk)
                                        
                                        logger.info(f"Video API download successful: {file_path}")
                                        return file_path
                except Exception as e:
                    logger.error(f"Video API failed: {e}")
            
            try:
                file_path = os.path.join(self.download_folder, f"{video_id}.mp4")
                ydl_opts = {
                    'format': 'best[ext=mp4]/best',
                    'outtmpl': file_path.replace('.mp4', '') + '.%(ext)s',
                    'quiet': True,
                    'no_warnings': True,
                }
                
                def _ytdlp_video():
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([link])
                
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, _ytdlp_video)
                
                for ext in ["mp4", "webm", "mkv"]:
                    possible_path = os.path.join(self.download_folder, f"{video_id}.{ext}")
                    if os.path.exists(possible_path):
                        return possible_path
                        
            except Exception as e:
                logger.error(f"yt-dlp video download failed: {e}")
            
            return None
            
        except Exception as e:
            logger.error(f"Error downloading video: {e}")
            return None
    
    # Compatibility methods for existing code
    
    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))
    
    async def url(self, message_1: Message) -> Optional[str]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        
        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        return text[entity.offset:entity.offset + entity.length]
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        
        return None
    
    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        
        try:
            # Get video ID for fallback
            video_id = self._get_video_id(link)
            f_title = f"YouTube Video {video_id}" if video_id else "Unknown Video"
            
            song_info = await self._get_song_info(link, f_title)
            if song_info:
                title = song_info.get('title', 'Unknown Title')
                duration_min = song_info.get('duration', '0:00')
                thumbnail = song_info.get('thumbnail', 'https://via.placeholder.com/360x202?text=No+Thumbnail')
                vidid = song_info.get('video_id', video_id or '')
                
                duration_sec = 0
                try:
                    if duration_min and ':' in duration_min:
                        parts = duration_min.split(':')
                        if len(parts) == 2:
                            duration_sec = int(parts[0]) * 60 + int(parts[1])
                        elif len(parts) == 3:
                            duration_sec = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                except:
                    # Generate random duration if parsing fails
                    minutes = random.randint(2, 5)
                    seconds = random.randint(0, 59)
                    duration_min = f"{minutes}:{seconds:02d}"
                    duration_sec = minutes * 60 + seconds
                
                return title, duration_min, duration_sec, thumbnail, vidid
        except Exception as e:
            logger.error(f"Error getting details: {e}")
        
        # Ultimate fallback
        video_id = self._get_video_id(link)
        if video_id:
            minutes = random.randint(2, 5)
            seconds = random.randint(0, 59)
            duration_min = f"{minutes}:{seconds:02d}"
            duration_sec = minutes * 60 + seconds
            return f"Video {video_id}", duration_min, duration_sec, 'https://via.placeholder.com/360x202?text=No+Thumbnail', video_id
        
        return None, None, 0, None, None
    
    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        try:
            video_id = self._get_video_id(link)
            fallback_title = f"YouTube Video {video_id}" if video_id else "Unknown Video"
            song_info = await self._get_song_info(link, fallback_title)
            return song_info.get('title') if song_info else fallback_title
        except:
            video_id = self._get_video_id(link)
            return str("Video " + str(video_id or "Unknown"))
    
    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        try:
            song_info = await self._get_song_info(link)
            if song_info and song_info.get('duration'):
                return song_info['duration']
        except:
            pass
        
        # Generate random duration
        minutes = random.randint(2, 5)
        seconds = random.randint(0, 59)
        return f"{minutes}:{seconds:02d}"
    
    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        try:
            song_info = await self._get_song_info(link)
            if song_info and song_info.get('thumbnail'):
                return song_info['thumbnail']
        except:
            pass
        
        return 'https://via.placeholder.com/360x202?text=No+Thumbnail'
    
    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        
        try:
            video_id = self._get_video_id(link)
            fallback_title = f"YouTube Video {video_id}" if video_id else "Unknown Video"
            
            song_info = await self._get_song_info(link, fallback_title)
            if song_info:
                return {
                    "title": song_info.get('title', fallback_title),
                    "link": song_info.get('link', link),
                    "vidid": song_info.get('video_id', video_id or ''),
                    "duration_min": song_info.get('duration', '3:00'),
                    "thumb": song_info.get('thumbnail', 'https://via.placeholder.com/360x202?text=No+Thumbnail'),
                    "raw_query": song_info.get('raw_query'),
                }, song_info.get('video_id', video_id or '')
        except Exception as e:
            logger.error(f"Error in track: {e}")
        
        # Ultimate fallback
        video_id = self._get_video_id(link) or "unknown"
        minutes = random.randint(2, 5)
        seconds = random.randint(0, 59)
        duration_min = f"{minutes}:{seconds:02d}"
        return {
            "title": link.title() if link else f"Video {video_id}",
            "link": link,
            "vidid": video_id,
            "duration_min": duration_min,
            "thumb": getattr(config, "STREAM_IMG_URL", 'https://via.placeholder.com/360x202?text=No+Thumbnail'),
        }, video_id
        
        return None, None
    
    async def download(self, link: str, mystic=None, video=False, raw_query: str = None, **kwargs) -> tuple:
        """Main download method for compatibility"""
        try:
            if video:
                file_path = await self.download_video(link)
            else:
                file_path = await self.download_song(link, raw_query=raw_query)
            
            return file_path, True if file_path else None
        except Exception as e:
            logger.error(f"Download error: {e}")
            return None, None
    
    async def close(self):
        """Clean up resources"""
        try:
            if self._cleanup_task:
                self._cleanup_task.cancel()
            
            if self._app:
                await self._app.stop()
                self._app = None
            
            if self._youmusic_app:
                await self._youmusic_app.stop()
                self._youmusic_app = None
            
            self._initialized = False
            logger.info("YouTube API closed")
        except Exception as e:
            logger.error(f"Error closing YouTube API: {e}")


# Create global instance
youtube = YouTubeAPI()

# Backward compatibility functions
async def download_song(link: str) -> Optional[str]:
    return await youtube.download_song(link)

async def download_video(link: str) -> Optional[str]:
    return await youtube.download_video(link)

async def get_song_by_keyword(keyword: str) -> Optional[str]:
    return await youtube.get_song_by_keyword(keyword)

async def initialize_module():
    return await youtube.initialize()

async def close_module():
    return await youtube.close()

# Export the YouTubeAPI class
__all__ = [
    'YouTubeAPI', 'youtube', 'download_song', 'download_video', 
    'get_song_by_keyword', 'initialize_module', 'close_module'
]
