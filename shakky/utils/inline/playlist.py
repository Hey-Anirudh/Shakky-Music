from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_playlist_markup(_=None):
    buttons = [
        [
            InlineKeyboardButton("▶ Play Audio", callback_data="play_playlist a"),
            InlineKeyboardButton("▶ Play Video", callback_data="play_playlist v"),
        ],
        [
            InlineKeyboardButton("✕ Close", callback_data="close"),
        ],
    ]
    return buttons


def warning_markup(_=None):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🗑 Yes, Delete All", callback_data="delete_whole_playlist")],
            [
                InlineKeyboardButton("◀ Back", callback_data="del_back_playlist"),
                InlineKeyboardButton("✕ Close", callback_data="close"),
            ],
        ]
    )


def close_markup(_=None):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("✕ Close", callback_data="close")]]
    )