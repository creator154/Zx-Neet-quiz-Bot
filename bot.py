import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

user_data = {}

# START
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Use /createquiz to create poll quiz.")

# CREATE QUIZ
@bot.message_handler(commands=['createquiz'])
def create_quiz(message):
    user_data[message.from_user.id] = {
        "step": "question",
        "options": []
    }
    bot.send_message(message.chat.id, "Send your Question:")

# TEXT HANDLER
@bot.message_handler(func=lambda m: True)
def text_handler(message):
    user_id = message.from_user.id
    
    if user_id not in user_data:
        return
    
    data = user_data[user_id]

    # STEP 1 - Question
    if data["step"] == "question":
        data["question"] = message.text
        data["step"] = "options"
        bot.send_message(message.chat.id, "Send Option 1:")
    
    # STEP 2 - Options
    elif data["step"] == "options":
        data["options"].append(message.text)
        
        if len(data["options"]) < 4:
            bot.send_message(message.chat.id, f"Send Option {len(data['options'])+1}:")
        else:
            # Ask correct answer
            markup = InlineKeyboardMarkup(row_width=2)
            markup.add(
                InlineKeyboardButton("Option 1", callback_data="correct_0"),
                InlineKeyboardButton("Option 2", callback_data="correct_1"),
                InlineKeyboardButton("Option 3", callback_data="correct_2"),
                InlineKeyboardButton("Option 4", callback_data="correct_3"),
            )
            data["step"] = "correct"
            bot.send_message(message.chat.id, "Select Correct Answer:", reply_markup=markup)

# CALLBACK HANDLER
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    
    if user_id not in user_data:
        return
    
    data = user_data[user_id]

    # STEP 3 - Correct Option
    if call.data.startswith("correct_"):
        correct_index = int(call.data.split("_")[1])
        data["correct"] = correct_index
        
        # Ask timer
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("10 sec", callback_data="timer_10"),
            InlineKeyboardButton("15 sec", callback_data="timer_15"),
            InlineKeyboardButton("30 sec", callback_data="timer_30"),
            InlineKeyboardButton("45 sec", callback_data="timer_45"),
        )
        data["step"] = "timer"
        bot.send_message(call.message.chat.id, "Select Timer:", reply_markup=markup)

    # STEP 4 - Timer
    elif call.data.startswith("timer_"):
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

        # Clear user data
        del user_data[user_id]

print("Bot Running...")
bot.infinity_polling()
