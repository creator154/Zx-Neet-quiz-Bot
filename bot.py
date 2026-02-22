# bot.py - Advanced Quiz Bot (official style)
import logging
import os
import uuid
from telegram import Update, Poll, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, PollAnswerHandler,
    ConversationHandler, CallbackQueryHandler, ContextTypes, filters
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# States
TITLE, DESC, QUESTION, TIMER, SHUFFLE, FINISH = range(6)

# Default question timer
DEFAULT_TIMER = 30

TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set!")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Create Quiz", callback_data="create")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Hi! Create quizzes with multiple choice questions:", reply_markup=reply_markup)

# --- Conversation handlers ---

async def create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Send quiz title:")
    return TITLE

async def save_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['title'] = update.message.text
    await update.message.reply_text("Send description or /skip")
    return DESC

async def save_desc_or_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text != '/skip':
        context.user_data['desc'] = update.message.text
    context.user_data['questions'] = []
    await update.message.reply_text("Now send a quiz poll (correct answer mark karein).")
    return QUESTION

async def save_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll = update.message.poll
    if poll.type != Poll.QUIZ:
        await update.message.reply_text("Please send a quiz-mode poll only!")
        return QUESTION

    q = {
        'question': poll.question,
        'options': [opt.text for opt in poll.options],
        'correct': poll.correct_option_id,
        'explanation': poll.explanation or ""
    }
    context.user_data['questions'].append(q)
    await update.message.reply_text(f"Saved ({len(context.user_data['questions'])}) questions. Send next poll or /done")

    # Inline buttons: Timer & Finish
    buttons = [
        [
            InlineKeyboardButton("10s", callback_data="timer_10"),
            InlineKeyboardButton("20s", callback_data="timer_20"),
            InlineKeyboardButton("30s", callback_data="timer_30"),
        ],
        [
            InlineKeyboardButton("45s", callback_data="timer_45"),
            InlineKeyboardButton("60s", callback_data="timer_60"),
        ],
        [InlineKeyboardButton("✅ Finish & Publish", callback_data="finish")]
    ]
    await update.message.reply_text("Set timer or finish quiz:", reply_markup=InlineKeyboardMarkup(buttons))
    return QUESTION

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("timer_"):
        t = int(data.split("_")[1])
        context.user_data['timer'] = t
        await query.message.reply_text(f"Timer set to {t} seconds.")
    elif data == "finish":
        qs = context.user_data.get('questions', [])
        if not qs:
            await query.message.reply_text("No questions added yet!")
            return QUESTION

        title = context.user_data.get('title', 'Untitled')
        desc = context.user_data.get('desc', '')
        quiz_id = str(uuid.uuid4())[:8]

        context.bot_data.setdefault('quizzes', {})[quiz_id] = {
            'title': title,
            'desc': desc,
            'questions': qs,
            'timer': context.user_data.get('timer', DEFAULT_TIMER)
        }

        await query.message.reply_text(f"Quiz created!\nID: {quiz_id}\nStart in group: /startquiz {quiz_id}")
        context.user_data.clear()
        return ConversationHandler.END

# --- Start quiz in group ---
async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("Use this command in a group.")
        return
    if not context.args:
        await update.message.reply_text("/startquiz <quiz_id>")
        return

    quiz_id = context.args[0]
    quiz = context.bot_data.get('quizzes', {}).get(quiz_id)
    if not quiz:
        await update.message.reply_text("Quiz not found!")
        return

    context.chat_data['active_quiz'] = {'quiz': quiz, 'index': 0, 'scores': {}}
    await update.message.reply_text(f"Quiz started: {quiz['title']}")
    await send_next(context, update.effective_chat.id)

async def send_next(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    active = context.chat_data.get('active_quiz')
    if not active:
        return

    index = active['index']
    quiz = active['quiz']

    if index >= len(quiz['questions']):
        scores = active['scores']
        text = "Leaderboard:\n" + "\n".join([f"{uid}: {score}" for uid, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)])
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
        open_period=quiz.get('timer', DEFAULT_TIMER)
    )

    active['index'] += 1

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

# --- Main ---
def main():
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(create, pattern="create")],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_title)],
            DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_desc_or_skip)],
            QUESTION: [
                MessageHandler(filters.POLL, save_question),
                CallbackQueryHandler(button_handler)
            ],
        },
        fallbacks=[]
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("startquiz", start_quiz))
    app.add_handler(PollAnswerHandler(handle_answer))
    app.run_polling()

if __name__ == "__main__":
    main()
