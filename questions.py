from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

user_data = {}

def register_handlers(bot):

    @bot.message_handler(commands=['createquiz'])
    def create_quiz(message):
        user_data[message.from_user.id] = {
            "step": "question",
            "options": []
        }
        bot.send_message(message.chat.id, "Send your Question:")

    @bot.message_handler(func=lambda m: m.from_user.id in user_data)
    def text_handler(message):
        user_id = message.from_user.id
        data = user_data[user_id]

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
                data["step"] = "correct"
                bot.send_message(message.chat.id, "Select Correct Answer:", reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.from_user.id in user_data)
    def callback_handler(call):
        user_id = call.from_user.id
        data = user_data[user_id]

        if call.data.startswith("correct_"):
            data["correct"] = int(call.data.split("_")[1])

            markup = InlineKeyboardMarkup(row_width=2)
            markup.add(
                InlineKeyboardButton("10 sec", callback_data="timer_10"),
                InlineKeyboardButton("15 sec", callback_data="timer_15"),
                InlineKeyboardButton("30 sec", callback_data="timer_30"),
                InlineKeyboardButton("45 sec", callback_data="timer_45"),
            )

            data["step"] = "timer"
            bot.send_message(call.message.chat.id, "Select Timer:", reply_markup=markup)

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
            del user_data[user_id]
