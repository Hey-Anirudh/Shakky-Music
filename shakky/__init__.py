import os
import sys
from unittest.mock import MagicMock

# 🤖 Universal Stealth Mock for tgcalls (ARM Fix)
# This prevents ModuleNotFoundError on ARM VPS even if the v3.x core is missing
if "tgcalls" not in sys.modules:
    sys.modules["tgcalls"] = MagicMock()

# Try to use Native Core (ntgcalls) by default, but allow fallbacks
os.environ["PYTGCALLS_IMPLEMENTATION"] = os.getenv("PYTGCALLS_IMPLEMENTATION", "native")
os.environ["NTGCALLS"] = "1"

from .logging import LOGGER
from shakky.core.bot import ani
from shakky.core.dir import dirr
from shakky.core.git import git
from shakky.core.userbot import Userbot
from shakky.misc import dbb, heroku

dirr()
git()
dbb()
heroku()

# start_webapp_server() is async and usually started in __main__.py, so we don't call it directly here at module level.

app = ani()
userbot = Userbot()

from .platforms import *
