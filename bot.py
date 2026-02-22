import os
import telebot
import psycopg2
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from telebot.types import InlineQueryResultArticle, InputTextMessageContent
import uuid

BOT_TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

# -------------------- DATABASE --------------------
DATABASE_URL = os.environ.get("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL, sslmode='require')
cur = conn.cursor()

# Create quizzes table if not exists
cur.execute("""
CREATE TABLE IF NOT EXISTS quizzes (
    id SERIAL PRIMARY KEY,
    creator_id BIGINT,
    question TEXT,
    option1 TEXT,
    option2 TEXT,
    option3 TEXT,
    option4 TEXT,
    correct INT,
    timer INT
)
""")
conn.commit()

# -------------------- USER STATE --------------------
user_states = {}

# -------------------- PRIVATE CHAT --------------------
@bot.message_handler(commands=['start'])
def start(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Create Quiz ✏️", callback_data="create"))
    bot.send_message(
        message.chat.id,
        "Welcome to Neet Quiz Bot!\nCreate quizzes in private, send polls to groups.",
        reply_markup=markup
    )

# -------------------- CREATE FLOW --------------------
@bot.callback_query_handler(func=lambda call: call.data == "create")
def create(call):
    user_states[call.from_user.id] = {"step": "question", "options": []}
    bot.send_message(call.message.chat.id, "Send your question:")

@bot.message_handler(func=lambda m: m.from_user.id in user_states)
def handle_text(message):
    user_id = message.from_user.id
    data = user_states[user_id]

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
            data["step"] = "correct"
            bot.send_message(message.chat.id, "Select correct answer:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("correct_"))
def handle_correct(call):
    user_id = call.from_user.id
    data = user_states[user_id]
    data["correct"] = int(call.data.split("_")[1])

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("10 sec", callback_data="timer_10"),
        InlineKeyboardButton("15 sec", callback_data="timer_15"),
        InlineKeyboardButton("30 sec", callback_data="timer_30"),
        InlineKeyboardButton("45 sec", callback_data="timer_45"),
    )
    data["step"] = "timer"
    bot.send_message(call.message.chat.id, "Select timer ⏳", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("timer_"))
def handle_timer(call):
    user_id = call.from_user.id
    data = user_states[user_id]
    seconds = int(call.data.split("_")[1])

    # Save to database
    cur.execute("""
        INSERT INTO quizzes (creator_id, question, option1, option2, option3, option4, correct, timer)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        user_id,
        data["question"],
        data["options"][0],
        data["options"][1],
        data["options"][2],
        data["options"][3],
        data["correct"],
        seconds
    ))
    conn.commit()

    bot.send_message(call.message.chat.id, "Quiz Saved ✅\nNow go to group and type:\n@Neet_Quizer_Bot")

    del user_states[user_id]

# -------------------- INLINE QUERY --------------------
@bot.inline_query_handler(func=lambda query: True)
def inline_query(query):
    cur.execute("SELECT id, question FROM quizzes WHERE creator_id=%s", (query.from_user.id,))
    quizzes = cur.fetchall()

    results = []
    for q in quizzes:
        results.append(
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title=q[1],
                description="Send this quiz",
                input_message_content=InputTextMessageContent(f"/sendquiz {q[0]}")
            )
        )

    bot.answer_inline_query(query.id, results)

# -------------------- SEND POLL IN GROUP --------------------
@bot.message_handler(commands=['sendquiz'])
def send_quiz(message):
    try:
        quiz_id = int(message.text.split()[1])
    except:
        bot.send_message(message.chat.id, "Invalid quiz ID.")
        return

    cur.execute("SELECT * FROM quizzes WHERE id=%s", (quiz_id,))
    q = cur.fetchone()

    if not q:
        bot.send_message(message.chat.id, "Quiz not found.")
        return

    bot.send_poll(
        chat_id=message.chat.id,
        question=q[2],
        options=[q[3], q[4], q[5], q[6]],
        type="quiz",
        correct_option_id=q[7],
        is_anonymous=False,
        open_period=q[8]
    )

print("Bot Running...")
bot.infinity_polling()
