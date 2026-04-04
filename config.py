# config.py — Merged from both bots

import os, re
from os import getenv
from dotenv import load_dotenv
from pyrogram import filters

load_dotenv()

AYU = ["🎀","🌸","✨","🧸","🍭","🥀","💖","🦋","🍬","🦄","🌈"]
AYUV = [ "**➲ ʜᴇʏ {0}**\n\n**ɪ'ᴍ {1}, ʏᴏᴜʀ ᴘʀᴇᴍɪᴜᴍ ᴍᴜsɪᴄ sᴛʀᴇᴀᴍɪɴɢ sᴏʟᴜᴛɪᴏɴ.**\n\n**➲ ʜɪɢʜ ǫᴜᴀʟɪᴛʏ ᴀᴜᴅɪᴏ/ᴠɪᴅᴇᴏ**\n**➲ sᴇᴀᴍʟᴇss ᴇxᴘᴇʀɪᴇɴᴄᴇ**\n**➲ sᴜᴘᴘᴏʀᴛᴇᴅ :** ʏᴏᴜᴛᴜʙᴇ, sᴘᴏᴛɪғʏ, ʀᴇssᴏ, ᴀᴘᴘʟᴇ ᴍᴜsɪᴄ.\n\n**➲ ᴄʟɪᴄᴋ ʜᴇʟᴘ ʙᴇʟᴏᴡ ᴛᴏ ᴠɪᴇᴡ ᴍᴀɴᴜᴀʟs.**"  ,
]

# ─── BOT IDENTITY ───────────────────────────────────────────
API_ID           = int(getenv("API_ID", "23212132"))
API_HASH = getenv("API_HASH", None)
BOT_TOKEN = getenv("BOT_TOKEN", None)
OWNER_ID         = int(getenv("OWNER_ID", "5598691892"))
OWNER_USERNAME   = getenv("OWNER_USERNAME", "@SpotifyHim")
BOT_USERNAME     = getenv("BOT_USERNAME", "@YourMusicBot")
BOT_NAME         = getenv("BOT_NAME", "Antigravity Music")
ASSUSERNAME      = getenv("ASSUSERNAME", "@RedBotAssistant")
EVALOP           = list(map(int, getenv("EVALOP", "").split())) if getenv("EVALOP", "").strip() else []
GPT_API          = getenv("GPT_API", None)
DEEP_API         = getenv("DEEP_API", None)

# ─── 5 ASSISTANT SESSIONS (from ShrutiMusic) ────────────────
STRING1 = getenv("STRING1", None)
STRING2 = getenv("STRING2", None)
STRING3 = getenv("STRING3", None)
STRING4 = getenv("STRING4", None)
STRING5 = getenv("STRING5", None)

# ─── SONG FETCHING SESSIONS (from SmashMusic) ───────────────
SESSION_STRING = getenv("SESSION_STRING", None)      # For DB channel reads
YOU_MUSIC_SESSION = getenv("YOU_MUSIC_SESSION", None)   # For @shadowmusicbase /find

# ─── TELEGRAM DB CHANNELS ───────────────────────────────────
CHANNEL_USERNAME     = getenv("CHANNEL_USERNAME", "@ShakkyData")     # Song archive channel
GROUP_USERNAME       = getenv("GROUP_USERNAME", "shadowmusicbase")     # Song request group
SONG_CHANNEL_ID      = int(getenv("SONG_CHANNEL_ID", "-1003791830381"))
DATABASE_CHANNEL     = getenv("DATABASE_CHANNEL", "ShakkyData")
DATABASE_CHANNEL_ID  = int(getenv("DATABASE_CHANNEL_ID", "-1002422501099"))

# ─── MONGODB ────────────────────────────────────────────────
MONGO_DB_URI = getenv("MONGO_DB_URI", None)

# ─── SONG API (SmashMusic NexGen API) ───────────────────────
API_URL        = getenv("API_URL", "https://api.nexgenbots.xyz")
VIDEO_API_URL  = getenv("VIDEO_API_URL", "https://api.video.nexgenbots.xyz")
API_KEY = getenv("API_KEY", None)

# ─── SPOTIFY ────────────────────────────────────────────────
SPOTIFY_CLIENT_ID = getenv("SPOTIFY_CLIENT_ID", None)
SPOTIFY_CLIENT_SECRET = getenv("SPOTIFY_CLIENT_SECRET", None)

# ─── WEBAPP (SmashMusic) ────────────────────────────────────
WEBAPP_PORT = int(getenv("WEBAPP_PORT", 8100))
WEBAPP_URL  = getenv("WEBAPP_URL", "https://your-cloudflare-tunnel.trycloudflare.com")

# ─── GROQ AI ────────────────────────────────────────────────
GROQ_API_KEY = getenv("GROQ_API_KEY", "")     # For AI recommendations + playlists

