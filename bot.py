# bot.py - Telegram Quiz Bot (official-like) - Heroku ready

import logging
import os
import uuid
from telegram import Update, Poll, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    PollAnswerHandler,
    ConversationHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TITLE, DESC, QUESTION, SETTINGS = range(4)
DEFAULT_TIMER = 30

TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set!")

# ---------- START ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi! Create quizzes with multiple choice questions.\nUse /create to start a new quiz."
    )

# ---------- CREATE QUIZ FLOW ----------
async def create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send quiz title:")
    return TITLE

async def save_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['title'] = update.message.text
    await update.message.reply_text("Send quiz description or /skip")
    return DESC

async def save_desc_or_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text != '/skip':
        context.user_data['desc'] = update.message.text

    context.user_data['questions'] = []
    # Direct poll prompt like official
    await update.message.reply_text(
        "Now add your first question using a poll (Quiz mode ON, mark correct answer).\n\n"
        "Send a poll to continue."
    )
    return QUESTION

async def save_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll = update.message.poll
    if poll.type != Poll.QUIZ:
        await update.message.reply_text("Send a quiz poll only!")
        return QUESTION

    q = {
        'question': poll.question,
        'options': [opt.text for opt in poll.options],
        'correct': poll.correct_option_id,
        'explanation': poll.explanation or "",
    }
    context.user_data['questions'].append(q)

    # Inline buttons for next poll or done
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ Add Another Question", callback_data="add")],
            [InlineKeyboardButton("✅ Done", callback_data="done")],
        ]
    )

    await update.message.reply_text(
        f"Saved ({len(context.user_data['questions'])}) question(s).",
        reply_markup=keyboard,
    )
    return QUESTION

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "add":
        await query.message.reply_text(
            "Send next quiz poll (Quiz mode ON, mark correct answer)"
        )
        return QUESTION
    elif data == "done":
        return await quiz_settings(update, context)

# ---------- QUIZ SETTINGS ----------
async def quiz_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    qs = context.user_data.get('questions', [])
    if not qs:
        await update.callback_query.message.reply_text("No questions added!")
        return ConversationHandler.END

    # Create unique quiz ID
    quiz_id = str(uuid.uuid4())[:8]
    context.bot_data.setdefault("quizzes", {})[quiz_id] = {
        "title": context.user_data.get("title", "Untitled"),
        "desc": context.user_data.get("desc", ""),
        "questions": qs,
        "timer": DEFAULT_TIMER,
    }

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"⏱ Set Timer (default {DEFAULT_TIMER}s)", callback_data=f"timer_{quiz_id}")],
            [InlineKeyboardButton("▶️ Start Quiz", callback_data=f"start_{quiz_id}")],
            [InlineKeyboardButton("Share Quiz", switch_inline_query_current_chat=f"startquiz {quiz_id}")],
        ]
    )

    await update.callback_query.message.reply_text(
        f"Quiz '{context.user_data.get('title','Untitled')}' created!\n"
        f"ID: {quiz_id}\nYou can now set timer or start the quiz in a group.",
        reply_markup=keyboard,
    )
    context.user_data.clear()
    return ConversationHandler.END

# ---------- START QUIZ IN GROUP ----------
async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("Use in a group only!")
        return

    if not context.args:
        await update.message.reply_text("/startquiz <quiz_id>")
        return

    quiz_id = context.args[0]
    quiz = context.bot_data.get("quizzes", {}).get(quiz_id)
    if not quiz:
        await update.message.reply_text("Quiz not found")
        return

    context.chat_data['active_quiz'] = {"quiz": quiz, "index": 0, "scores": {}}
    await update.message.reply_text(f"Quiz started: {quiz['title']}")
    await send_next(context, update.effective_chat.id)

# ---------- SEND NEXT QUESTION ----------
async def send_next(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    active = context.chat_data.get("active_quiz")
    if not active:
        return

    index = active["index"]
    quiz = active["quiz"]

    if index >= len(quiz["questions"]):
        scores = active["scores"]
        text = "🏆 Leaderboard:\n" + "\n".join(
            [f"{uid}: {score}" for uid, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)]
        )
        await context.bot.send_message(chat_id, text)
        context.chat_data.pop("active_quiz", None)
        return

    q = quiz["questions"][index]
    await context.bot.send_poll(
        chat_id=chat_id,
        question=q["question"],
        options=q["options"],
        type=Poll.QUIZ,
        correct_option_id=q["correct"],
        explanation=q["explanation"],
        is_anonymous=False,
        open_period=quiz.get("timer", DEFAULT_TIMER),
    )
    active["index"] += 1

# ---------- HANDLE POLL ANSWERS ----------
async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll_answer = update.poll_answer
    user_id = poll_answer.user.id
    active = context.chat_data.get("active_quiz")
    if not active:
        return

    index = active["index"] - 1
    q = active["quiz"]["questions"][index]
    selected = poll_answer.option_ids[0] if poll_answer.option_ids else None

    if selected == q["correct"]:
        active["scores"][user_id] = active["scores"].get(user_id, 0) + 1

# ---------- MAIN ----------
def main():
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("create", create)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_title)],
            DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_desc_or_skip)],
            QUESTION: [
                MessageHandler(filters.POLL, save_question),
                CallbackQueryHandler(button_handler),
            ],
        },
        fallbacks=[],
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("startquiz", start_quiz))
    app.add_handler(PollAnswerHandler(handle_answer))

    app.run_polling()

if __name__ == "__main__":
    main()
