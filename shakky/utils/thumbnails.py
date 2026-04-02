import os
import re
import textwrap

import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from unidecode import unidecode
from youtubesearchpython.__future__ import VideosSearch

from shakky import app
from config import YOUTUBE_IMG_URL


def changeImageSize(maxWidth, maxHeight, image):
    widthRatio = maxWidth / image.size[0]
    heightRatio = maxHeight / image.size[1]
    newWidth = int(widthRatio * image.size[0])
    newHeight = int(heightRatio * image.size[1])
    newImage = image.resize((newWidth, newHeight))
    return newImage


def clear(text):
    list = text.split(" ")
    title = ""
    for i in list:
        if len(title) + len(i) < 60:
            title += " " + i
    return title.strip()


async def get_thumb(videoid):
    if os.path.isfile(f"cache/{videoid}.png"):
        return f"cache/{videoid}.png"

    url = f"https://www.youtube.com/watch?v={videoid}"
    try:
        title = "Unsupported Title"
        duration = "Unknown Mins"
        thumbnail = YOUTUBE_IMG_URL
        views = "Unknown Views"
        channel = "Unknown Channel"
        
        results = VideosSearch(url, limit=1)
        for result in (await results.next())["result"]:
            try:
                title = result["title"]
                title = re.sub("\W+", " ", title)
                title = title.title()
            except:
                title = "Unsupported Title"
            try:
                duration = result["duration"]
            except:
                duration = "Unknown Mins"
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            try:
                views = result["viewCount"]["short"]
            except:
                views = "Unknown Views"
            try:
                channel = result["channel"]["name"]
            except:
                channel = "Unknown Channel"

        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail) as resp:
                if resp.status == 200:
                    f = await aiofiles.open(f"cache/thumb{videoid}.png", mode="wb")
                    await f.write(await resp.read())
                    await f.close()

        # Load YouTube thumbnail for background
        background = Image.open(f"cache/thumb{videoid}.png").convert("RGBA")
        background = changeImageSize(1280, 720, background)
        
        # Apply blur and darken effect to background for better readability
        background = background.filter(ImageFilter.GaussianBlur(10))
        enhancer = ImageEnhance.Brightness(background)
        background = enhancer.enhance(0.7)
        
        # Load YouTube thumbnail again for the box content
        youtube = Image.open(f"cache/thumb{videoid}.png")
        youtube = changeImageSize(400, 400, youtube)  # Size for the thumbnail box
        
        # Create translucent rectangular box in the middle
        box_width, box_height = 800, 600
        box_x = (1280 - box_width) // 2
        box_y = (720 - box_height) // 2
        
        translucent_box = Image.new('RGBA', (box_width, box_height), (0, 0, 0, 180))
        background.paste(translucent_box, (box_x, box_y), translucent_box)
        
        # Add YouTube thumbnail to the box
        thumb_x = box_x + (box_width - 400) // 2
        thumb_y = box_y + 50
        background.paste(youtube, (thumb_x, thumb_y))
        
        draw = ImageDraw.Draw(background)
        
        # Load fonts
        try:
            title_font = ImageFont.truetype("shakky/assets/font.ttf", 36)
            channel_font = ImageFont.truetype("shakky/assets/font2.ttf", 28)
            controls_font = ImageFont.truetype("shakky/assets/font2.ttf", 24)
            time_font = ImageFont.truetype("shakky/assets/font2.ttf", 22)
            watermark_font = ImageFont.truetype("shakky/assets/font2.ttf", 20)
        except:
            # Fallback to default fonts
            title_font = ImageFont.load_default()
            channel_font = ImageFont.load_default()
            controls_font = ImageFont.load_default()
            time_font = ImageFont.load_default()
            watermark_font = ImageFont.load_default()

        # Song title (below thumbnail)
        title_lines = textwrap.wrap(clear(title), width=25)
        title_y = thumb_y + 420
        for i, line in enumerate(title_lines):
            if i < 2:  # Max 2 lines
                bbox = draw.textbbox((0, 0), line, font=title_font)
                text_width = bbox[2] - bbox[0]
                text_x = box_x + (box_width - text_width) // 2
                draw.text(
                    (text_x, title_y + (i * 45)),
                    line,
                    (255, 255, 255),
                    font=title_font,
                )

        # Channel name
        channel_text = f"🎤 {channel}"
        bbox = draw.textbbox((0, 0), channel_text, font=channel_font)
        channel_width = bbox[2] - bbox[0]
        channel_x = box_x + (box_width - channel_width) // 2
        draw.text(
            (channel_x, title_y + 100),
            channel_text,
            (200, 200, 200),
            font=channel_font,
        )

        # Progress/Time bar
        progress_y = title_y + 160
        # Progress bar background
        draw.rounded_rectangle([
            (box_x + 100, progress_y), 
            (box_x + box_width - 100, progress_y + 8)
        ], radius=4, fill="#444444")
        
        # Progress bar progress
        draw.rounded_rectangle([
            (box_x + 100, progress_y), 
            (box_x + 300, progress_y + 8)
        ], radius=4, fill="#FF0000")
        
        # Time stamps
        draw.text(
            (box_x + 80, progress_y + 15),
            "00:00",
            (200, 200, 200),
            font=time_font,
        )
        draw.text(
            (box_x + box_width - 120, progress_y + 15),
            f"{duration}",
            (200, 200, 200),
            font=time_font,
        )

        # Control buttons
        controls_y = progress_y + 60
        controls_start_x = box_x + (box_width - 300) // 2
        
        # Previous button (⏮️)
        draw.text(
            (controls_start_x, controls_y),
            "⏮️",
            (255, 255, 255),
            font=controls_font,
        )
        
        # Play/Pause button (⏸️)
        draw.text(
            (controls_start_x + 100, controls_y),
            "⏸️",
            (255, 255, 255),
            font=controls_font,
        )
        
        # Next button (⏭️)
        draw.text(
            (controls_start_x + 200, controls_y),
            "⏭️",
            (255, 255, 255),
            font=controls_font,
        )

        # Watermark - @RedBotsHQ (top right, transparent)
        watermark_text = "@RedBotsHQ"
        bbox = draw.textbbox((0, 0), watermark_text, font=watermark_font)
        text_width = bbox[2] - bbox[0]
        
        # Semi-transparent background for watermark
        watermark_bg = Image.new('RGBA', (text_width + 15, 30), (0, 0, 0, 120))
        background.paste(watermark_bg, (1250 - text_width - 10, 20), watermark_bg)
        
        # Watermark text
        draw.text(
            (1250 - text_width - 5, 25),
            watermark_text,
            (255, 255, 255, 180),  # Semi-transparent white
            font=watermark_font,
        )

        # Clean up temporary files
        try:
            os.remove(f"cache/thumb{videoid}.png")
        except:
            pass
        
        background.save(f"cache/{videoid}.png")
        return f"cache/{videoid}.png"
    except Exception as e:
        print(e)
        return YOUTUBE_IMG_URL
