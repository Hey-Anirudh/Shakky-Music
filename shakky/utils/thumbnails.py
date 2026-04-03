# Thumbnail generation logic for Shakky Music
# Design: Stencil + Heavy Smoke + Two Circular PFPs (Requester & Bot) + Song Info
# Uses SVG-style flat icons (downloaded PNG) instead of emoji

import os
import io
import aiohttp
import aiofiles
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import logging

LOGGER = logging.getLogger(__name__)

STENCIL_PATH = "static/stencil.jpg"
THUMB_CACHE = "downloads/thumbs"

os.makedirs(THUMB_CACHE, exist_ok=True)

# Flat SVG-style icon URLs (small transparent PNGs from a reliable CDN)
ICON_MUSIC   = "https://cdn-icons-png.flaticon.com/64/727/727218.png"   # music note
ICON_CLOCK   = "https://cdn-icons-png.flaticon.com/64/2088/2088617.png" # clock
ICON_USER    = "https://cdn-icons-png.flaticon.com/64/1077/1077012.png" # person silhouette


# ─────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────

def _make_circle(img: Image.Image, size: int) -> Image.Image:
    """Crop & resize to a perfect anti-aliased circle."""
    img = img.convert("RGBA").resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(img, (0, 0), mask)
    return result


def _draw_shadow_ring(canvas: Image.Image, cx: int, cy: int, r: int):
    """Blurred black drop shadow behind the circle."""
    blur = 20
    pad  = blur * 2
    s = Image.new("RGBA", (r * 2 + pad * 2, r * 2 + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(s).ellipse((pad, pad, pad + r * 2, pad + r * 2), fill=(0, 0, 0, 210))
    s = s.filter(ImageFilter.GaussianBlur(blur))
    canvas.paste(s, (cx - r - pad, cy - r - pad), s)


def _draw_glow_ring(canvas: Image.Image, cx: int, cy: int, r: int, thick: int):
    """Glowing gold ring border around the circle."""
    ring = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d    = ImageDraw.Draw(ring)
    x0, y0 = cx - r - thick, cy - r - thick
    x1, y1 = cx + r + thick, cy + r + thick
    d.ellipse((x0, y0, x1, y1), fill=(230, 190, 70, 200))           # gold outer
    d.ellipse((x0 + thick, y0 + thick, x1 - thick, y1 - thick), fill=(0, 0, 0, 0))  # hollow
    ring = ring.filter(ImageFilter.GaussianBlur(4))
    canvas.alpha_composite(ring)


async def _download_to_disk(url: str, path: str) -> bool:
    """Download URL to disk. Returns True on success."""
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status == 200:
                    async with aiofiles.open(path, "wb") as f:
                        await f.write(await r.read())
                    return True
    except Exception as e:
        LOGGER.warning(f"Download failed {url}: {e}")
    return False


async def _get_tg_pfp(tg_client, user_id: int, cache_name: str) -> Image.Image | None:
    """
    Download a Telegram profile/chat photo using Pyrogram 2 async iteration.
    Returns PIL Image or None.
    """
    if not tg_client: return None
    
    cache_path = os.path.join(THUMB_CACHE, cache_name)
    if os.path.exists(cache_path):
        try:
            return Image.open(cache_path).convert("RGBA")
        except Exception:
            pass

    try:
        photo = None
        # Pyrogram 2 uses get_chat_photos for both users and groups
        async for p in tg_client.get_chat_photos(user_id, limit=1):
            photo = p
            break

        if photo is None:
            return None

        # Download to a temp path
        tmp = cache_path + ".tmp"
        dl = await tg_client.download_media(photo, file_name=tmp)
        if dl and os.path.exists(tmp):
            if os.path.exists(cache_path): os.remove(cache_path)
            os.rename(tmp, cache_path)
            return Image.open(cache_path).convert("RGBA")
    except Exception as e:
        # LOGGER.warning(f"Could not fetch PFP for {user_id}: {e}")
        pass

    return None


async def _load_icon(url: str, size: int, cache_name: str, tint=None) -> Image.Image | None:
    """Download a flat PNG icon, tint it, resize to (size x size)."""
    cache_path = os.path.join(THUMB_CACHE, cache_name)
    if not os.path.exists(cache_path):
        ok = await _download_to_disk(url, cache_path)
        if not ok:
            return None
    try:
        icon = Image.open(cache_path).convert("RGBA").resize((size, size), Image.LANCZOS)
        if tint:
            # Colour the icon (keep alpha, recolour RGB)
            r, g, b, a = icon.split()
            coloured = Image.new("RGBA", icon.size, tint)
            coloured.putalpha(a)
            return coloured
        return icon
    except Exception as e:
        LOGGER.warning(f"Icon load failed: {e}")
        return None


def _text_shadow(draw, pos, text, font, fill, shadow=(0, 0, 0)):
    draw.text((pos[0] + 2, pos[1] + 2), text, font=font, fill=shadow)
    draw.text(pos, text, font=font, fill=fill)


# ─────────────────────────────────────────────────────────────────
# main entry point
# ─────────────────────────────────────────────────────────────────

async def get_thumb(videoid, title, duration, by, chat_id, user_id=None):
    """
    Generates a custom wanted-poster style thumbnail.
      - Stencil base + heavy multi-layer smoke
      - Two circular PFPs (requester left, bot right) with shadows & gold glow rings
      - SVG-style flat icon badges for music note & clock
      - Song title + duration text with drop shadows
    """
    output_path = os.path.join(THUMB_CACHE, f"{videoid}_{chat_id}.jpg")
    if os.path.isfile(output_path):
        return output_path

    try:
        # ── 1. Load Stencil ──────────────────────────────────────────────────────
        if not os.path.exists(STENCIL_PATH):
            return "https://files.catbox.moe/5ni0on.jpg"

        stencil = Image.open(STENCIL_PATH).convert("RGBA")
        W, H    = stencil.size

        # ── 2. Heavy Smoke (multi-layer) ─────────────────────────────────────────
        stencil = Image.alpha_composite(stencil, Image.new("RGBA", stencil.size, (8,  4,  2, 140)))  # dark haze
        stencil = Image.alpha_composite(stencil, Image.new("RGBA", stencil.size, (40, 20, 8,  80)))  # warm tint
        stencil = Image.alpha_composite(stencil, Image.new("RGBA", stencil.size, (0,  0,  0,  40)))  # extra depth

        # Radial centre spotlight so PFPs are visible
        spot = Image.new("RGBA", stencil.size, (0, 0, 0, 0))
        sd   = ImageDraw.Draw(spot)
        cxs, cys = W // 2, int(H * 0.42)
        for i in range(90, 0, -1):
            a = int(22 * (1 - i / 90))
            sd.ellipse((cxs - i*3, cys - i*2, cxs + i*3, cys + i*2), fill=(255, 220, 160, a))
        stencil = Image.alpha_composite(stencil, spot)

        # ── 3. Get Telegram PFPs ─────────────────────────────────────────────────
        from shakky import app as bot_app
        from shakky.core.userbot import userbot as assistant_manager

        # Clients for fetching (Assistant is better for user PFPs, Bot for itself)
        ass_client = assistant_manager.one if hasattr(assistant_manager.one, "get_chat_photos") else None
        bot_client = bot_app if hasattr(bot_app, "get_chat_photos") else None
        
        pfp_size = int(min(W, H) * 0.22)

        # 👤 Fetch Requester PFP (User)
        req_img = None
        if user_id:
            # Try assistant first, then bot
            if ass_client: req_img = await _get_tg_pfp(ass_client, int(user_id), f"pfp_user_{user_id}.jpg")
            if not req_img and bot_client: req_img = await _get_tg_pfp(bot_client, int(user_id), f"pfp_user_{user_id}.jpg")

        # 🤖 Fetch Bot PFP
        bot_img = None
        # Bot can practically always get its own info via bot_client
        if bot_client:
            try:
                me = await bot_client.get_me()
                pfp_id = me.id
                bot_img = await _get_tg_pfp(bot_client, pfp_id, f"pfp_bot_{pfp_id}.jpg")
            except: pass
        if not bot_img and ass_client:
            try:
                me = await bot_client.get_me() if bot_client else await ass_client.get_me()
                bot_img = await _get_tg_pfp(ass_client, me.id, f"pfp_bot_{me.id}.jpg")
            except: pass

        # Fallback solid-colour circles if PFP unavailable
        if req_img is None:
            req_img = Image.new("RGBA", (pfp_size, pfp_size), (70, 130, 200, 255))
        if bot_img is None:
            bot_img = Image.new("RGBA", (pfp_size, pfp_size), (200, 160, 50, 255))

        # ── 4. Circular Crop ─────────────────────────────────────────────────────
        req_circ = _make_circle(req_img,  pfp_size)
        bot_circ = _make_circle(bot_img,  pfp_size)

        # ── 5. Layout: two circles centred horizontally ──────────────────────────
        gap     = int(pfp_size * 0.30)
        total_w = pfp_size * 2 + gap
        ox      = (W - total_w) // 2
        pfp_y   = int(H * 0.26)

        req_cx  = ox + pfp_size // 2
        req_cy  = pfp_y + pfp_size // 2
        bot_cx  = ox + pfp_size + gap + pfp_size // 2
        bot_cy  = req_cy

        # ── 6. Drop shadows ──────────────────────────────────────────────────────
        _draw_shadow_ring(stencil, req_cx, req_cy, pfp_size // 2)
        _draw_shadow_ring(stencil, bot_cx, bot_cy, pfp_size // 2)

        # ── 7. Glow border rings ─────────────────────────────────────────────────
        thick = max(5, pfp_size // 14)
        _draw_glow_ring(stencil, req_cx, req_cy, pfp_size // 2, thick)
        _draw_glow_ring(stencil, bot_cx, bot_cy, pfp_size // 2, thick)

        # ── 8. Paste PFPs ────────────────────────────────────────────────────────
        stencil.paste(req_circ, (ox,                       pfp_y), req_circ)
        stencil.paste(bot_circ, (ox + pfp_size + gap,      pfp_y), bot_circ)

        # ── 9. SVG-style icons (flat PNGs) as badge overlays ─────────────────────
        icon_sz = max(24, pfp_size // 5)

        music_icon = await _load_icon(ICON_MUSIC, icon_sz, "icon_music.png", tint=(230, 190, 70, 255))
        clock_icon = await _load_icon(ICON_CLOCK, icon_sz, "icon_clock.png", tint=(200, 220, 255, 255))

        # Place music icon badge on bot circle (bottom-right corner of circle)
        if music_icon:
            mi_x = ox + pfp_size + gap + pfp_size - icon_sz + 4
            mi_y = pfp_y + pfp_size - icon_sz + 4
            stencil.paste(music_icon, (mi_x, mi_y), music_icon)

        # ── 10. Convert to RGB for text ────────────────────────────────────────
        out = stencil.convert("RGB")
        draw = ImageDraw.Draw(out)

        try:
            fp = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if not os.path.exists(fp):
                fp = "arial.ttf"
            f_title = ImageFont.truetype(fp, int(H * 0.054))
            f_info  = ImageFont.truetype(fp, int(H * 0.038))
            f_label = ImageFont.truetype(fp, int(H * 0.030))
        except Exception:
            f_title = f_info = f_label = ImageFont.load_default()

        CREAM  = (255, 240, 200)
        GOLD   = (220, 180, 65)
        MUTED  = (190, 175, 145)

        # Labels under circles
        req_label = f"@{by[:12]}"
        rb = draw.textbbox((0, 0), req_label, font=f_label)
        _text_shadow(draw, (ox + (pfp_size - (rb[2]-rb[0])) // 2, pfp_y + pfp_size + 6), req_label, f_label, CREAM)

        bot_label = "Shakky Music"
        bb = draw.textbbox((0, 0), bot_label, font=f_label)
        _text_shadow(draw, (ox + pfp_size + gap + (pfp_size - (bb[2]-bb[0])) // 2, pfp_y + pfp_size + 6), bot_label, f_label, GOLD)

        # "VS" marker between
        vs_x = ox + pfp_size + gap // 2 - 6
        vs_y = pfp_y + pfp_size // 2 - int(H * 0.028)
        _text_shadow(draw, (vs_x, vs_y), "VS", f_info, GOLD)

        # Song Title — centred
        clean = (title[:24] + "...") if len(title) > 24 else title
        cb = draw.textbbox((0, 0), clean.upper(), font=f_title)
        title_y = pfp_y + pfp_size + int(H * 0.10)
        _text_shadow(draw, ((W - (cb[2]-cb[0])) // 2, title_y), clean.upper(), f_title, CREAM)

        # Duration line with clock icon inline
        if clock_icon:
            # Place clock icon inline
            clock_pil = clock_icon.resize((int(H * 0.038), int(H * 0.038)), Image.LANCZOS)
        dur_text = f"  {duration}    {by[:14]}"
        db2 = draw.textbbox((0, 0), dur_text, font=f_info)
        info_y = title_y + int(H * 0.075)
        info_x = (W - (db2[2]-db2[0])) // 2
        _text_shadow(draw, (info_x, info_y), dur_text, f_info, MUTED)
        if clock_icon:
            out.paste(clock_pil, (info_x - clock_pil.size[0] - 4, info_y), clock_pil)

        # ── 11. Save ──────────────────────────────────────────────────────────────
        out.save(output_path, "JPEG", quality=90)
        return output_path

    except Exception as e:
        LOGGER.error(f"Error generating thumbnail: {e}", exc_info=True)
        return "https://files.catbox.moe/5ni0on.jpg"
