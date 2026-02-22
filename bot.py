# bot.py - Clean Telegram Quiz Bot with inline buttons (official-style)
import logging
import os
import uuid
from telegram import (
    Update,
    Poll,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    PollAnswerHandler,
    ConversationHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TITLE, DESC, QUESTION = range(3)
QUESTION_TIMER = 30

TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable not set!")

# ----------- Start / Home -----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📝 Create New Quiz", callback_data="create_quiz")],
        [InlineKeyboardButton("🎯 View My Quizzes", callback_data="view_quizzes")],
    ]
    await update.message.reply_text(
        "Welcome! Choose an option:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ----------- Create Quiz Flow -----------

async def create_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Send the **title** of your quiz:")
    return TITLE

async def save_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['title'] = update.message.text
    keyboard = [
        [InlineKeyboardButton("Skip / No Description", callback_data="skip_desc")]
    ]
    await update.message.reply_text(
        "Send a description or skip:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return DESC

async def save_desc_or_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text != '/skip':
        context.user_data['desc'] = update.message.text
    else:
        context.user_data['desc'] = ""

    context.user_data['questions'] = []

    # Inline button to add poll question
    keyboard = [
        [InlineKeyboardButton("➕ Add Poll Question", callback_data="add_question")],
        [InlineKeyboardButton("✅ Finish Quiz", callback_data="finish_quiz")]
    ]
    await update.message.reply_text(
        "Now add questions using the button below:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return QUESTION

async def add_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Send a poll in QUIZ mode (with correct answer selected).")
    return QUESTION

async def save_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll = update.message.poll
    if poll.type != Poll.QUIZ:
        await update.message.reply_text("Send a **quiz type poll** only!")
        return QUESTION

    q = {
        'question': poll.question,
        'options': [opt.text for opt in poll.options],
        'correct': poll.correct_option_id,
        'explanation': poll.explanation or ""
    }
    context.user_data['questions'].append(q)

    # Show next steps
    keyboard = [
        [InlineKeyboardButton("➕ Add Another Question", callback_data="add_question")],
        [InlineKeyboardButton("✅ Finish Quiz", callback_data="finish_quiz")]
    ]
    await update.message.reply_text(
        f"Saved ({len(context.user_data['questions'])}) question(s).",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return QUESTION

async def finish_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qs = context.user_data.get('questions', [])
    if not qs:
        await query.message.reply_text("No questions added!")
        return ConversationHandler.END

    title = context.user_data.get('title', 'Untitled')
    desc = context.user_data.get('desc', '')

    quiz_id = str(uuid.uuid4())[:8]
    context.bot_data.setdefault('quizzes', {})[quiz_id] = {
        'title': title,
        'desc': desc,
        'questions': qs
    }

    await query.message.reply_text(
        f"Quiz created!\nID: {quiz_id}\nShare in group: /startquiz {quiz_id}"
    )

    context.user_data.clear()
    return ConversationHandler.END

# ----------- Start Quiz in Group -----------

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

# ----------- Main -----------

def main():
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(create_quiz, pattern="create_quiz")],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_title)],
            DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_desc_or_skip),
                   CallbackQueryHandler(save_desc_or_skip, pattern="skip_desc")],
            QUESTION: [
                MessageHandler(filters.POLL, save_question),
                CallbackQueryHandler(add_question, pattern="add_question"),
                CallbackQueryHandler(finish_quiz, pattern="finish_quiz")
            ],
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("startquiz", start_quiz))
    app.add_handler(PollAnswerHandler(handle_answer))
    app.add_handler(conv)

    app.run_polling()

if __name__ == "__main__":
    main()
