import os
import sqlite3
import uuid
from telegram import (
    Update, 
    Poll,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    PollAnswerHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")

# ---------------- DATABASE ----------------
conn = sqlite3.connect("quiz.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS quizzes (
    quiz_id TEXT,
    title TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS questions (
    quiz_id TEXT,
    question TEXT,
    opt1 TEXT,
    opt2 TEXT,
    opt3 TEXT,
    opt4 TEXT,
    correct INTEGER,
    timer INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS scores (
    quiz_id TEXT,
    user_id INTEGER,
    username TEXT,
    score INTEGER
)
""")
conn.commit()

# --------------- STATES ----------------
TITLE, QUESTION, OPTIONS, CORRECT, TIMER = range(5)

# --------------- CREATE QUIZ FLOW ----------------

async def newquiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send quiz title:")
    context.user_data["quiz_id"] = str(uuid.uuid4())[:8]
    return TITLE

async def get_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["title"] = update.message.text
    cursor.execute("INSERT INTO quizzes VALUES (?,?)",
                   (context.user_data["quiz_id"], update.message.text))
    conn.commit()
    await update.message.reply_text("Send question:")
    return QUESTION

async def get_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["question"] = update.message.text
    await update.message.reply_text("Send 4 options separated by |")
    return OPTIONS

async def get_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    opts = update.message.text.split("|")
    context.user_data["options"] = [o.strip() for o in opts]
    await update.message.reply_text("Send correct option number (0-3)")
    return CORRECT

async def get_correct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["correct"] = int(update.message.text)
    await update.message.reply_text("Send timer in seconds:")
    return TIMER

async def get_timer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quiz_id = context.user_data["quiz_id"]
    q = context.user_data["question"]
    o = context.user_data["options"]
    c = context.user_data["correct"]
    t = int(update.message.text)

    cursor.execute("INSERT INTO questions VALUES (?,?,?,?,?,?,?,?)",
                   (quiz_id, q, o[0], o[1], o[2], o[3], c, t))
    conn.commit()

    link = f"https://t.me/{context.bot.username}?start={quiz_id}"

    keyboard = [[InlineKeyboardButton("Add Another Question", callback_data="add")]]
    await update.message.reply_text(
        f"Question saved ✅\nShare this link:\n{link}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END

# --------------- START QUIZ ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        quiz_id = context.args[0]
        context.chat_data["quiz_id"] = quiz_id
        cursor.execute("SELECT * FROM questions WHERE quiz_id=?",
                       (quiz_id,))
        context.chat_data["questions"] = cursor.fetchall()
        context.chat_data["index"] = 0
        await send_question(update, context)

async def send_question(update, context):
    questions = context.chat_data["questions"]
    index = context.chat_data["index"]

    if index >= len(questions):
        await show_result(update, context)
        return

    q = questions[index]
    poll = await context.bot.send_poll(
        chat_id=update.effective_chat.id,
        question=q[1],
        options=[q[2], q[3], q[4], q[5]],
        type=Poll.QUIZ,
        correct_option_id=q[6],
        open_period=q[7],
        is_anonymous=False
    )

    context.bot_data[poll.poll.id] = {
        "quiz_id": q[0],
        "correct": q[6]
    }

# --------------- ANSWER TRACK ----------------

async def poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.poll_answer
    poll_id = answer.poll_id

    data = context.bot_data.get(poll_id)
    if not data:
        return

    correct = data["correct"]
    quiz_id = data["quiz_id"]

    if answer.option_ids[0] == correct:
        cursor.execute("""
        INSERT INTO scores VALUES (?,?,?,?)
        """, (quiz_id,
              answer.user.id,
              answer.user.username,
              1))
        conn.commit()

# --------------- RESULT ----------------

async def show_result(update, context):
    quiz_id = context.chat_data["quiz_id"]
    cursor.execute("""
    SELECT username, SUM(score) 
    FROM scores WHERE quiz_id=? 
    GROUP BY user_id 
    ORDER BY SUM(score) DESC
    """, (quiz_id,))
    results = cursor.fetchall()

    text = "🏆 Quiz Finished!\n\n"
    for i, r in enumerate(results, 1):
        text += f"{i}. {r[0]} - {r[1]} pts\n"

    await update.effective_chat.send_message(text)

# --------------- APP ----------------

app = ApplicationBuilder().token(TOKEN).build()

conv = ConversationHandler(
    entry_points=[CommandHandler("newquiz", newquiz)],
    states={
        TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_title)],
        QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_question)],
        OPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_options)],
        CORRECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_correct)],
        TIMER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_timer)],
    },
    fallbacks=[]
)

app.add_handler(conv)
app.add_handler(CommandHandler("start", start))
app.add_handler(PollAnswerHandler(poll_answer))

app.run_polling()
