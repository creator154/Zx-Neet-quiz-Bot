# bot.py - Official-style Quiz Bot (like @quizbot)
# Heroku ready | Inline buttons | Poll timer | Group share

import os
import uuid
import logging
from telegram import (
    Update, Poll, KeyboardButton, ReplyKeyboardMarkup,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    PollAnswerHandler, ConversationHandler, CallbackQueryHandler,
    ContextTypes, filters
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
TITLE, DESC, QUESTION = range(3)
QUESTION_TIMER = 30  # default seconds per question

# Token from Heroku config var
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set!")

# ---------- START / MAIN MENU ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("📝 Create New Quiz")],
        [KeyboardButton("🎯 View My Quizzes")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Welcome! Choose an option:",
        reply_markup=reply_markup
    )

# ---------- CREATE QUIZ FLOW ----------
async def create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Enter quiz title:")
    return TITLE

async def save_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['title'] = update.message.text
    await update.message.reply_text("Enter description or /skip")
    return DESC

async def save_desc_or_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text != '/skip':
        context.user_data['desc'] = update.message.text
    context.user_data['questions'] = []

    # ✅ Send inline poll creation button immediately
    keyboard = [
        [InlineKeyboardButton("➕ Add Poll Question", callback_data="add_question")],
        [InlineKeyboardButton("✅ Finish Quiz", callback_data="finish_quiz")]
    ]
    await update.message.reply_text(
        "Now add questions using the button below:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return QUESTION

async def add_question_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Send a quiz-mode poll for this question:")
    return QUESTION

async def save_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    poll = update.message.poll
    if poll.type != Poll.QUIZ:
        await update.message.reply_text("Only quiz mode polls are allowed!")
        return QUESTION

    q = {
        'question': poll.question,
        'options': [opt.text for opt in poll.options],
        'correct': poll.correct_option_id,
        'explanation': poll.explanation or ""
    }
    context.user_data['questions'].append(q)

    # Show buttons again for next question or finish
    keyboard = [
        [InlineKeyboardButton("➕ Add Another Question", callback_data="add_question")],
        [InlineKeyboardButton("✅ Finish Quiz", callback_data="finish_quiz")]
    ]
    await update.message.reply_text(
        f"Saved ({len(context.user_data['questions'])}) questions.\nNext?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return QUESTION

async def finish_quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
# bot.py - Official-style Quiz Bot (like @quizbot)
# Heroku ready | Inline buttons | Poll timer | Group share

import os
import uuid
import logging
from telegram import (
    Update, Poll, KeyboardButton, ReplyKeyboardMarkup,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    PollAnswerHandler, ConversationHandler, CallbackQueryHandler,
    ContextTypes, filters
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
TITLE, DESC, QUESTION = range(3)
QUESTION_TIMER = 30  # default seconds per question

# Token from Heroku config var
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set!")

# ---------- START / MAIN MENU ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("📝 Create New Quiz")],
        [KeyboardButton("🎯 View My Quizzes")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Welcome! Choose an option:",
        reply_markup=reply_markup
    )

# ---------- CREATE QUIZ FLOW ----------
async def create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Enter quiz title:")
    return TITLE

async def save_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['title'] = update.message.text
    await update.message.reply_text("Enter description or /skip")
    return DESC

async def save_desc_or_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text != '/skip':
        context.user_data['desc'] = update.message.text
    context.user_data['questions'] = []

    # ✅ Send inline poll creation button immediately
    keyboard = [
        [InlineKeyboardButton("➕ Add Poll Question", callback_data="add_question")],
        [InlineKeyboardButton("✅ Finish Quiz", callback_data="finish_quiz")]
    ]
    await update.message.reply_text(
        "Now add questions using the button below:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return QUESTION

async def add_question_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Send a quiz-mode poll for this question:")
    return QUESTION

async def save_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    poll = update.message.poll
    if poll.type != Poll.QUIZ:
        await update.message.reply_text("Only quiz mode polls are allowed!")
        return QUESTION

    q = {
        'question': poll.question,
        'options': [opt.text for opt in poll.options],
        'correct': poll.correct_option_id,
        'explanation': poll.explanation or ""
    }
    context.user_data['questions'].append(q)

    # Show buttons again for next question or finish
    keyboard = [
        [InlineKeyboardButton("➕ Add Another Question", callback_data="add_question")],
        [InlineKeyboardButton("✅ Finish Quiz", callback_data="finish_quiz")]
    ]
    await update.message.reply_text(
        f"Saved ({len(context.user_data['questions'])}) questions.\nNext?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return QUESTION

async def finish_quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    questions = context.user_data.get('questions', [])
    if not questions:
        await query.edit_message_text("No questions added. Cannot finish.")
        return QUESTION

    title = context.user_data.get('title', 'Untitled')
    desc = context.user_data.get('desc', '')
    quiz_id = str(uuid.uuid4())[:8]

    # Store quiz in bot_data
    context.bot_data.setdefault('quizzes', {})[quiz_id] = {
        'title': title,
        'desc': desc,
        'questions': questions
    }

    keyboard = [
        [InlineKeyboardButton("Start in Group", callback_data=f"startgroup_{quiz_id}")],
        [InlineKeyboardButton("Copy Quiz Link", callback_data=f"copylink_{quiz_id}")]
    ]
    await query.edit_message_text(
        f"Quiz '{title}' created!\nID: {quiz_id}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data.clear()
    return ConversationHandler.END

# ---------- START QUIZ IN GROUP ----------
async def startgroup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    quiz_id = query.data.split("_")[1]
    quiz = context.bot_data.get('quizzes', {}).get(quiz_id)
    if not quiz:
        await query.edit_message_text("Quiz not found.")
        return

    context.chat_data['active_quiz'] = {'quiz': quiz, 'index': 0, 'scores': {}}
    await query.edit_message_text(f"Quiz started in this group: {quiz['title']}")
    await send_next(context, query.message.chat_id)

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
                CallbackQueryHandler(add_question_callback, pattern="add_question"),
                CallbackQueryHandler(finish_quiz_callback, pattern="finish_quiz"),
            ]
        },
        fallbacks=[]
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(PollAnswerHandler(handle_answer))
    app.add_handler(CallbackQueryHandler(startgroup_callback, pattern="startgroup_.*"))

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()    await query.answer()

    questions = context.user_data.get('questions', [])
    if not questions:
        await query.edit_message_text("No questions added. Cannot finish.")
        return QUESTION

    title = context.user_data.get('title', 'Untitled')
    desc = context.user_data.get('desc', '')
    quiz_id = str(uuid.uuid4())[:8]

    # Store quiz in bot_data
    context.bot_data.setdefault('quizzes', {})[quiz_id] = {
        'title': title,
        'desc': desc,
        'questions': questions
    }

    keyboard = [
        [InlineKeyboardButton("Start in Group", callback_data=f"startgroup_{quiz_id}")],
        [InlineKeyboardButton("Copy Quiz Link", callback_data=f"copylink_{quiz_id}")]
    ]
    await query.edit_message_text(
        f"Quiz '{title}' created!\nID: {quiz_id}",
        reply_markup=InlineKeyboardMarkup(keyboard)
dler(filters.Regex("✅ Done"), done)
            ],
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(PollAnswerHandler(handle_answer))

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
