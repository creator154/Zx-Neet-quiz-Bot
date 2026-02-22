import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

user_data = {}

# START MESSAGE WITH BUTTON
@bot.message_handler(commands=['start'])
def start(message):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("Create Quiz ✏️", callback_data="create_quiz")
    )

    bot.send_message(
        message.chat.id,
        "This bot will help you create a quiz with a series of multiple choice questions.",
        reply_markup=markup
    )

# BUTTON HANDLER
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):

    user_id = call.from_user.id

    # STEP 1 - Create Quiz
    if call.data == "create_quiz":
        user_data[user_id] = {
            "step": "question",
            "options": []
        }
        bot.send_message(call.message.chat.id, "Send your Question:")

    # STEP 3 - Select Correct Option
    elif call.data.startswith("correct_"):
        data = user_data[user_id]
        data["correct"] = int(call.data.split("_")[1])

        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("10 sec", callback_data="timer_10"),
            InlineKeyboardButton("15 sec", callback_data="timer_15"),
            InlineKeyboardButton("30 sec", callback_data="timer_30"),
            InlineKeyboardButton("45 sec", callback_data="timer_45"),
        )

        data["step"] = "timer"
        bot.send_message(call.message.chat.id, "Select Timer ⏳", reply_markup=markup)

    # STEP 4 - Send Poll
    elif call.data.startswith("timer_"):
        data = user_data[user_id]
        seconds = int(call.data.split("_")[1])

        bot.send_poll(
            chat_id=call.message.chat.id,
            question=data["question"],
            options=data["options"],
            type="quiz",
            correct_option_id=data["correct"],
            is_anonymous=False,
            open_period=seconds
        )

        bot.send_message(call.message.chat.id, "Quiz Sent Successfully ✅")
        del user_data[user_id]

# TEXT HANDLER FOR QUESTION + OPTIONS
@bot.message_handler(func=lambda m: m.from_user.id in user_data)
def text_handler(message):
    user_id = message.from_user.id
    data = user_data[user_id]

    # STEP 2 - Question
    if data["step"] == "question":
        data["question"] = message.text
        data["step"] = "options"
        bot.send_message(message.chat.id, "Send Option 1:")

    # STEP 3 - Options
    elif data["step"] == "options":
        data["options"].append(message.text)

        if len(data["options"]) < 4:
            bot.send_message(message.chat.id, f"Send Option {len(data['options'])+1}:")
        else:
            markup = InlineKeyboardMarkup(row_width=2)
            markup.add(
                InlineKeyboardButton("Option 1", callback_data="correct_0"),
                InlineKeyboardButton("Option 2", callback_data="correct_1"),
                InlineKeyboardButton("Option 3", callback_data="correct_2"),
                InlineKeyboardButton("Option 4", callback_data="correct_3"),
            )

            data["step"] = "correct"
            bot.send_message(message.chat.id, "Select Correct Answer:", reply_markup=markup)

print("Bot Running...")
bot.infinity_polling()
