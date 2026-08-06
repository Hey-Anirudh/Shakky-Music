# Thumbnail generation logic for Shakky Music
# Design: Airbuds-style card — pink gradient, rounded dark panel,
# album art on the left, song title + artist on the right.

import os
import io
import asyncio
import hashlib
import aiohttp
import aiofiles
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import logging
from concurrent.futures import ThreadPoolExecutor

LOGGER = logging.getLogger(__name__)

# Shared thread pool for CPU-bound PIL work (4 workers max)
_thumb_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="thumb")

# Shared aiohttp session (initialized lazily)
_http_session = None

async def _get_session():
    global _http_session
    if _http_session is None or _http_session.closed:
        _http_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8))
    return _http_session

THUMB_CACHE = "downloads/thumbs"

os.makedirs(THUMB_CACHE, exist_ok=True)

# Airbuds card font
FONT_PATH = "static/fonts/BricolageGrotesque-Bold.ttf"

# Card geometry (1280x720)
WIDTH = 1280
HEIGHT = 720
CARD = (90, 110, 1170, 590)
ALBUM_SIZE = 320
ALBUM_POS = (150, 190)
TITLE_POS = (540, 255)
ARTIST_POS = (545, 385)
TITLE_FONT_SIZE = 80
ARTIST_FONT_SIZE = 40
MAX_TEXT_WIDTH = 520

GRADIENT_TOP = (255, 80, 160)
GRADIENT_BOTTOM = (240, 40, 120)
CARD_COLOR = (10, 10, 10)
ARTIST_COLOR = (180, 180, 180)

# Different gradient palettes — a song's hash picks one so every thumbnail
# gets its own background color set.
GRADIENT_PALETTES = [
    ((255, 80, 160), (240, 40, 120)),   # classic pink
    ((120, 80, 255), (40, 20, 180)),    # violet
    ((80, 180, 255), (20, 60, 220)),    # blue
    ((255, 120, 60), (220, 40, 40)),    # orange-red
    ((80, 220, 140), (20, 120, 90)),    # green
    ((255, 200, 60), (220, 80, 20)),    # amber
    ((180, 80, 255), (100, 20, 160)),   # purple
    ((60, 220, 220), (20, 100, 180)),   # teal
    ((255, 90, 120), (160, 30, 90)),    # rose
    ((160, 200, 255), (70, 90, 200)),   # steel
]


def _gradient_for(videoid: str):
    """Deterministic palette choice per song (stable across re-renders)."""
    h = hashlib.md5(str(videoid or "music").encode("utf-8", "ignore")).hexdigest()
    idx = int(h[:8], 16) % len(GRADIENT_PALETTES)
    return GRADIENT_PALETTES[idx]


def _make_gradient(width: int, height: int, top, bottom) -> Image.Image:
    """Vertical gradient background."""
    bg = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(bg)
    for y in range(height):
        ratio = y / height
        r = int(top[0] + (bottom[0] - top[0]) * ratio)
        g = int(top[1] + (bottom[1] - top[1]) * ratio)
        b = int(top[2] + (bottom[2] - top[2]) * ratio)
        draw.line((0, y, width, y), fill=(r, g, b))
    return bg


def _fit_album(thumb_bytes, size: int, gradient: tuple) -> Image.Image:
    """Crop & resize album art to a rounded square.

    Always fills the square — if no artwork bytes are available a matching
    gradient placeholder is drawn so no empty space remains.
    """
    album = None
    if thumb_bytes:
        try:
            album = Image.open(io.BytesIO(thumb_bytes)).convert("RGB")
            album = ImageOps.fit(album, (size, size), method=Image.Resampling.LANCZOS)
        except Exception:
            album = None

    if album is None:
        top, bottom = gradient
        album = _make_gradient(size, size, top, bottom)
        mask_tmp = ImageDraw.Draw(album)
        mask_tmp.ellipse((size // 4, size // 4, size * 3 // 4, size * 3 // 4), fill=(245, 245, 245))

    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((0, 0, size, size), radius=35, fill=255)

    result = Image.new("RGB", (size, size), CARD_COLOR)
    result.paste(album, (0, 0), mask)
    return result


def _fit_text(draw, text, font, max_width):
    """Shrink a string until it fits the max width."""
    while True:
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] <= max_width:
            return text
        text = text[:-1]


def _render_thumb(thumb_bytes: bytes, title: str, artist: str, output_path: str, gradient: tuple) -> str:
    """CPU-bound PIL rendering."""
    top, bottom = gradient
    bg = _make_gradient(WIDTH, HEIGHT, top, bottom).convert("RGBA")

    # Blurred shadow behind the card
    shadow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((110, 130, 1190, 610), radius=60, fill=(0, 0, 0, 100))
    shadow = shadow.filter(ImageFilter.GaussianBlur(25))
    bg = Image.alpha_composite(bg, shadow)

    # Dark card
    draw = ImageDraw.Draw(bg)
    draw.rounded_rectangle(CARD, radius=60, fill=CARD_COLOR)

    # Album art (always fills the square)
    try:
        album = _fit_album(thumb_bytes, ALBUM_SIZE, gradient)
        bg.paste(album, ALBUM_POS)
    except Exception as e:
        LOGGER.warning(f"Album paste failed: {e}")

    draw = ImageDraw.Draw(bg)

    try:
        font_path = FONT_PATH if os.path.exists(FONT_PATH) else "arial.ttf"
        title_font = ImageFont.truetype(font_path, TITLE_FONT_SIZE)
        artist_font = ImageFont.truetype(font_path, ARTIST_FONT_SIZE)
    except Exception:
        title_font = artist_font = ImageFont.load_default()

    clean_title = _fit_text(draw, title or "Unknown", title_font, MAX_TEXT_WIDTH)
    clean_artist = _fit_text(draw, artist or "Unknown", artist_font, MAX_TEXT_WIDTH)

    draw.text(TITLE_POS, clean_title, fill="white", font=title_font)
    draw.text(ARTIST_POS, clean_artist, fill=ARTIST_COLOR, font=artist_font)

    out = bg.convert("RGB")
    out.save(output_path, "JPEG", quality=95)
    return output_path


async def _download_thumb_bytes(url: str) -> bytes | None:
    """Download thumbnail bytes using shared session."""
    try:
        session = await _get_session()
        async with session.get(url) as r:
            if r.status == 200:
                return await r.read()
    except Exception as e:
        LOGGER.warning(f"Thumb download failed {url}: {e}")
    return None


async def get_thumb(videoid, title, duration, by, chat_id, user_id=None):
    """
    Generates an Airbuds-style thumbnail card.
      - Pink gradient background with a blurred dark panel
      - Rounded album art on the left
      - Song title + artist on the right
    The card is cached per (videoid, chat_id). Returns the local path.
    """
    output_path = os.path.join(THUMB_CACHE, f"{videoid}_{chat_id}.jpg")
    if os.path.isfile(output_path):
        return output_path

    try:
        # Album art from the YouTube video thumbnail
        thumb_url = f"https://i.ytimg.com/vi/{videoid}/hqdefault.jpg"
        thumb_bytes = await _download_thumb_bytes(thumb_url)
        if not thumb_bytes:
            # Solid placeholder album block
            thumb_bytes = b""

        artist = str(by or "")
        gradient = _gradient_for(videoid)

        def _render():
            return _render_thumb(thumb_bytes, title, artist, output_path, gradient)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_thumb_executor, _render)
        return result

    except Exception as e:
        LOGGER.error(f"Error generating thumbnail: {e}", exc_info=True)
        return f"https://i.ytimg.com/vi/{videoid}/hqdefault.jpg"
