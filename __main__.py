import asyncio
import os
from pyrogram import idle
from shakky import app, LOGGER
from shakky.core.call import Nand
from shakky.core.userbot import userbot

async def main():
    # Start all 5 assistant userbots
    await userbot.start()
    
    # Start PyTgCalls instances
    await Nand.one.start()
    for attr in ["two", "three", "four", "five"]:
        instance = getattr(Nand, attr, None)
        if instance:
            try:
                await instance.start()
            except:
                pass
    
    # Initialize YouTube API (SmashMusic: starts Telegram clients)
    from shakky.platforms import YouTube
    await YouTube.initialize()
    
    LOGGER(__name__).info("Bot Started Successfully")
    
    # Start main bot
    await app.start()
    await idle()
    os._exit(0)

if __name__ == "__main__":
    asyncio.run(main())
