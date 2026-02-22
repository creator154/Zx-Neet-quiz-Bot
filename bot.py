import os
import sqlite3
from telegram import Update, Poll
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    PollAnswerHandler,
)

TOKEN = os.getenv("BOT_TOKEN")

# ---------------- DATABASE ----------------
conn = sqlite3.connect("quiz.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS quiz (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    poll_id TEXT,
    user_id INTEGER,
    username TEXT,
    score INTEGER
)
""")

conn.commit()

# ---------------- COMMANDS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bot working ✅\n\n"
        "Private me /create se quiz banao\n"
        "Group me /quiz se start karo"
    )


async def create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.message.reply_text("Quiz sirf private me create karo.")
        return

    await update.message.reply_text(
        "Is format me bhejo:\n\n"
        "Question | opt1 | opt2 | opt3 | opt4 | correct(0-3) | timer(seconds)"
    )


async def save_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return

    if "|" not in update.message.text:
        return

    try:
        data = update.message.text.split("|")
        cursor.execute("""
        INSERT INTO quiz (question,opt1,opt2,opt3,opt4,correct,timer)
        VALUES (?,?,?,?,?,?,?)
        """, (
            data[0].strip(),
            data[1].strip(),
            data[2].strip(),
            data[3].strip(),
            data[4].strip(),
            int(data[5].strip()),
            int(data[6].strip())
        ))
        conn.commit()

        await update.message.reply_text("Quiz saved ✅")
    except:
        await update.message.reply_text("Format galat hai ❌")


async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT * FROM quiz ORDER BY RANDOM() LIMIT 1")
    q = cursor.fetchone()

    if not q:
        await update.message.reply_text("No quiz found ❌")
        return

    poll = await update.message.reply_poll(
        question=q[1],
        options=[q[2], q[3], q[4], q[5]],
        type=Poll.QUIZ,
        correct_option_id=q[6],
        open_period=q[7],
        is_anonymous=False
    )

    context.bot_data[poll.poll.id] = q[6]


async def answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll_id = update.poll_answer.poll_id
    user = update.poll_answer.user
    selected = update.poll_answer.option_ids[0]

    correct = context.bot_data.get(poll_id)

    if correct is None:
        return

    if selected == correct:
        cursor.execute("""
        INSERT INTO scores VALUES (?,?,?,?)
        """, (poll_id, user.id, user.username, 1))
        conn.commit()


# ---------------- APP ----------------

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("create", create))
app.add_handler(CommandHandler("quiz", quiz))
app.add_handler(PollAnswerHandler(answer))

app.run_polling()
