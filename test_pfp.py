import asyncio
import os
import sys

# Mocking or importing what we need
# We want to test get_profile_photos and download_media
async def test_pfp_fetch():
    try:
        from shakky import app
        from shakky.core.userbot import userbot
        
        await app.start()
        await userbot.start()
        
        bot_client = app
        ass_client = userbot.one
        
        test_id = bot_client.me.id
        print(f"Testing with Bot ID: {test_id}")
        
        # Test bot client
        print("Testing Bot Client...")
        found = False
        async for p in bot_client.get_profile_photos(test_id, limit=1):
            print(f"Found photo: {p}")
            dl = await bot_client.download_media(p, file_name="bot_pfp_test.jpg")
            print(f"Downloaded to: {dl}")
            found = True
            break
        if not found: print("Bot client failed to find its own photo.")
        
        # Test assistant client
        print("\nTesting Assistant Client...")
        found = False
        async for p in ass_client.get_profile_photos(test_id, limit=1):
            print(f"Found photo via Assistant: {p}")
            dl = await ass_client.download_media(p, file_name="ass_pfp_test.jpg")
            print(f"Downloaded to: {dl}")
            found = True
            break
        if not found: print("Assistant client failed to find bot's photo.")
        
        await app.stop()
        await userbot.stop()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_pfp_fetch())
