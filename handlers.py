import json
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from database import cursor, conn
from states import WAITING_TITLE, WAITING_DESCRIPTION, WAITING_POLL
from keyboards import poll_keyboard, finish_keyboard


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "This bot will help you create a quiz.\n\nSend /create to begin."
    )


async def create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send me the title of your quiz.")
    return WAITING_TITLE


async def receive_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["title"] = update.message.text
    await update.message.reply_text("Send description or /skip")
    return WAITING_DESCRIPTION


async def skip_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["description"] = ""
    return await save_quiz(update, context)


async def receive_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["description"] = update.message.text
    return await save_quiz(update, context)


async def save_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute(
        "INSERT INTO quizzes (user_id, title, description) VALUES (?, ?, ?)",
        (update.effective_user.id,
         context.user_data["title"],
         context.user_data["description"])
    )
    conn.commit()

    context.user_data["quiz_id"] = cursor.lastrowid

    await update.message.reply_text(
        "Now press the button below to create your first question.",
        reply_markup=poll_keyboard()
    )

    await update.message.reply_text(
        "When done adding questions, press Finish.",
        reply_markup=finish_keyboard()
    )

    return WAITING_POLL


async def receive_poll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll = update.message.poll

    if poll.type != "quiz":
        await update.message.reply_text("Poll must be in QUIZ mode.")
        return WAITING_POLL

    options = [option.text for option in poll.options]

    cursor.execute(
        "INSERT INTO questions (quiz_id, question, options, correct_option) VALUES (?, ?, ?, ?)",
        (context.user_data["quiz_id"],
         poll.question,
         json.dumps(options),
         poll.correct_option_id)
    )
    conn.commit()

    await update.message.reply_text(
        "Question added. Add another one.",
        reply_markup=poll_keyboard()
    )

    return WAITING_POLL


async def finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    quiz_id = context.user_data.get("quiz_id")

    cursor.execute("SELECT title FROM quizzes WHERE id=?", (quiz_id,))
    quiz = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) FROM questions WHERE quiz_id=?", (quiz_id,))
    total = cursor.fetchone()[0]

    await query.message.reply_text(
        f"📚 Quiz Published!\n\nTitle: {quiz[0]}\nTotal Questions: {total}",
        reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END
