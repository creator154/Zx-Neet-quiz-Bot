from telegram import ReplyKeyboardMarkup, KeyboardButton, KeyboardButtonPollType, InlineKeyboardMarkup, InlineKeyboardButton

def poll_keyboard():
    keyboard = [
        [KeyboardButton(text="Create a question", request_poll=KeyboardButtonPollType(type="quiz"))]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def finish_keyboard():
    keyboard = [[InlineKeyboardButton("✅ Finish & Publish", callback_data="finish")]]
    return InlineKeyboardMarkup(keyboard)

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

def shuffle_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Yes", callback_data="shuffle_yes"),
            InlineKeyboardButton("No", callback_data="shuffle_no")
        ]
    ])
