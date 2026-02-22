# bot.py - Complete Quiz Bot (official style)
import logging
import os
import uuid
from telegram import (
    Update, Poll, KeyboardButton, ReplyKeyboardMarkup,
    KeyboardButtonPollType, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, PollAnswerHandler,
    ConversationHandler, filters, ContextTypes
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# States
TITLE, DESC, QUESTION, TIMER, SHUFFLE = range(5)

# Default question timer
QUESTION_TIMER = 30

# Bot token from env
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set!")

# ---------------- KEYBOARDS ----------------
def start_keyboard():
    keyboard = [
        [KeyboardButton("📝 Create New Quiz")],
        [KeyboardButton("🎯 View My Quizzes")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def poll_keyboard():
    keyboard = [
        [KeyboardButton(
            "➕ Add Question (Poll)",
            request_poll=KeyboardButtonPollType(type="quiz")
        )],
        [KeyboardButton("✅ Done")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def timer_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("10 sec", callback_data="timer_10"),
            InlineKeyboardButton("20 sec", callback_data="timer_20"),
            InlineKeyboardButton("30 sec", callback_data="timer_30"),
        ],
        [
            InlineKeyboardButton("45 sec", callback_data="timer_45"),
            InlineKeyboardButton("60 sec", callback_data="timer_60"),
        ]
    ])

def shuffle_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Yes", callback_data="shuffle_yes"),
            InlineKeyboardButton("No", callback_data="shuffle_no")
        ]
    ])

def share_quiz_keyboard(quiz_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Start in Group", switch_inline_query=quiz_id)]
    ])

# ---------------- HANDLERS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi! Create quizzes with multiple choice questions.\nChoose:",
        reply_markup=start_keyboard()
    )

# Create quiz flow
async def create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Send quiz title:")
    return TITLE

async def save_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['title'] = update.message.text
    await update.message.reply_text("Send description or /skip:")
    return DESC

async def save_desc_or_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text != '/skip':
        context.user_data['desc'] = update.message.text

    context.user_data['questions'] = []
    await update.message.reply_text(
        "Now add your first question using the button below:",
        reply_markup=poll_keyboard()
    )
    return QUESTION

async def save_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    poll = update.message.poll
    if poll.type != Poll.QUIZ:
        await update.message.reply_text("Please send a quiz poll only!")
        return QUESTION

    q = {
        'question': poll.question,
        'options': [opt.text for opt in poll.options],
        'correct': poll.correct_option_id,
        'explanation': poll.explanation or ""
    }
    context.user_data['questions'].append(q)

    await update.message.reply_text(
        f"Saved ({len(context.user_data['questions'])}) questions.\nNext poll or /done",
        reply_markup=poll_keyboard()
    )
    return QUESTION

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    qs = context.user_data.get('questions', [])
    if not qs:
        await update.message.reply_text("No questions added, quiz cancelled")
        return ConversationHandler.END

    quiz_id = str(uuid.uuid4())[:8]
    context.bot_data.setdefault('quizzes', {})[quiz_id] = {
        'title': context.user_data.get('title', 'Untitled'),
        'desc': context.user_data.get('desc', ''),
        'questions': qs
    }

    await update.message.reply_text(
        f"Quiz created!\nID: {quiz_id}",
        reply_markup=share_quiz_keyboard(quiz_id)
    )
    context.user_data.clear()
    return ConversationHandler.END

# Start quiz in group
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
        open_period=QUESTION_TIMER
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

# ---------------- MAIN ----------------
def main():
    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("create", create)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_title)],
            DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_desc_or_skip)],
            QUESTION: [
                MessageHandler(filters.POLL, save_question),
                CommandHandler("done", done)
            ],
        },
        fallbacks=[]
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("startquiz", start_quiz))
    app.add_handler(PollAnswerHandler(handle_answer))

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()# bot.py - Official-like Telegram Quiz Bot
# Python Telegram Bot v20+, Async
# Heroku ready

import os
import uuid
import logging
from telegram import (
    Update,
    Poll,
    KeyboardButton,
    KeyboardButtonPollType,
    ReplyKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    PollAnswerHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

'][index]
    await context.bot.send_poll(
        chat_id=chat_id,
        question=q['question'],
        options=q['options'],
        type=Poll.QUIZ,
        correct_option_id=q['correct'],
        explanation=q['explanation'],
        is_anonymous=False,
        open_period=QUESTION_TIMER
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

# === Main ===
def main():
    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("create", create)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_title)],
            DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_desc_or_skip)],
            QUESTION: [
                MessageHandler(filters.POLL, save_question),
                MessageHandler(filters.Regex("^✅ Done$"), done)
            ],
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("startquiz", start_quiz))
    app.add_handler(PollAnswerHandler(handle_answer))
    app.add_handler(conv_handler)

    app.run_polling()

if __name__ == "__main__":
    main()
