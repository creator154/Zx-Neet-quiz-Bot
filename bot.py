# bot.py - Complete official-like Telegram Quiz Bot (PTB v20+)
# Heroku-ready, async, clean

import logging
import os
import uuid
from telegram import (
    Update, Poll, KeyboardButton, ReplyKeyboardMarkup,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, PollAnswerHandler,
    ConversationHandler, CallbackQueryHandler, filters, ContextTypes
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
TITLE, DESC, QUESTION = range(3)

QUESTION_TIMER = 30  # default per question

# Telegram bot token
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set!")

# ---------------- Handlers ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("📝 Create New Quiz")],
        [KeyboardButton("🎯 View My Quizzes")],
        [KeyboardButton("▶️ Start Quiz in Group")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Hi! Create quizzes with multiple choice questions.\nChoose:",
        reply_markup=reply_markup
    )

# --- Create Quiz Flow ---

async def create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send quiz title:")
    return TITLE

async def save_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['title'] = update.message.text
    await update.message.reply_text("Send quiz description or /skip")
    return DESC

async def save_desc_or_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text != "/skip":
        context.user_data['desc'] = update.message.text
    await update.message.reply_text(
        "Now add your first question using the button below:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Question", callback_data="add_question")]
        ])
    )
    context.user_data['questions'] = []
    return QUESTION

# --- Question Flow ---

async def save_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll = update.message.poll
    if poll.type != Poll.QUIZ:
        await update.message.reply_text("Send quiz poll only (Quiz mode ON)!")
        return QUESTION

    question_data = {
        "question": poll.question,
        "options": [opt.text for opt in poll.options],
        "correct": poll.correct_option_id,
        "explanation": poll.explanation or ""
    }
    context.user_data['questions'].append(question_data)
    await update.message.reply_text(
        f"Saved ({len(context.user_data['questions'])}) questions.\nSend next poll or press /done"
    )
    return QUESTION

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    qs = context.user_data.get('questions', [])
    if not qs:
        await update.message.reply_text("No questions added")
        return ConversationHandler.END

    title = context.user_data.get('title', 'Untitled')
    desc = context.user_data.get('desc', '')

    quiz_id = str(uuid.uuid4())[:8]

    context.bot_data.setdefault('quizzes', {})[quiz_id] = {
        'title': title,
        'desc': desc,
        'questions': qs,
        'timer': QUESTION_TIMER,
        'negative': 0,
        'shuffle': False
    }

    # Official-like summary message
    summary = f"Quiz created successfully!\n\n" \
              f"📁 {title}\n" \
              f"{desc or ''}\n" \
              f"Total questions: {len(qs)}\n" \
              f"⏱ Time per question: {QUESTION_TIMER} sec\n" \
              f"Quiz ID: {quiz_id}"

    inline_keyboard = [
        [InlineKeyboardButton("▶️ Start Quiz", callback_data=f"start_{quiz_id}")],
        [InlineKeyboardButton("Group Start", callback_data=f"group_{quiz_id}")],
        [InlineKeyboardButton("Share Quiz", switch_inline_query_current_chat=f"startquiz {quiz_id}")],
        [InlineKeyboardButton("✏️ Edit Quiz", callback_data=f"edit_{quiz_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard)

    await update.message.reply_text(summary, reply_markup=reply_markup)
    context.user_data.clear()
    return ConversationHandler.END

# --- Button Handler ---

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "add_question":
        await query.edit_message_text("Send your poll question now (Quiz mode ON)")
        return QUESTION
    elif data.startswith("start_"):
        quiz_id = data.split("_")[1]
        quiz = context.bot_data.get('quizzes', {}).get(quiz_id)
        if not quiz:
            await query.edit_message_text("Quiz not found")
            return
        context.chat_data['active_quiz'] = {"quiz": quiz, "index": 0, "scores": {}}
        await query.edit_message_text(f"Quiz started: {quiz['title']}")
        await send_next(context, update.effective_chat.id)
    elif data.startswith("group_"):
        await query.edit_message_text("Group mein jaake /startquiz <id> use karo")
    elif data.startswith("edit_"):
        await query.edit_message_text("Editing not implemented yet")

# --- Send next question in group quiz ---

async def send_next(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    active = context.chat_data.get('active_quiz')
    if not active:
        return

    index = active['index']
    quiz = active['quiz']

    if index >= len(quiz['questions']):
        scores = active['scores']
        text = "🏆 Leaderboard:\n" + "\n".join(
            [f"{uid}: {score}" for uid, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)]
        )
        await context.bot.send_message(chat_id, text)
        context.chat_data.pop('active_quiz', None)
        return

    q = quiz['questions'][index]
    await context.bot.send_poll(
        chat_id=chat_id,
        question=q['question'],
        options=q['options'],
        type=Poll.QUIZ,
        correct_option_id=q['correct'],
        explanation=q['explanation'],
        is_anonymous=False,
        open_period=quiz.get('timer', QUESTION_TIMER)
    )
    active['index'] += 1

# --- Poll Answer Handler ---

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll_answer = update.poll_answer
    user_id = poll_answer.user.id
    active = context.chat_data.get('active_quiz')
    if not active:
        return

    index = active['index'] - 1
    q = active['quiz']['questions'][index]
    selected = poll_answer.option_ids[0] if poll_answer.option_ids else None
    if selected == q['correct']:
        active['scores'][user_id] = active['scores'].get(user_id, 0) + 1

# ---------------- Main ----------------

def main():
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("create", create)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_title)],
            DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_desc_or_skip)],
            QUESTION: [MessageHandler(filters.POLL, save_question), CommandHandler("done", done)],
        },
        fallbacks=[]
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(PollAnswerHandler(handle_answer))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.run_polling()

if __name__ == "__main__":
    main()
