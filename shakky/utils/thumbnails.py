# Thumbnail generation logic for Shakky Music
# Design: Stencil + Heavy Smoke + Two Circular PFPs (Requester & Bot) + Song Info

import os
import io
import math
import aiohttp
import aiofiles
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import logging

LOGGER = logging.getLogger(__name__)

STENCIL_PATH = "static/stencil.jpg"
THUMB_CACHE = "downloads/thumbs"

os.makedirs(THUMB_CACHE, exist_ok=True)


def _make_circle(img: Image.Image, size: int) -> Image.Image:
    """Resize image to a perfect circle with anti-aliased mask."""
    img = img.convert("RGBA").resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size - 1, size - 1), fill=255)
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(img, (0, 0), mask)
    return result


def _draw_circle_shadow(canvas: Image.Image, cx: int, cy: int, r: int, blur: int = 16, color=(0, 0, 0, 180)):
    """Draw a blurred circular drop shadow at position (cx, cy) with radius r."""
    shadow_size = (r * 2 + blur * 4, r * 2 + blur * 4)
    shadow = Image.new("RGBA", shadow_size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    pad = blur * 2
    sd.ellipse((pad, pad, pad + r * 2, pad + r * 2), fill=color)
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
    canvas.paste(shadow, (cx - r - pad, cy - r - pad), shadow)


async def _fetch_image(url: str, cache_path: str) -> str | None:
    """Download image to cache_path, return path or None on failure."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as resp:
                if resp.status == 200:
                    async with aiofiles.open(cache_path, "wb") as f:
                        await f.write(await resp.read())
                    return cache_path
    except Exception as e:
        LOGGER.warning(f"Failed to fetch image {url}: {e}")
    return None


async def get_thumb(videoid, title, duration, by, chat_id, user_id=None):
    """
    Generates a custom wanted-poster style thumbnail.
    - Stencil base with heavy smoke overlay
    - Two circular profile pictures (requester & bot) in the center with shadows
    - Song info text below
    """
    output_path = os.path.join(THUMB_CACHE, f"{videoid}_{chat_id}.jpg")

    # Return cached version if it exists
    if os.path.isfile(output_path):
        return output_path

    try:
        # ── 1. Load Stencil ──────────────────────────────────────────────────────
        if not os.path.exists(STENCIL_PATH):
            return "https://files.catbox.moe/5ni0on.jpg"

        stencil = Image.open(STENCIL_PATH).convert("RGBA")
        width, height = stencil.size

        # ── 2. Heavy Smoke Overlay ───────────────────────────────────────────────
        # Multi-layer smoke for depth: base dark haze + brownish vignette
        smoke1 = Image.new("RGBA", stencil.size, (10, 5, 2, 130))  # deep dark haze
        smoke2 = Image.new("RGBA", stencil.size, (35, 18, 8, 70))  # warm brownish tint
        stencil = Image.alpha_composite(stencil, smoke1)
        stencil = Image.alpha_composite(stencil, smoke2)

        # Radial "torch light" brighten in center to make PFPs pop
        radial = Image.new("RGBA", stencil.size, (0, 0, 0, 0))
        rd = ImageDraw.Draw(radial)
        cx_r, cy_r = width // 2, int(height * 0.45)
        for i in range(80, 0, -1):
            alpha = int(30 * (1 - i / 80))
            rd.ellipse(
                (cx_r - i * 3, cy_r - i * 2, cx_r + i * 3, cy_r + i * 2),
                fill=(255, 230, 180, alpha)
            )
        stencil = Image.alpha_composite(stencil, radial)

        # ── 3. Fetch Profile Pictures ────────────────────────────────────────────
        pfp_size = int(min(width, height) * 0.22)  # circle diameter

        # Requester PFP (from Telegram by user_id)
        req_pfp = None
        if user_id:
            try:
                from shakky import app as bot_app
                photos = await bot_app.get_profile_photos(int(user_id), limit=1)
                if photos.photos:
                    pfp_bytes = await bot_app.download_media(photos.photos[0][0], in_memory=True)
                    req_pfp = Image.open(io.BytesIO(pfp_bytes.getvalue())).convert("RGBA")
            except Exception as e:
                LOGGER.warning(f"Could not fetch requester PFP: {e}")

        # Fallback requester: blue gradient circle
        if req_pfp is None:
            req_pfp = Image.new("RGBA", (pfp_size, pfp_size), (70, 130, 200, 255))

        # Bot PFP (from Telegram)
        bot_pfp = None
        try:
            from shakky import app as bot_app
            me = await bot_app.get_me()
            photos = await bot_app.get_profile_photos(me.id, limit=1)
            if photos.photos:
                pfp_bytes = await bot_app.download_media(photos.photos[0][0], in_memory=True)
                bot_pfp = Image.open(io.BytesIO(pfp_bytes.getvalue())).convert("RGBA")
        except Exception as e:
            LOGGER.warning(f"Could not fetch bot PFP: {e}")

        # Fallback bot PFP: gold gradient circle
        if bot_pfp is None:
            bot_pfp = Image.new("RGBA", (pfp_size, pfp_size), (200, 160, 50, 255))

        # ── 4. Circular Crop the PFPs ────────────────────────────────────────────
        req_circ = _make_circle(req_pfp, pfp_size)
        bot_circ = _make_circle(bot_pfp, pfp_size)

        # ── 5. Positions: Both centered, side by side in the middle ─────────────
        gap = int(pfp_size * 0.25)  # gap between the two circles
        total_w = pfp_size * 2 + gap
        start_x = (width - total_w) // 2
        pfp_y = int(height * 0.28)  # vertical center position

        req_cx = start_x + pfp_size // 2
        req_cy = pfp_y + pfp_size // 2
        bot_cx = start_x + pfp_size + gap + pfp_size // 2
        bot_cy = req_cy

        # ── 6. Draw Shadows behind each circle ───────────────────────────────────
        _draw_circle_shadow(stencil, req_cx, req_cy, pfp_size // 2, blur=18, color=(0, 0, 0, 200))
        _draw_circle_shadow(stencil, bot_cx, bot_cy, pfp_size // 2, blur=18, color=(0, 0, 0, 200))

        # ── 7. Draw Glowing Border Ring ──────────────────────────────────────────
        border_thickness = max(4, pfp_size // 16)
        for circ_x, circ_y in [(req_cx, req_cy), (bot_cx, bot_cy)]:
            ring = Image.new("RGBA", stencil.size, (0, 0, 0, 0))
            ring_d = ImageDraw.Draw(ring)
            bx0 = circ_x - pfp_size // 2 - border_thickness
            by0 = circ_y - pfp_size // 2 - border_thickness
            bx1 = circ_x + pfp_size // 2 + border_thickness
            by1 = circ_y + pfp_size // 2 + border_thickness
            # Outer gold glow ring
            ring_d.ellipse((bx0, by0, bx1, by1), fill=(220, 180, 80, 180))
            # Inner slightly smaller white ring
            inner = border_thickness // 2
            ring_d.ellipse(
                (bx0 + inner, by0 + inner, bx1 - inner, by1 - inner),
                fill=(255, 245, 200, 220)
            )
            ring_blur = ring.filter(ImageFilter.GaussianBlur(3))
            stencil = Image.alpha_composite(stencil, ring_blur)

        # ── 8. Paste the Circular PFPs ───────────────────────────────────────────
        stencil.paste(req_circ, (start_x, pfp_y), req_circ)
        stencil.paste(bot_circ, (start_x + pfp_size + gap, pfp_y), bot_circ)

        # ── 9. Text Overlay ──────────────────────────────────────────────────────
        stencil_rgb = stencil.convert("RGB")
        draw = ImageDraw.Draw(stencil_rgb)

        try:
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if not os.path.exists(font_path):
                font_path = "arial.ttf"
            title_font  = ImageFont.truetype(font_path, int(height * 0.052))
            info_font   = ImageFont.truetype(font_path, int(height * 0.036))
            label_font  = ImageFont.truetype(font_path, int(height * 0.028))
        except Exception:
            title_font = info_font = label_font = ImageFont.load_default()

        text_color     = (255, 240, 200)   # warm cream  – readable on dark smoke
        shadow_color   = (0, 0, 0)

        def draw_text_shadowed(pos, text, font, color=text_color):
            draw.text((pos[0] + 2, pos[1] + 2), text, font=font, fill=shadow_color)
            draw.text(pos, text, font=font, fill=color)

        # "VS" divider label between the two circles
        vs_x = start_x + pfp_size + gap // 2
        vs_y = pfp_y + pfp_size // 2 - int(height * 0.025)
        draw_text_shadowed((vs_x - 10, vs_y), "⚡", info_font, color=(255, 210, 50))

        # Requester label under left circle
        req_label = f"@{by[:10]}"
        bbox = draw.textbbox((0, 0), req_label, font=label_font)
        lw = bbox[2] - bbox[0]
        draw_text_shadowed((start_x + (pfp_size - lw) // 2, pfp_y + pfp_size + 4), req_label, label_font)

        # Bot label under right circle
        bot_label = "Shakky 🎵"
        bbox2 = draw.textbbox((0, 0), bot_label, font=label_font)
        bw = bbox2[2] - bbox2[0]
        draw_text_shadowed(
            (start_x + pfp_size + gap + (pfp_size - bw) // 2, pfp_y + pfp_size + 4),
            bot_label, label_font, color=(220, 180, 80)
        )

        # Song title — centered, below PFPs
        clean_title = (title[:22] + "…") if len(title) > 22 else title
        title_y = pfp_y + pfp_size + int(height * 0.09)
        t_bbox = draw.textbbox((0, 0), clean_title.upper(), font=title_font)
        t_w = t_bbox[2] - t_bbox[0]
        draw_text_shadowed(((width - t_w) // 2, title_y), clean_title.upper(), title_font)

        # Duration + requestor line
        info_text = f"🕐 {duration}  •  🎤 {by[:12]}"
        i_bbox = draw.textbbox((0, 0), info_text, font=info_font)
        i_w = i_bbox[2] - i_bbox[0]
        info_y = title_y + int(height * 0.07)
        draw_text_shadowed(((width - i_w) // 2, info_y), info_text, info_font, color=(200, 185, 150))

        # ── 10. Save ─────────────────────────────────────────────────────────────
        stencil_rgb.save(output_path, "JPEG", quality=88)
        return output_path

    except Exception as e:
        LOGGER.error(f"Error generating thumbnail: {e}", exc_info=True)
        return "https://files.catbox.moe/5ni0on.jpg"
