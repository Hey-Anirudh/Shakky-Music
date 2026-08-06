from pyrogram import filters

from shakky import app
from shakky.utils.inlinequery import answer
from config import BANNED_USERS


@app.on_inline_query(~BANNED_USERS)
async def inline_controls(_, query):
    if len(query.query.strip()) > 50:
        return
    await query.answer(
        results=answer,
        cache_time=10,
        is_personal=True,
    )
