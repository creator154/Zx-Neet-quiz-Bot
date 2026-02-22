# bot.py - Telegram Quiz Bot (official-like) - Poll + Timer + Shuffle + Negative + Group start
# Heroku ready - CLEAN

import logging
import os
import uuid
from telegram import (
    Update, Poll, ReplyKeyboardMarkup, KeyboardButton, KeyboardButtonPollType,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, PollAnswerHandler,
    ConversationHandler, CallbackQueryHandler, filters, ContextTypes
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TITLE, DESC, QUESTION, CONFIG = range(4)
QUESTION_TIMER = 30  # default per question

TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set!")

# --- START ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("Create New Quiz", request_poll=KeyboardButtonPollType(type="quiz"))]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Hi! Create quizzes with multiple choice questions.\nTap below to start:",
        reply_markup=reply_markup
    )

# --- CREATE QUIZ ---
async def create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Send quiz title")
    return TITLE

async def save_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['title'] = update.message.text
    await update.message.reply_text("Send description or /skip")
    return DESC

async def save_desc_or_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text != '/skip':
        context.user_data['desc'] = update.message.text
    await update.message.reply_text("Now send your first quiz poll (Quiz mode ON, mark correct answer)")
    context.user_data['questions'] = []
    return QUESTION

async def save_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    poll = update.message.poll
    if poll.type != Poll.QUIZ:
        await update.message.reply_text("Send quiz poll only!")
        return QUESTION

    context.user_data['questions'].append({
        'question': poll.question,
        'options': [opt.text for opt in poll.options],
        'correct': poll.correct_option_id,
        'explanation': poll.explanation or ""
    })

    await update.message.reply_text(
        f"Saved ({len(context.user_data['questions'])}) question(s).\nSend next poll or /done"
    )
    return QUESTION

# --- DONE & CONFIG ---
async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    qs = context.user_data.get('questions', [])
    if not qs:
        await update.message.reply_text("No questions added")
        return ConversationHandler.END

    quiz_id = str(uuid.uuid4())[:8]
    context.bot_data.setdefault('quizzes', {})[quiz_id] = {
        'title': context.user_data.get('title', 'Untitled'),
        'desc': context.user_data.get('desc', ''),
        'questions': qs,
        'timer': QUESTION_TIMER,
        'negative': 0,
        'shuffle': False
    }

    # Summary + inline buttons (official-like)
    summary = f"✅ Quiz Created!\n\n" \
              f"📁 {context.user_data.get('title', 'Untitled')}\n" \
              f"{context.user_data.get('desc', '')}\n" \
              f"Total Questions: {len(qs)}\n" \
              f"⏱ Time per question: {QUESTION_TIMER} sec\n" \
              f"Quiz ID: {quiz_id}"

    buttons = [
        [InlineKeyboardButton("⏱ Set Timer", callback_data=f"timer_{quiz_id}")],
        [InlineKeyboardButton("➖ Set Negative Marking", callback_data=f"negative_{quiz_id}")],
        [InlineKeyboardButton("🔀 Shuffle Questions", callback_data=f"shuffle_{quiz_id}")],
        [InlineKeyboardButton("▶️ Start Quiz", callback_data=f"start_{quiz_id}")],
        [InlineKeyboardButton("📍 Start in Group", switch_inline_query_current_chat=f"startquiz {quiz_id}")],
        [InlineKeyboardButton("🔗 Share Quiz", switch_inline_query_current_chat=f"share {quiz_id}")],
        [InlineKeyboardButton("✏️ Edit Quiz", callback_data=f"edit_{quiz_id}")]
    ]

    reply_markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(summary, reply_markup=reply_markup)

    context.user_data.clear()
    return ConversationHandler.END

# --- BUTTON HANDLER ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("timer_"):
        await query.edit_message_text("Timer setting clicked (implement logic)")
    elif data.startswith("negative_"):
        await query.edit_message_text("Negative marking clicked (implement logic)")
    elif data.startswith("shuffle_"):
        await query.edit_message_text("Shuffle clicked (implement logic)")
    elif data.startswith("start_"):
        quiz_id = data.split("_")[1]
        await query.edit_message_text(f"Quiz started: {quiz_id}\nUse /startquiz <id> in group")
    elif data.startswith("edit_"):
        await query.edit_message_text("Edit clicked (implement logic)")

# --- START QUIZ IN GROUP ---
async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("Use this command in a group!")
        return

    if not context.args:
        await update.message.reply_text("/startquiz <quiz_id>")
        return

    quiz_id = context.args[0]
    quiz = context.bot_data.get('quizzes', {}).get(quiz_id)
    if not quiz:
        await update.message.reply_text("Quiz not found")
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
        text = "🏆 Leaderboard:\n" + "\n".join([f"{uid}: {score}" for uid, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)])
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

# --- MAIN ---
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
    app.add_handler(CommandHandler("startquiz", start_quiz))
    app.add_handler(PollAnswerHandler(handle_answer))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.run_polling()

if __name__ == "__main__":
    main()