# ─── LIMITS ─────────────────────────────────────────────────
DURATION_LIMIT_MIN        = int(getenv("DURATION_LIMIT", 36000))
PLAYLIST_FETCH_LIMIT      = int(getenv("PLAYLIST_FETCH_LIMIT", 2500))
SERVER_PLAYLIST_LIMIT     = int(getenv("SERVER_PLAYLIST_LIMIT", 3000))
SONG_DOWNLOAD_DURATION    = int(getenv("SONG_DOWNLOAD_DURATION", 9999999))
SONG_DOWNLOAD_DURATION_LIMIT = int(getenv("SONG_DOWNLOAD_DURATION_LIMIT", 9999999))
TG_AUDIO_FILESIZE_LIMIT   = int(getenv("TG_AUDIO_FILESIZE_LIMIT", "5242880000"))
TG_VIDEO_FILESIZE_LIMIT   = int(getenv("TG_VIDEO_FILESIZE_LIMIT", "5242880000"))

# ─── SUPPORT ────────────────────────────────────────────────
SUPPORT_CHANNEL = getenv("SUPPORT_CHANNEL", "https://t.me/YourChannel")
SUPPORT_CHAT    = getenv("SUPPORT_CHAT", "https://t.me/YourGroup")
SUPPORT_GROUP   = getenv("SUPPORT_GROUP", "https://t.me/YourGroup")
LOGGER_ID       = int(getenv("LOGGER_ID", "0"))
LOG_GROUP_ID    = int(getenv("LOG_GROUP_ID", str(OWNER_ID)))

# ─── IMAGES ─────────────────────────────────────────────────
START_IMG_URL    = getenv("START_IMG_URL", "https://files.catbox.moe/9orx6x.jpg")
PING_IMG_URL     = getenv("PING_IMG_URL", "https://files.catbox.moe/410ebd.jpg")
STREAM_IMG_URL   = getenv("STREAM_IMG_URL", "https://files.catbox.moe/5ni0on.jpg")
YOUTUBE_IMG_URL  = getenv("YOUTUBE_IMG_URL", "https://files.catbox.moe/5ni0on.jpg")
SPOTIFY_ARTIST_IMG_URL   = getenv("SPOTIFY_ARTIST_IMG_URL", "https://files.catbox.moe/5ni0on.jpg")
SPOTIFY_ALBUM_IMG_URL    = getenv("SPOTIFY_ALBUM_IMG_URL", "https://files.catbox.moe/5ni0on.jpg")
SPOTIFY_PLAYLIST_IMG_URL = getenv("SPOTIFY_PLAYLIST_IMG_URL", "https://files.catbox.moe/5ni0on.jpg")
PLAYLIST_IMG_URL = "https://files.catbox.moe/hqhh0n.jpg"
STATS_IMG_URL    = "https://files.catbox.moe/hqhh0n.jpg"
TELEGRAM_AUDIO_URL = getenv("TELEGRAM_AUDIO_URL", "https://files.catbox.moe/5ni0on.jpg")
TELEGRAM_VIDEO_URL = getenv("TELEGRAM_VIDEO_URL", "https://files.catbox.moe/5ni0on.jpg")
TELEGRAM_VID_URL = "https://files.catbox.moe/5ni0on.jpg"
SOUNCLOUD_IMG_URL = "https://files.catbox.moe/5ni0on.jpg"
STATS_VID_URL    = "https://files.catbox.moe/diotfk.mp4"

# ─── MISC ───────────────────────────────────────────────────
AUTO_LEAVING_ASSISTANT    = bool(getenv("AUTO_LEAVING_ASSISTANT", True))
AUTO_LEAVE_ASSISTANT_TIME = int(getenv("AUTO_LEAVE_ASSISTANT_TIME", 3600))
UPSTREAM_REPO  = getenv("UPSTREAM_REPO", "")
UPSTREAM_BRANCH = getenv("UPSTREAM_BRANCH", "main")
GIT_TOKEN = getenv("GIT_TOKEN", "")
ERROR_FORMAT = getenv("ERROR_FORMAT", str(OWNER_ID))
FIND_GROUP_ID = int(getenv("FIND_GROUP_ID", "0"))
YOU_MUSIC_GROUP_ID = int(getenv("YOU_MUSIC_GROUP_ID", "0"))
YOUR_API_URL = getenv("YOUR_API_URL", "http://localhost:8080")
TEMP_DB_FOLDER = "tempdb"
INSTAGRAM = getenv("INSTAGRAM", "")
GITHUB = getenv("GITHUB", "")
DONATE = getenv("DONATE", "")
PRIVACY_LINK = getenv("PRIVACY_LINK", "")

# ─── DYNAMIC FILTERS ────────────────────────────────────────
BANNED_USERS = filters.user()
adminlist    = {}
lyrical      = {}
votemode     = {}
autoclean    = []
confirmer    = {}



def time_to_seconds(time):
    stringt = str(time)
    return sum(int(x) * 60**i for i, x in enumerate(reversed(stringt.split(":"))))

DURATION_LIMIT = int(time_to_seconds(f"{DURATION_LIMIT_MIN}:00"))

# Validate WEBAPP_URL
if WEBAPP_URL:
    WEBAPP_URL = WEBAPP_URL.strip().rstrip("/")
    if not WEBAPP_URL.startswith(("http://", "https://")):
        WEBAPP_URL = f"http://{WEBAPP_URL}"

HEROKU_APP_NAME = getenv("HEROKU_APP_NAME", None)
HEROKU_API_KEY = getenv("HEROKU_API_KEY", None)
