import aiohttp
from bs4 import BeautifulSoup
import urllib.parse
import asyncio
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from shakky import app

TIMEOUT_SECONDS = 30

async def google_dork(dork_query, num_results):
    query = urllib.parse.quote_plus(dork_query)
    start = 0
    results = []
    total_results = "N/A"

    async with aiohttp.ClientSession() as session:
        while len(results) < num_results:
            url = f"https://www.google.com/search?q={query}&start={start}"
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                )
            }

            try:
                async with session.get(url, headers=headers, timeout=TIMEOUT_SECONDS) as response:
                    if response.status == 200:
                        text = await response.text()
                        soup = BeautifulSoup(text, "html.parser")

                        if start == 0:
                            total_results_text = soup.find('div', id='result-stats')
                            if total_results_text:
                                total_results = total_results_text.get_text()

                        for g in soup.find_all('div', class_='g'):
                            anchors = g.find_all('a')
                            if anchors:
                                link = anchors[0]['href']
                                if link not in results:
                                    results.append(link)
                                    if len(results) >= num_results:
                                        break
            except asyncio.TimeoutError:
                break

            start += 10

    return results, total_results

@app.on_message(filters.command(["dork", "stack", "search"]))
async def dork(client, message):
    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2:
        await message.reply_text(
            "🚫 Please provide a query after the command.\n\nUsage: `/dork your_query_here`"
        )
        return

    dork_query = command_parts[1].strip()
    num_results = 15

    processing_msg = await message.reply_text("**Processing your request...**")

    try:
        start_time = asyncio.get_event_loop().time()
        results, total_results = await asyncio.wait_for(google_dork(dork_query, num_results), timeout=TIMEOUT_SECONDS)
        end_time = asyncio.get_event_loop().time()

        if results:
            results_text = "\n".join([f"{i + 1}. {url}" for i, url in enumerate(results)])
            time_taken = end_time - start_time

            caption = (
                f"𝗚𝗼𝗼𝗴𝗹𝗲 𝗗𝗼𝗿𝗸 𝗥𝗲𝘀𝘂𝗹𝘁𝘀  🔍\n"
                f"𝗤𝘂𝗲𝗿𝘆: {dork_query}\n\n"
                f"{results_text}"
            )

            await processing_msg.delete()
            await message.reply_text(
                caption,
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await processing_msg.edit_text("No results found.")
    except asyncio.TimeoutError:
        await processing_msg.edit_text("Sorry, the server took too long to respond. Please try again later.")
    except Exception as e:
        await processing_msg.edit_text(f"An error occurred: {str(e)}")
