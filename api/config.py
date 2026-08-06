# api/config.py
# Environment-driven config for the standalone Shakky Music fetch API.
# Nothing here touches the main bot — this service is fully self-contained.

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Server ---
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8300"))

# --- WebApp origin (optional) for CORS ---
ALLOWED_ORIGINS = os.getenv(
    "API_ALLOWED_ORIGINS", "*"
).split(",")

# --- Data dirs (kept separate from the bot's downloads/ to avoid clashes) ---
DATA_DIR = os.getenv("API_DATA_DIR", os.path.join(BASE_DIR, "data"))
DOWNLOADS_DIR = os.path.join(DATA_DIR, "downloads")
THUMBS_DIR = os.path.join(DATA_DIR, "thumbs")
for _d in (DATA_DIR, DOWNLOADS_DIR, THUMBS_DIR):
    os.makedirs(_d, exist_ok=True)

# --- Cookies -----------------------------------------------------------------
# Default: reuse the repo-root cookies.txt the bot already ships with.
# Override with YTDLP_COOKIES to point anywhere else.
_COOKIE_PROBE = os.getenv(
    "YTDLP_COOKIES",
    os.path.join(os.path.dirname(BASE_DIR), "cookies.txt"),
)
COOKIES_FILE = _COOKIE_PROBE if os.path.isfile(_COOKIE_PROBE) else ""

# --- yt-dlp tuning -----------------------------------------------------------
YTDLP_RETRIES = int(os.getenv("YTDLP_RETRIES", "3"))
YTDLP_TIMEOUT = int(os.getenv("YTDLP_TIMEOUT", "30"))
YTDLP_CONCURRENCY = int(os.getenv("YTDLP_CONCURRENCY", "4"))  # worker threads

# --- Cache TTLs (seconds) ----------------------------------------------------
STREAM_URL_TTL = int(os.getenv("API_STREAM_URL_TTL", "3600"))  # googlevideo URLs expire
METADATA_TTL = int(os.getenv("API_METADATA_TTL", "600"))

# --- Safety ------------------------------------------------------------------
MAX_PLAYLIST_ITEMS = int(os.getenv("API_MAX_PLAYLIST", "120"))
MAX_COMPRESSED_SIZE_MB = 512