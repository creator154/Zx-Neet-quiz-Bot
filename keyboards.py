from telegram import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    KeyboardButtonPollType,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

def poll_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(
            text="Create a question",
            request_poll=KeyboardButtonPollType(type="quiz")
        )]],
        resize_keyboard=True
    )

def finish_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add Question", callback_data="add_q"),
            InlineKeyboardButton("✅ Finish & Publish", callback_data="finish")
        ]
    ])

def timer_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("10 sec", callback_data="timer_10"),
            InlineKeyboardButton("20 sec", callback_data="timer_20"),
            InlineKeyboardButton("30 sec", callback_data="timer_30"),
        ],
        [
            InlineKeyboardButton("45 sec", callback_data="timer_45"),
            InlineKeyboardButton("60 sec", callback_data="timer_60"),
        ]
    ])

def yes_no_keyboard(prefix):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Yes", callback_data=f"{prefix}_yes"),
            InlineKeyboardButton("No", callback_data=f"{prefix}_no"),
        ]
    ])
