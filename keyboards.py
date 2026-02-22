from telegram import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    KeyboardButtonPollType,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

def poll_keyboard():
    keyboard = [
        [KeyboardButton(
            text="Create a question",
            request_poll=KeyboardButtonPollType(type="quiz")
        )]
    ]
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )

def finish_keyboard():
    keyboard = [
        [InlineKeyboardButton("✅ Finish & Publish", callback_data="finish")]
    ]
    return InlineKeyboardMarkup(keyboard)
