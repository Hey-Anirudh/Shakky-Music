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
            yt_img = Image.open(yt_thumb_path).convert("RGB")
            
            # The central Luffy poster portrait in 735x420 collage is approx:
            # x: 295, y: 155, w: 145, h: 105
            # We scale relative to actual image size just in case:
            target_w = int(width * 0.197)
            target_h = int(height * 0.25)
            yt_img = yt_img.resize((target_w, target_h), Image.LANCZOS)
            
            pos_x = int(width * 0.40)
            pos_y = int(height * 0.36)
            
            # Add a slight dark border to blend it in
            border = Image.new("RGB", (target_w + 4, target_h + 4), (40, 25, 15))
            border.paste(yt_img, (2, 2))
            
            stencil.paste(border, (pos_x - 2, pos_y - 2))

        # 4. Text Overlays
        draw = ImageDraw.Draw(stencil)
        
        try:
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if not os.path.exists(font_path):
                font_path = "arial.ttf"
            
            title_font = ImageFont.truetype(font_path, int(height * 0.045))
            info_font = ImageFont.truetype(font_path, int(height * 0.035))
        except:
            title_font = ImageFont.load_default()
            info_font = ImageFont.load_default()

        # Clean title for layout
        clean_title = (title[:22] + '...') if len(title) > 22 else title
        text_color = (48, 28, 13) # Very dark brown, perfectly matching wanted ink
        
        # Dead or Alive section placement
        title_y = int(height * 0.64)
        draw.text((int(width * 0.405), title_y), clean_title.upper(), font=title_font, fill=text_color)
        
        # Bounty / Info placement
        info_y = int(height * 0.70)
        draw.text((int(width * 0.41), info_y), f"DUR: {duration}  |  BY: {by[:10]}", font=info_font, fill=text_color)

        # 5. Save
        stencil.save(output_path, "JPEG", quality=85)
        
        # Cleanup raw YT thumb
        if yt_thumb_path and os.path.exists(yt_thumb_path):
            os.remove(yt_thumb_path)
            
        return output_path

    except Exception as e:
        LOGGER.error(f"Error generating thumbnail: {e}")
        return "https://files.catbox.moe/5ni0on.jpg"
