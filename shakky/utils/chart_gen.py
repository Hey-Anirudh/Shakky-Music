import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import textwrap

def create_chart_card(chat_title: str, top_songs: list, top_dj: str, top_listener: str):
    """
    Generates a premium 'Aura' style chart card.
    top_songs: list of (title, play_count)
    """
    # Create canvas (1280x720)
    width, height = 1280, 720
    # Create a deep gradient background
    base = Image.new('RGB', (width, height), (15, 15, 25))
    draw = ImageDraw.Draw(base)
    
    # Draw some abstract 'Aura' gradients
    for i in range(width):
        r = int(20 + (i / width) * 40)
        g = int(10 + (i / width) * 20)
        b = int(40 + (i / width) * 60)
        draw.line([(i, 0), (i, height)], fill=(r, g, b))

    # Add a glassmorphism overlay
    overlay = Image.new('RGBA', (width - 100, height - 100), (255, 255, 255, 15))
    base.paste(overlay, (50, 50), overlay)
    
    # Fonts (assuming standard fonts or fallback)
    try:
        font_title = ImageFont.truetype("arial.ttf", 60)
        font_header = ImageFont.truetype("arial.ttf", 40)
        font_text = ImageFont.truetype("arial.ttf", 30)
    except:
        font_title = font_header = font_text = ImageFont.load_default()

    # Draw Header
    draw.text((100, 80), "🏆 WEEKLY GROUP CHARTS", fill=(255, 215, 0), font=font_title)
    draw.text((100, 150), f"Group: {chat_title}", fill=(200, 200, 200), font=font_header)
    
    draw.line([(100, 220), (1180, 220)], fill=(255, 255, 255, 50), width=2)

    # Draw Top Songs
    draw.text((100, 250), "🔥 TOP 5 TRACKS", fill=(255, 100, 100), font=font_header)
    y_offset = 320
    for i, (title, count) in enumerate(top_songs, 1):
        display_title = textwrap.shorten(title, width=50, placeholder="...")
        draw.text((120, y_offset), f"{i}. {display_title}", fill=(255, 255, 255), font=font_text)
        draw.text((1000, y_offset), f"{count} Plays", fill=(150, 150, 255), font=font_text)
        y_offset += 50

    # Draw Special Status
    draw.line([(100, 600), (1180, 600)], fill=(255, 255, 255, 50), width=2)
    
    draw.text((100, 630), f"👑 TOP DJ: {top_dj}", fill=(255, 255, 255), font=font_text)
    draw.text((700, 630), f"👂 TOP LISTENER: {top_listener}", fill=(255, 255, 255), font=font_text)

    # Save
    out_path = f"downloads/chart_{int(time.time())}.png"
    base.save(out_path)
    return out_path

import time
