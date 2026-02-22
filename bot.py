import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

user_states = {}

# START COMMAND
@bot.message_handler(commands=['start'])
def start(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Create Quiz ✏️", callback_data="create"))

    bot.send_message(
        message.chat.id,
        "This bot will help you create a quiz with a series of multiple choice questions.",
        reply_markup=markup
    )

# CALLBACK HANDLER
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id

    if call.data == "create":
        user_states[user_id] = {
            "step": "question",
            "options": []
        }
        bot.send_message(call.message.chat.id, "Send your Question:")

    elif call.data.startswith("correct_"):
        correct = int(call.data.split("_")[1])
        user_states[user_id]["correct"] = correct

        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("10 sec", callback_data="time_10"),
            InlineKeyboardButton("15 sec", callback_data="time_15"),
            InlineKeyboardButton("30 sec", callback_data="time_30"),
            InlineKeyboardButton("45 sec", callback_data="time_45"),
        )

        bot.send_message(call.message.chat.id, "Select Timer ⏳", reply_markup=markup)

    elif call.data.startswith("time_"):
        seconds = int(call.data.split("_")[1])
        data = user_states[user_id]

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
        del user_states[user_id]

# TEXT HANDLER
@bot.message_handler(func=lambda message: message.from_user.id in user_states)
def text_handler(message):
    user_id = message.from_user.id
    data = user_states[user_id]

    if data["step"] == "question":
        data["question"] = message.text
        data["step"] = "options"
        bot.send_message(message.chat.id, "Send Option 1:")

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

            bot.send_message(message.chat.id, "Select Correct Answer:", reply_markup=markup)

print("Bot Running...")
bot.infinity_polling()
