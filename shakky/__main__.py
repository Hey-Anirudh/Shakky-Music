import logging
import asyncio
import importlib
import signal
from pyrogram import idle
import config
from shakky import LOGGER, app
logger = logging.getLogger("shakky")
from shakky.core.call import Nand
from shakky.misc import sudo
from shakky.plugins import ALL_MODULES
from shakky.utils.database import get_banned_users, get_gbanned
from config import BANNED_USERS


async def shutdown(sig, loop):
    """Cleanup tasks tied to its shutdown."""
    LOGGER("shakky").info(f"Received exit signal {sig.name}...")
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    LOGGER("shakky").info(f"Cancelling {len(tasks)} outstanding tasks")
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()


async def init():
    """
    WebApp-Only Bot Initialization.
    No Voice Chat engine — audio plays in the browser Mini App.
    """
    # Load Sudoers & Banned Users
    await sudo()
    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except:
        pass

    # Start Bot Client
    await app.start()

    # Load Plugins
    for all_module in ALL_MODULES:
        importlib.import_module("shakky.plugins" + all_module)
    LOGGER("shakky.plugins").info("WebApp Bot Modules Loaded.")

    # Start Assistant (needed for "find" downloads via @VKmusicTopbot)
    try:
        from shakky import userbot
        await userbot.start()
        LOGGER("shakky").info("Assistant started (for music downloads).")
    except Exception as e:
        LOGGER("shakky").warning(f"Assistant start failed (yt-dlp fallback only): {e}")

    # Start WebApp Streaming Server
    webapp_task = None
    try:
        from shakky.server import start_webapp_server
        webapp_task = asyncio.create_task(start_webapp_server())
        LOGGER("shakky").info(f"WebApp Player Server listening on port {config.WEBAPP_PORT}...")
    except Exception as e:
        LOGGER("shakky").error(f"Failed to start WebApp: {e}")

    # Start PyTgCalls instances
    await Nand.start()
    
    from shakky.platforms import YouTube
    await YouTube.initialize()
    
    await Nand.decorators()
    
    LOGGER("shakky").info("Music Bot Started as Shakky Music Bot")
    
    await idle()
    
    # Cleanup
    if webapp_task:
        webapp_task.cancel()
        try:
            await webapp_task
        except asyncio.CancelledError:
            pass

    await app.stop()
    from shakky import userbot
    await userbot.stop()
    
if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())
