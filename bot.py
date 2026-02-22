import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

users = {}

@bot.message_handler(commands=['start'])
def start(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Create Quiz ✏️", callback_data="create"))
    bot.send_message(
        message.chat.id,
        "This bot will help you create a quiz with a series of multiple choice questions.",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    user_id = call.from_user.id

    if call.data == "create":
        users[user_id] = {"step": "question", "options": []}
        bot.send_message(call.message.chat.id, "Send your question:")

    elif call.data.startswith("correct_"):
        users[user_id]["correct"] = int(call.data.split("_")[1])

        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("10 sec", callback_data="time_10"),
            InlineKeyboardButton("15 sec", callback_data="time_15"),
            InlineKeyboardButton("30 sec", callback_data="time_30"),
            InlineKeyboardButton("45 sec", callback_data="time_45"),
        )
        bot.send_message(call.message.chat.id, "Select timer ⏳", reply_markup=markup)

    elif call.data.startswith("time_"):
        seconds = int(call.data.split("_")[1])
        data = users[user_id]

        bot.send_poll(
            chat_id=call.message.chat.id,
            question=data["question"],
            options=data["options"],
            type="quiz",
            correct_option_id=data["correct"],
            is_anonymous=False,
            open_period=seconds
        )

        bot.send_message(call.message.chat.id, "Quiz Sent ✅")
        del users[user_id]

@bot.message_handler(func=lambda m: m.from_user.id in users)
def text_handler(message):
    user_id = message.from_user.id
    data = users[user_id]

    if data["step"] == "question":
        data["question"] = message.text
        data["step"] = "options"
        bot.send_message(message.chat.id, "Send option 1:")

    elif data["step"] == "options":
        data["options"].append(message.text)

        if len(data["options"]) < 4:
            bot.send_message(message.chat.id, f"Send option {len(data['options'])+1}:")
        else:
            markup = InlineKeyboardMarkup(row_width=2)
            markup.add(
                InlineKeyboardButton("Option 1", callback_data="correct_0"),
                InlineKeyboardButton("Option 2", callback_data="correct_1"),
                InlineKeyboardButton("Option 3", callback_data="correct_2"),
                InlineKeyboardButton("Option 4", callback_data="correct_3"),
            )
            bot.send_message(message.chat.id, "Select correct answer:", reply_markup=markup)

print("Bot Running...")
bot.infinity_polling()
