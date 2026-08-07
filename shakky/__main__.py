import os
os.environ["PYTGCALLS_IMPLEMENTATION"] = os.getenv("PYTGCALLS_IMPLEMENTATION", "native")
os.environ["NTGCALLS"] = "1"

import logging
import asyncio
import importlib
import signal
import config
from shakky import LOGGER, app
logger = logging.getLogger("shakky")
from shakky.core.call import Nand
from shakky.misc import sudo
from shakky.plugins import ALL_MODULES
from shakky.utils.database import get_banned_users, get_gbanned, get_gmuted_users
from config import BANNED_USERS, GMUTED_USERS


async def init():
    """
    Music Bot Initialization.
    """
    stop_event = asyncio.Event()

    # Register Ctrl+C / Ctrl+Break / SIGTERM handlers so the bot actually
    # exits (works on Windows AND Linux — loop.add_signal_handler does not
    # exist on Windows). NOTE: uvicorn runs with handle_signals=False (see
    # shakky/server.py) so these handlers are the single owner of the signals.
    def _stop(*_):
        stop_event.set()

    for _sig in (signal.SIGINT, signal.SIGTERM, getattr(signal, "SIGBREAK", None)):
        if _sig is None:
            continue
        try:
            signal.signal(_sig, _stop)
            LOGGER("shakky").info(f"Signal handler registered: {_sig.name}")
        except (ValueError, OSError) as e:
            LOGGER("shakky").warning(f"Could not register {_sig}: {e}")

    # Immediate Cleanup on Start
    try:
        from shakky.utils.cleanup import run_cleanup_now
        await run_cleanup_now()
        LOGGER("shakky").info("Boot-time cleanup of downloads folder successful.")
    except Exception as e:
        LOGGER("shakky").warning(f"Boot-time cleanup failed: {e}")

    # Load Sudoers & Banned Users
    await sudo()
    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_gmuted_users()
        for user_id in users:
            GMUTED_USERS.add(user_id)
    except:
        pass

    # Start Bot Client + everything else inside try/finally so Ctrl+C at
    # ANY point (including the long startup) logs and cleans up properly.
    cleanup_task = None
    try:
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

        # Start PyTgCalls instances
        await Nand.start()
        
        from shakky.platforms import YouTube
        await YouTube.initialize()
        
        await Nand.decorators()
        
        # Start Periodic Cleanup (every 30m)
        from shakky.utils.cleanup import start_cleaning
        cleanup_task = asyncio.create_task(start_cleaning())
        LOGGER("shakky").info("Background cleanup task started (runs every 30m).")

        LOGGER("shakky").info("Music Bot Started as Shakky Music Bot")
        
        await stop_event.wait()
    except (KeyboardInterrupt, SystemExit):
        LOGGER("shakky").info("Stop signal received locally. Shutting down...")
    finally:
        # Cleanup
        LOGGER("shakky").info("Cleaning up and stopping clients...")
        if cleanup_task is not None:
            cleanup_task.cancel()

        async def _stop_clients():
            await app.stop()
            from shakky import userbot
            await userbot.stop()
            # Stop PyTgCalls engine
            await asyncio.wait_for(Nand.stop(), timeout=10)

        try:
            await asyncio.wait_for(_stop_clients(), timeout=15)
        except Exception as e:
            LOGGER("shakky").warning(f"Error during shutdown cleanup: {e}")

        # Final Force Exit to prevent hanging on Windows/VPS.
        # Deliberately no awaits guard it, so it always runs.
        LOGGER("shakky").info("Exiting...")
        os._exit(0)
    
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(init())
    except KeyboardInterrupt:
        pass
    finally:
        os._exit(0)
