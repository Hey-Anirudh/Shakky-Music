import asyncio
import time

import speedtest
from pyrogram import filters
from pyrogram.types import Message

from shakky import app
from shakky.misc import SUDOERS


def _run_speedtest():
    test = speedtest.Speedtest(secure=True)
    test.get_best_server()
    server = test.results.server
    start = time.time()
    test.download()
    test.upload()
    results = test.results.dict()
    results["ping_time"] = (time.time() - start)
    return results


@app.on_message(filters.command(["speedtest", "spt"], prefixes=["/", "!", "%", ",", "", ".", "@", "#"]) & SUDOERS)
async def speedtest_function(client, message: Message):
    mystic = await message.reply_text("➲ **Running Speedtest...** (takes up to 30s)")
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _run_speedtest)
    except Exception as e:
        return await mystic.edit_text(f"❌ **Speedtest failed:** <code>{e}</code>")

    client_info = result.get("client", {})
    server_info = result.get("server", {})
    download_mbps = result.get("download", 0) / 1_000_000
    upload_mbps = result.get("upload", 0) / 1_000_000
    ping = result.get("ping", 0)

    output = (
        "➲ **SPEEDTEST RESULT**\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🖧 **ISP:** <code>{client_info.get('isp', 'N/A')}</code>\n"
        f"🌍 **Country:** <code>{client_info.get('country', 'N/A')}</code>\n"
        f"📡 **Server:** <code>{server_info.get('name', 'N/A')}</code> "
        f"({server_info.get('country', 'N/A')})\n"
        f"⚡ **Latency:** <code>{ping:.2f} ms</code>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"⬇️ **Download:** <code>{download_mbps:.2f} Mbps</code>\n"
        f"⬆️ **Upload:** <code>{upload_mbps:.2f} Mbps</code>\n"
    )
    await mystic.edit_text(output)