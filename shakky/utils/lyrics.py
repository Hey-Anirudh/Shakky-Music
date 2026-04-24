import aiohttp
import asyncio
import time
import logging
import re

LOGGER = logging.getLogger(__name__)

async def fetch_lrc(title: str):
    """
    Fetch synchronized lyrics (LRC) from lrclib.net.
    Returns a list of tuples (seconds, text).
    """
    url = f"https://lrclib.net/api/search?q={title}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    results = await response.json()
                    if not results:
                        return None
                    
                    # Try to find a result with synced lyrics
                    for result in results:
                        if result.get("syncedLyrics"):
                            return parse_lrc(result["syncedLyrics"])
    except Exception as e:
        LOGGER.error(f"LRC Fetch Error: {e}")
    return None

def parse_lrc(lrc_content: str):
    """
    Parse LRC format into a list of (seconds, text).
    """
    lyrics = []
    lines = lrc_content.split('\n')
    for line in lines:
        # Match [mm:ss.xx] text
        match = re.match(r'\[(\d+):(\d+\.\d+)\](.*)', line)
        if match:
            minutes = int(match.group(1))
            seconds = float(match.group(2))
            text = match.group(3).strip()
            if text:
                total_seconds = minutes * 60 + seconds
                lyrics.append((total_seconds, text))
    return sorted(lyrics, key=lambda x: x[0])
