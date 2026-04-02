import sys
from pyrogram import Client
import config
from shakky import LOGGER

assistants = []
assistantids = []

class Userbot:
    def __init__(self):
        self.one = Client(
            "Ass1",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING1),
            no_updates=True,
        )
        self.two = Client(
            "Ass2",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING2),
            no_updates=True,
        ) if config.STRING2 else None
        self.three = Client(
            "Ass3",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING3),
            no_updates=True,
        ) if config.STRING3 else None
        self.four = Client(
            "Ass4",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING4),
            no_updates=True,
        ) if config.STRING4 else None
        self.five = Client(
            "Ass5",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING5),
            no_updates=True,
        ) if config.STRING5 else None

    async def start(self):
        LOGGER(__name__).info(f"Starting Assistant Clients...")
        
        await self.one.start()
        assistants.append(1)
        self.one.id = self.one.me.id
        self.one.name = self.one.me.mention
        self.one.username = self.one.me.username
        assistantids.append(self.one.id)
        LOGGER(__name__).info(f"Assistant 1 started as {self.one.name}")

        if self.two:
            try:
                await self.two.start()
                assistants.append(2)
                self.two.id = self.two.me.id
                self.two.name = self.two.me.mention
                self.two.username = self.two.me.username
                assistantids.append(self.two.id)
                LOGGER(__name__).info(f"Assistant 2 started as {self.two.name}")
            except Exception as e:
                LOGGER(__name__).error(f"Failed to start Assistant 2: {e}")

        if self.three:
            try:
                await self.three.start()
                assistants.append(3)
                self.three.id = self.three.me.id
                self.three.name = self.three.me.mention
                self.three.username = self.three.me.username
                assistantids.append(self.three.id)
                LOGGER(__name__).info(f"Assistant 3 started as {self.three.name}")
            except Exception as e:
                LOGGER(__name__).error(f"Failed to start Assistant 3: {e}")

        if self.four:
            try:
                await self.four.start()
                assistants.append(4)
                self.four.id = self.four.me.id
                self.four.name = self.four.me.mention
                self.four.username = self.four.me.username
                assistantids.append(self.four.id)
                LOGGER(__name__).info(f"Assistant 4 started as {self.four.name}")
            except Exception as e:
                LOGGER(__name__).error(f"Failed to start Assistant 4: {e}")

        if self.five:
            try:
                await self.five.start()
                assistants.append(5)
                self.five.id = self.five.me.id
                self.five.name = self.five.me.mention
                self.five.username = self.five.me.username
                assistantids.append(self.five.id)
                LOGGER(__name__).info(f"Assistant 5 started as {self.five.name}")
            except Exception as e:
                LOGGER(__name__).error(f"Failed to start Assistant 5: {e}")

    async def stop(self):
        LOGGER(__name__).info(f"Stopping Assistants...")
        try:
            if config.STRING1:
                await self.one.stop()
            if config.STRING2 and self.two:
                await self.two.stop()
            if config.STRING3 and self.three:
                await self.three.stop()
            if config.STRING4 and self.four:
                await self.four.stop()
            if config.STRING5 and self.five:
                await self.five.stop()
        except:
            pass

userbot = Userbot()
