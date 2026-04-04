
from pyrogram import Client, errors, utils
from pyrogram.enums import ChatMemberStatus, ParseMode
import httpx
import config
from ..logging import LOGGER

# --- MONKEYPATCHES (Stability Fixes) ---
# 1. Fix for Peer ID range issues (-1002... IDs) in older Pyrogram
_get_peer = utils.get_peer_type
def patched_get_peer_type(peer_id):
    if isinstance(peer_id, int) and peer_id < -1000000000000:
        return "channel"
    return _get_peer(peer_id)
utils.get_peer_type = patched_get_peer_type

# 2. Fix for httpx proxies vs proxy incompatibility
_orig_httpx_init = httpx.AsyncClient.__init__
def _patched_httpx_init(self, *args, **kwargs):
    if "proxies" in kwargs:
        p = kwargs.pop("proxies")
        if "proxy" not in kwargs and p:
            kwargs["proxy"] = p.get("http://") if isinstance(p, dict) else p
    return _orig_httpx_init(self, *args, **kwargs)
httpx.AsyncClient.__init__ = _patched_httpx_init
# ---------------------------------------

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
