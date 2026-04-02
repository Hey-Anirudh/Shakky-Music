import aiohttp
import json
import random

import os
from config import GROQ_API_KEY
GROQ_MODEL = "llama-3.1-8b-instant"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

async def get_groq_playlist(mood_query: str):
    """Get a list of 50 songs from Groq based on mood"""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Prompt to get 50 songs as a comma-separated list
    prompt = (f"Act as a professional music curator. Generate a list of exactly 50 diverse songs (Title - Artist) for the mood: '{mood_query}'. "
              "Do not include any intro, numbers, or notes. Just return the song titles separated by semicolons (;). "
              "Make sure to include a mix of popular hits and deep cuts.")

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": "You are a professional music librarian."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.8, # Different playlist each time
        "max_tokens": 1500
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(GROQ_URL, headers=headers, data=json.dumps(payload)) as response:
                if response.status == 200:
                    data = await response.json()
                    content = data["choices"][0]["message"]["content"]
                    # Split by semicolon and clean up
                    songs = [s.strip() for s in content.split(";") if s.strip()]
                    # Ensure we have a list (sometimes LLM might use different separators)
                    if len(songs) < 5:
                        songs = [s.strip() for s in content.split("\n") if s.strip()]
                    return songs[:50]
                else:
                    return None
        except Exception as e:
            print(f"Groq API Error: {e}")
            return None

async def get_enhanced_metadata(keyword: str):
    """
    Uses Groq API to get high-quality song title and thumbnail URL for a keyword.
    Returns (title, thumbnail_url)
    """
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        prompt = f"""
        Act as a music metadata expert. For the search query "{keyword}", provide the most likely official song title and a high-quality relevant square image URL (from a reliable source like i.scdn.co or images.genius.com).
        Respond ONLY in valid JSON format like this:
        {{"title": "Song Name - Artist", "thumbnail": "https://example.com/image.jpg"}}
        """

        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": "You are a professional music librarian."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(GROQ_URL, headers=headers, data=json.dumps(payload)) as response:
                if response.status == 200:
                    data = await response.json()
                    result = json.loads(data["choices"][0]["message"]["content"])
                    return result.get("title", keyword.title()), result.get("thumbnail", "https://files.catbox.moe/5ni0on.jpg")
                else:
                    return keyword.title(), "https://files.catbox.moe/5ni0on.jpg"

    except Exception as e:
        print(f"Groq API error in get_enhanced_metadata: {e}")
        return keyword.title(), "https://files.catbox.moe/5ni0on.jpg"


async def get_song_recommendation(last_song_title: str):
    """
    Get a single song recommendation from Groq based on the last played song.
    """
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        prompt = f"Act as a professional music curator. Based on the song '{last_song_title}', recommend exactly one similar popular song. Reply ONLY with 'Song Title - Artist'. No other text."

        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": "You are a professional music librarian."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.5
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(GROQ_URL, headers=headers, data=json.dumps(payload)) as response:
                if response.status == 200:
                    data = await response.json()
                    content = data["choices"][0]["message"]["content"].strip().replace('"', '')
                    return content
                else:
                    return None

    except Exception as e:
        print(f"Groq API error in get_song_recommendation: {e}")
        return None
