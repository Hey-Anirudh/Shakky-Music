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

import config

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
CARD_COLOR = (10, 10, 10)
ARTIST_COLOR = (180, 180, 180)
CHIP_BG = (15, 15, 15)
TITLE_FONT_SIZE = 56
ARTIST_FONT_SIZE = 32
SMALL_FONT_SIZE = 22
MAX_TEXT_WIDTH = 590

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

    radius = max(16, size // 5)
    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((0, 0, size, size), radius=radius, fill=255)

    result = Image.new("RGB", (size, size), CARD_COLOR)
    result.paste(album, (0, 0), mask)

    # Thin accent-colored border hugging the curved corners
    rd = ImageDraw.Draw(result)
    rd.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, outline=tuple(gradient[0]), width=4)
    return result


def _fit_text(draw, text, font, max_width):
    """Shrink a string until it fits the max width."""
    while True:
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] <= max_width:
            return text
        text = text[:-1]


def _wrap_text(draw, text, font, max_width, max_lines):
    """Word-wrap text into up to max_lines lines; last line gets an ellipsis."""
    words = str(text).split()
    if not words:
        return [""]
    lines, current = [], ""
    for w in words:
        trial = (current + " " + w).strip()
        if not current or draw.textbbox((0, 0), trial, font=font)[2] <= max_width:
            current = trial
        else:
            lines.append(current)
            current = w
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while lines and draw.textbbox((0, 0), lines[-1] + "…", font=font)[2] > max_width:
            lines[-1] = lines[-1][:-1]
        lines[-1] += "…"
    return lines or [""]


def _render_thumb(thumb_bytes: bytes, title: str, artist: str, duration: str, username: str, output_path: str, gradient: tuple) -> str:
    """CPU-bound PIL rendering."""
    top, bottom = gradient
    accent = top
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
        small_font = ImageFont.truetype(font_path, SMALL_FONT_SIZE)
        pill_font = ImageFont.truetype(font_path, 22)
    except Exception:
        title_font = artist_font = small_font = pill_font = ImageFont.load_default()

    # --- "NOW PLAYING" pill with live dot (accent = gradient top color) ---
    pill_text = "NOW PLAYING"
    psize = draw.textbbox((0, 0), pill_text, font=pill_font)
    pw = psize[2] + 48
    pill = (540, 198, 540 + pw, 240)
    draw.rounded_rectangle(pill, radius=21, fill=accent)
    draw.ellipse((554, 210, 568, 224), fill="white")
    draw.text((582, 201), pill_text, fill="white", font=pill_font)

    # --- Title (up to 2 wrapped lines) ---
    lines = _wrap_text(draw, title or "Unknown", title_font, MAX_TEXT_WIDTH, 2)
    ty = 262
    for ln in lines:
        draw.text((540, ty), ln, fill="white", font=title_font)
        ty += 66

    # --- Artist with a small playing-equalizer accent ---
    artist_text = _fit_text(draw, artist or "Unknown Artist", artist_font, MAX_TEXT_WIDTH - 60)
    eq_x = 540
    for h in (16, 26, 20):
        draw.rounded_rectangle((eq_x, ty + 4 + 26 - h, eq_x + 6, ty + 4 + 26), radius=3, fill=accent)
        eq_x += 10
    draw.text((eq_x + 6, ty + 4), artist_text, fill=ARTIST_COLOR, font=artist_font)

    # --- Progress bar + duration chip (bottom row) ---
    bar_y = 545
    bar_left, bar_right = 540, 925
    draw.rounded_rectangle((bar_left, bar_y, bar_right, bar_y + 6), radius=3, fill=(35, 35, 35))
    draw.rounded_rectangle(
        (bar_left, bar_y, bar_left + int(0.4 * (bar_right - bar_left)), bar_y + 6),
        radius=3,
        fill=accent,
    )

    dur_text = _fit_text(draw, duration or "0:00", small_font, 150)
    chip = (962, 536, 1134, 568)
    draw.rounded_rectangle(chip, radius=16, fill=CHIP_BG, outline=accent, width=2)
    tw = draw.textbbox((0, 0), dur_text, font=small_font)[2]
    draw.text((962 + (172 - tw) // 2, 539), dur_text, fill=accent, font=small_font)

    # --- Brand watermark (top-right of the card, bot username) ---
    wm = _fit_text(draw, username or "Music Bot", small_font, 560)
    ww = draw.textbbox((0, 0), wm, font=small_font)[2]
    draw.text((1130 - ww, 128), wm, fill=(150, 150, 150), font=small_font)

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
      - Gradient background with a blurred dark panel
      - Rounded album art on the left
      - "NOW PLAYING" pill, wrapped song title + artist on the right
      - Progress bar, duration chip and brand watermark
    The card is cached per (videoid, chat_id). Returns the local path.
    """
    output_path = os.path.join(THUMB_CACHE, f"{videoid}_{chat_id}_v2.jpg")
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

        # Real bot username (fetched once at runtime, cached after first call)
        username = config.BOT_USERNAME
        try:
            from shakky import app as _app
            if _app.me is None:
                await _app.get_me()
            if _app.me and _app.me.username:
                username = f"@{_app.me.username}"
        except Exception:
            pass

        def _render():
            return _render_thumb(thumb_bytes, title, artist, duration, username, output_path, gradient)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_thumb_executor, _render)
        return result

    except Exception as e:
        LOGGER.error(f"Error generating thumbnail: {e}", exc_info=True)
        return f"https://i.ytimg.com/vi/{videoid}/hqdefault.jpg"
