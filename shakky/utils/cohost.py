import os
import asyncio
import random
import edge_tts
from shakky.utils.groq import GROQ_API_KEY, GROQ_MODEL, GROQ_URL
import aiohttp
import json
import logging

LOGGER = logging.getLogger(__name__)

# Database for co-host settings (Simplified for now, will add to database.py later)
cohost_chats = {}

async def generate_cohost_script(title: str, requester_name: str):
    """
    Generate a fun radio-style announcement or roast for the next song.
    """
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""
    Act as Shakky, a cool, slightly mysterious bar owner from One Piece. 
    The next song coming up in your bar is '{title}', requested by '{requester_name}'.
    
    Give a short, punchy introduction (max 20 words). 
    If the song title sounds 'basic' or 'bad', give a playful roast to the requester.
    Otherwise, make a cool radio-style announcement.
    
    Stay in character as Shakky. Do not use emoji. Just the spoken text.
    """

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": "You are Shakky from One Piece, a professional and witty bar owner."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.8,
        "max_tokens": 100
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(GROQ_URL, headers=headers, data=json.dumps(payload)) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    return f"Up next, {title} for {requester_name}."
        except Exception as e:
            LOGGER.error(f"Groq Cohost Error: {e}")
            return f"Next up is {title}."

async def text_to_speech(text: str, chat_id: int):
    """
    Convert text to speech using edge-tts.
    Returns the path to the generated mp3 file.
    """
    try:
        output_dir = os.path.join(os.getcwd(), "cache", "cohost")
        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, f"intro_{chat_id}.mp3")
        
        # Use a cool mature female voice for Shakky
        communicate = edge_tts.Communicate(text, "en-US-MichelleNeural")
        await communicate.save(file_path)
        
        return file_path
    except Exception as e:
        LOGGER.error(f"TTS Error: {e}")
        return None
