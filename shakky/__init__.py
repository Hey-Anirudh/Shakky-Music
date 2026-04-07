import os
# Force PyTgCalls to use the native implementation (ntgcalls) instead of Node.js engine
os.environ["PYTGCALLS_IMPLEMENTATION"] = "native"
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
