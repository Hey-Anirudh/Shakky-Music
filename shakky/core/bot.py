
from pyrogram import Client, errors
from pyrogram.enums import ChatMemberStatus, ParseMode
import config
from ..logging import LOGGER

class ani(Client):
    def __init__(self):
        LOGGER(__name__).info("Initializing Bot...")
        super().__init__(
            name="smashmusic",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            in_memory=True,
            max_concurrent_transmissions=7,
        )

    async def start(self):
        try:
            await super().start()
        except Exception as e:
            LOGGER(__name__).error(f"FATAL: Bot failed to start: {e}")
            import traceback
            LOGGER(__name__).error(traceback.format_exc())
            raise e
            
        self.id = self.me.id
        self.name = self.me.first_name + " " + (self.me.last_name or "")
        self.username = self.me.username
        self.mention = self.me.mention

        try:
            await self.send_message(
                chat_id=config.OWNER_ID,
                text=f"Bot started as {self.name}",
            )
        except:
            pass

        LOGGER(__name__).info(f"Music Bot Started as {self.name}")

    async def stop(self):
        await super().stop()
