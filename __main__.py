import asyncio
import os
import signal

from shakky import app, LOGGER
from shakky.core.call import Nand
from shakky.core.userbot import userbot

_log = LOGGER(__name__)


async def shutdown():
    _log.info("Shutting down...")
    tasks = []
    for attr in ["one", "two", "three", "four", "five"]:
        instance = getattr(Nand, attr, None)
        if instance:
            tasks.append(instance.stop())
    tasks.extend([userbot.stop(), app.stop()])
    try:
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=10)
    except asyncio.TimeoutError:
        _log.warning("Graceful shutdown timed out; forcing exit.")
    _log.info("Stopped. Bye!")
    os._exit(0)


async def main():
    await userbot.start()

    for attr in ["one", "two", "three", "four", "five"]:
        instance = getattr(Nand, attr, None)
        if instance:
            try:
                await instance.start()
            except Exception:
                pass

    from shakky.platforms import YouTube
    await YouTube.initialize()

    _log.info("Bot Started Successfully")

    await app.start()

    stop_event = asyncio.Event()

    def _stop(*_):
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM, getattr(signal, "SIGBREAK", None)):
        if sig is None:
            continue
        try:
            signal.signal(sig, _stop)
        except (ValueError, OSError):
            pass

    await stop_event.wait()
    await shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        asyncio.run(shutdown())
