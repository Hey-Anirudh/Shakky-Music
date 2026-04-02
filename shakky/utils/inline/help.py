from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from shakky import app

def help_pannel(_, current_page=1):
    buttons = []
    # Music related buttons (1-11)
    # Sudo related buttons (15-19)
    include_indices = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 15, 16, 17, 18, 19]
    
    current_row = []
    for count, i in enumerate(include_indices):
        current_row.append(InlineKeyboardButton(
            text=f"{_[f'H_B_{i}']}",
            callback_data=f"help_callback hb{i}_p1"
        ))
        if len(current_row) == 2:
            buttons.append(current_row)
            current_row = []
    if current_row:
        buttons.append(current_row)
        
    navigation_buttons = [
        InlineKeyboardButton(text="• ᴍᴇɴᴜ •", callback_data="back_to_main"),
        InlineKeyboardButton(text="✧ ᴄʟᴏsᴇ ✧", callback_data="close")
    ]
    buttons.append(navigation_buttons)
    return InlineKeyboardMarkup(buttons)

def first_page(_):
    return help_pannel(_)

def second_page(_):
    return help_pannel(_)

def help_back_markup(_, current_page):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=f"{_['BACK_BUTTON']}",
                    callback_data=f"help_back_1"
                ),
                InlineKeyboardButton(
                    text=f"{_['CLOSE_BUTTON']}",
                    callback_data="close"
                ),
            ]
        ]
    )

def private_help_panel(_):
    return [
        [
            InlineKeyboardButton(
                text=f"{_[f'S_B_4']}",
                url=f"https://t.me/{app.username}?start=help"
            ),
        ],
    ]
