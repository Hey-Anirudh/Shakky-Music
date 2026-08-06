import aiohttp
import json

from config import GROQ_API_KEY
GROQ_MODEL = "llama-3.1-8b-instant"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

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