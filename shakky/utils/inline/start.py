from pyrogram.types import InlineKeyboardButton

import config
from shakky import app


def start_panel(_):
    buttons = [
        [
            InlineKeyboardButton(
                text=f"{(_['S_B_11'])}", url=f"https://t.me/{app.username}?startgroup=true"
            ),
            InlineKeyboardButton(text=f"{(_['S_B_2'])}", url=config.SUPPORT_CHANNEL),
        ],
    ]
    return buttons


def private_panel(_):
    buttons = [
        [
            InlineKeyboardButton(
                text=f"{(_['S_B_3'])}",
                url=f"https://t.me/{app.username}?startgroup=true",
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{(_['S_B_10'])}",
                url=f"https://t.me/{config.OWNER_USERNAME.replace('@', '')}"
            ),
            InlineKeyboardButton(text=f"{(_['S_B_6'])}", url=config.SUPPORT_CHAT),
        ],
        [
            InlineKeyboardButton(text=f"{(_['S_B_4'])}", callback_data="open_help"),
        ],
    ]
    return buttons
