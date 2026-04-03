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
            
            # Place YT image in the center wanted poster area
            # Estimated coordinates for the center poster in the provided stencil
            # Poster is roughly at [360, 240] to [580, 600] in a 1920x1080 context?
            # Let's scale based on actual image size.
            
            # Target area for the portrait:
            # We'll put it roughly in the middle, slightly offset for the One Piece look
            target_w = int(width * 0.22)
            target_h = int(height * 0.28)
            yt_img = yt_img.resize((target_w, target_h), Image.LANCZOS)
            
            # Position: Middle poster frame
            pos_x = int(width * 0.38)
            pos_y = int(height * 0.26)
            
            stencil.paste(yt_img, (pos_x, pos_y))

        # 4. Text Overlays
        draw = ImageDraw.Draw(stencil)
        
        # We try to load a font, fallback to default
        try:
            # You might need to provide a .ttf file on the VPS or use a system font
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if not os.path.exists(font_path):
                font_path = "arial.ttf" # Windows fallback
            
            title_font = ImageFont.truetype(font_path, int(height * 0.05))
            info_font = ImageFont.truetype(font_path, int(height * 0.03))
        except:
            title_font = ImageFont.load_default()
            info_font = ImageFont.load_default()

        # Draw Title (centered bottom)
        clean_title = (title[:25] + '...') if len(title) > 25 else title
        text_color = (60, 40, 20) # Brownish like the wanted poster
        
        # Position Title on the center poster's name area
        draw.text((int(width*0.4), int(height*0.62)), clean_title.upper(), font=title_font, fill=text_color)
        
        # Draw Duration & Requested By
        draw.text((int(width*0.4), int(height*0.71)), f"DUR: {duration}", font=info_font, fill=text_color)
        draw.text((int(width*0.4), int(height*0.75)), f"REQ: {by[:15]}", font=info_font, fill=text_color)

        # 5. Save
        stencil.save(output_path, "JPEG", quality=85)
        
        # Cleanup raw YT thumb
        if yt_thumb_path and os.path.exists(yt_thumb_path):
            os.remove(yt_thumb_path)
            
        return output_path

    except Exception as e:
        LOGGER.error(f"Error generating thumbnail: {e}")
        return "https://files.catbox.moe/5ni0on.jpg"
