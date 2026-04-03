# Thumbnail generation logic for Shakky Music
# Uses a stencil image and composites YouTube metadata onto it.

import os
import aiohttp
import aiofiles
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import logging

LOGGER = logging.getLogger(__name__)

STENCIL_PATH = "static/stencil.jpg"
THUMB_CACHE = "downloads/thumbs"

os.makedirs(THUMB_CACHE, exist_ok=True)

async def get_thumb(videoid, title, duration, by, chat_id):
    """Generates a custom wanted-poster style thumbnail."""
    output_path = os.path.join(THUMB_CACHE, f"{videoid}_{chat_id}.jpg")
    
    # If already generated, return it
    if os.path.isfile(output_path):
        return output_path

    try:
        # 1. Load Stencil
        if not os.path.exists(STENCIL_PATH):
            # Fallback if stencil missing
            return "https://files.catbox.moe/5ni0on.jpg"
        
        stencil = Image.open(STENCIL_PATH).convert("RGB")
        width, height = stencil.size

        # 2. Fetch YT Thumbnail
        yt_thumb_url = f"https://img.youtube.com/vi/{videoid}/mqdefault.jpg"
        yt_thumb_path = os.path.join(THUMB_CACHE, f"raw_{videoid}.jpg")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(yt_thumb_url) as resp:
                if resp.status == 200:
                    f = await aiofiles.open(yt_thumb_path, mode='wb')
                    await f.write(await resp.read())
                    await f.close()
                else:
                    yt_thumb_path = None

        # 3. Composite
        if yt_thumb_path and os.path.exists(yt_thumb_path):
            yt_img = Image.open(yt_thumb_path).convert("RGBA")
            
            # Scale slightly larger as requested
            target_w = int(width * 0.22)
            target_h = int(height * 0.28)
            yt_img = yt_img.resize((target_w, target_h), Image.LANCZOS)
            
            # Curve edges
            rad = 12
            mask = Image.new("L", yt_img.size, 0)
            draw_m = ImageDraw.Draw(mask)
            draw_m.rounded_rectangle([(0,0), yt_img.size], radius=rad, fill=255)
            yt_img.putalpha(mask)
            
            pos_x = int(width * 0.388)
            pos_y = int(height * 0.35)
            
            # Generate drop shadow
            shadow = Image.new("RGBA", (target_w + 30, target_h + 30), (0,0,0,0))
            shadow_draw = ImageDraw.Draw(shadow)
            shadow_draw.rounded_rectangle([(10, 10), (target_w + 20, target_h + 20)], radius=rad, fill=(0, 0, 0, 180))
            from PIL import ImageFilter
            shadow = shadow.filter(ImageFilter.GaussianBlur(8))
            
            # Smoke Alpha Blend
            smoke_overlay = Image.new("RGBA", stencil.size, (20, 10, 5, 85))  # Brownish vintage smoke
            stencil = Image.alpha_composite(stencil.convert("RGBA"), smoke_overlay)
            
            # Paste shadow then image
            stencil.paste(shadow, (pos_x - 15, pos_y - 15), shadow)
            stencil.paste(yt_img, (pos_x, pos_y), yt_img)

        # 4. Text Overlays
        stencil = stencil.convert("RGB")
        draw = ImageDraw.Draw(stencil)
        
        try:
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if not os.path.exists(font_path):
                font_path = "arial.ttf"
            
            title_font = ImageFont.truetype(font_path, int(height * 0.050))
            info_font = ImageFont.truetype(font_path, int(height * 0.038))
        except:
            title_font = ImageFont.load_default()
            info_font = ImageFont.load_default()

        # Clean title for layout
        clean_title = (title[:20] + '...') if len(title) > 20 else title
        text_color = (25, 12, 5) # Darker wanted ink
        
        # Dead or Alive section placement
        title_y = int(height * 0.65)
        draw.text((int(width * 0.400), title_y), clean_title.upper(), font=title_font, fill=text_color)
        
        # Bounty / Info placement
        info_y = int(height * 0.71)
        draw.text((int(width * 0.405), info_y), f"DUR: {duration} | VIP: {by[:8]}", font=info_font, fill=text_color)

        # 5. Save
        stencil.save(output_path, "JPEG", quality=85)
        
        # Cleanup raw YT thumb
        if yt_thumb_path and os.path.exists(yt_thumb_path):
            os.remove(yt_thumb_path)
            
        return output_path

    except Exception as e:
        LOGGER.error(f"Error generating thumbnail: {e}")
        return "https://files.catbox.moe/5ni0on.jpg"
