import socket
import time

import heroku3
from pyrogram import filters

import config
from shakky.core.mongo import mongodb

from .logging import LOGGER

SUDOERS = filters.user()

HAPP = None
_boot_ = time.time()


def is_heroku():
    return "heroku" in socket.getfqdn()


XCB = [
    "/",
    "@",
    ".",
    "com",
    ":",
    "git",
    "heroku",
    "push",
    str(config.HEROKU_API_KEY),
    "https",
    str(config.HEROKU_APP_NAME),
    "HEAD",
    "master",
]


# 🧠 ULTIMATE DATABASE: Global dictionary for music queues
# Initialized here at module level to ensure a consistent Singleton reference.
db = {}
# Tracks the last played song title for Groq recommendations
last_played = {}
# Tracks if AI-Recommend-Only mode is enabled for a chat
ai_mode = {}

def dbb():
    # Only logs now, never re-assigns the 'db' variable to avoid stale references.
    LOGGER(__name__).info(f"ᴅᴀᴛᴀʙᴀsᴇ sʏɴᴄ ᴠᴇʀɪғɪᴇᴅ 💗")


async def sudo():
    global SUDOERS
    SUDOERS.add(config.OWNER_ID)
    sudoersdb = mongodb.sudoers
    sudoers = await sudoersdb.find_one({"sudo": "sudo"})
    sudoers = [] if not sudoers else sudoers["sudoers"]
    if config.OWNER_ID not in sudoers:
        sudoers.append(config.OWNER_ID)
        await sudoersdb.update_one(
            {"sudo": "sudo"},
            {"$set": {"sudoers": sudoers}},
            upsert=True,
        )
    if sudoers:
        for user_id in sudoers:
            SUDOERS.add(user_id)
    LOGGER(__name__).info(f"sᴜᴅᴏ ᴜsᴇʀs ᴅᴏɴᴇ..")


def heroku():
    global HAPP
    if is_heroku:
        if config.HEROKU_API_KEY and config.HEROKU_APP_NAME:
            try:
                Heroku = heroku3.from_key(config.HEROKU_API_KEY)
                HAPP = Heroku.app(config.HEROKU_APP_NAME)
                LOGGER(__name__).info(f"ʜᴇʀᴏᴋᴜ ᴀᴘᴘ ᴄᴏɴғɪɢᴜʀᴇᴅ..")
            except BaseException:
                LOGGER(__name__).warning(
                    f"ʏᴏᴜ sʜᴏᴜʟᴅ ʜᴀᴠᴇ ɴᴏᴛ ғɪʟʟᴇᴅ ʜᴇʀᴏᴋᴜ ᴀᴘᴘ ɴᴀᴍᴇ ᴏʀ ᴀᴘɪ ᴋᴇʏ ᴄᴏʀʀᴇᴄᴛʟʏ ᴘʟᴇᴀsᴇ ᴄʜᴇᴄᴋ ɪᴛ...")
