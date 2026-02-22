# bot.py - Official-like Telegram Quiz Bot
# Heroku ready - CLEAN, inline buttons for poll creation & quiz settings

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
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TITLE, DESC, QUESTION, SETTINGS = range(4)
DEFAULT_TIMER = 30  # seconds

TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set!")

# --------------------- START ---------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("📝 Create New Quiz", callback_data="create")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Hi! Create quizzes like official quiz bot.", reply_markup=reply_markup)

# --------------------- CREATE FLOW ---------------------
async def start_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Send quiz title")
    return TITLE

async def save_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['title'] = update.message.text
    await update.message.reply_text("Send description or /skip")
    return DESC

async def save_desc_or_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text != '/skip':
        context.user_data['desc'] = update.message.text
    context.user_data['questions'] = []

    # Inline button to add poll
    keyboard = [[InlineKeyboardButton("➕ Add Question", callback_data="add_question")],
                [InlineKeyboardButton("✅ Done", callback_data="done_quiz")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Now add your first question using the button below:",
        reply_markup=reply_markup
    )
    return QUESTION

async def add_question_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Send your quiz poll (Quiz mode ON, mark correct answer)")
    return QUESTION

async def save_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll = update.message.poll
    if poll.type != Poll.QUIZ:
        await update.message.reply_text("Send quiz poll only!")
        return QUESTION

    q = {
        'question': poll.question,
        'options': [opt.text for opt in poll.options],
        'correct': poll.correct_option_id,
        'explanation': poll.explanation or ""
    }
    context.user_data['questions'].append(q)

    keyboard = [[InlineKeyboardButton("➕ Add Another Question", callback_data="add_question")],
                [InlineKeyboardButton("✅ Done", callback_data="done_quiz")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Saved ({len(context.user_data['questions'])}) questions.\nAdd more or finish:",
        reply_markup=reply_markup
    )
    return QUESTION

async def done_quiz_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    qs = context.user_data.get('questions', [])
    if not qs:
        await query.message.reply_text("No questions added")
        return ConversationHandler.END

    title = context.user_data.get('title', 'Untitled')
    desc = context.user_data.get('desc', '')

    quiz_id = str(uuid.uuid4())[:8]
    context.bot_data.setdefault('quizzes', {})[quiz_id] = {
        'title': title,
        'desc': desc,
        'questions': qs,
        'timer': DEFAULT_TIMER,
        'shuffle': False,
        'negative': 0
    }

    # Settings buttons after done
    keyboard = [
        [InlineKeyboardButton(f"⏱ Set Timer ({DEFAULT_TIMER}s)", callback_data=f"set_timer_{quiz_id}")],
        [InlineKeyboardButton("🔀 Shuffle Questions", callback_data=f"set_shuffle_{quiz_id}")],
        [InlineKeyboardButton("➖ Set Negative Marking", callback_data=f"set_negative_{quiz_id}")],
        [InlineKeyboardButton("▶️ Start Quiz", callback_data=f"start_{quiz_id}")],
        [InlineKeyboardButton("Start in Group", callback_data=f"group_{quiz_id}")],
        [InlineKeyboardButton("Share Quiz", switch_inline_query_current_chat=f"startquiz {quiz_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(f"Quiz '{title}' saved! Now configure or start:", reply_markup=reply_markup)

    context.user_data.clear()
    return SETTINGS

# --------------------- SETTINGS HANDLER ---------------------
async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    quiz_id = data.split("_")[-1]
    quiz = context.bot_data['quizzes'][quiz_id]

    if data.startswith("set_timer"):
        # Example: just toggling between 30, 45, 60 for demo
        new_timer = 45 if quiz['timer']==30 else 60 if quiz['timer']==45 else 30
        quiz['timer'] = new_timer
        await query.edit_message_text(f"Timer set to {new_timer}s")
    elif data.startswith("set_shuffle"):
        quiz['shuffle'] = not quiz['shuffle']
        await query.edit_message_text(f"Shuffle set to {quiz['shuffle']}")
    elif data.startswith("set_negative"):
        quiz['negative'] = quiz['negative'] + 1  # simple increment demo
        await query.edit_message_text(f"Negative marking set to {quiz['negative']}")
    elif data.startswith("start"):
        await query.edit_message_text(f"Quiz started: {quiz['title']}")
        context.chat_data['active_quiz'] = {'quiz': quiz, 'index':0, 'scores':{}}
        await send_next(context, query.message.chat.id)
    elif data.startswith("group"):
        await query.edit_message_text(f"Use in your group: /startquiz {quiz_id}")

# --------------------- QUIZ FLOW ---------------------
async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("Use in group only!")
        return
    if not context.args:
        await update.message.reply_text("/startquiz <quiz_id>")
        return

    quiz_id = context.args[0]
    quiz = context.bot_data.get('quizzes', {}).get(quiz_id)
    if not quiz:
        await update.message.reply_text("Quiz not found")
        return

    context.chat_data['active_quiz'] = {'quiz':quiz, 'index':0, 'scores':{}}
    await update.message.reply_text(f"Quiz started: {quiz['title']}")
    await send_next(context, update.effective_chat.id)

async def send_next(context: ContextTypes.DEFAULT_TYPE, chat_id:int):
    active = context.chat_data.get('active_quiz')
    if not active: return
    index = active['index']
    quiz = active['quiz']
    if index >= len(quiz['questions']):
        # leaderboard
        scores = active['scores']
        text = "🏆 Leaderboard:\n" + "\n".join([f"{uid}: {score}" for uid,score in sorted(scores.items(), key=lambda x:x[1], reverse=True)])
        await context.bot.send_message(chat_id, text)
        context.chat_data.pop('active_quiz')
        return
    q = quiz['questions'][index]
    await context.bot.send_poll(
        chat_id=chat_id,
        question=q['question'],
        options=[opt for opt in q['options']],
        type=Poll.QUIZ,
        correct_option_id=q['correct'],
        explanation=q['explanation'],
        is_anonymous=False,
        open_period=quiz['timer']
    )
    active['index'] +=1

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll_answer = update.poll_answer
    user_id = poll_answer.user.id
    active = context.chat_data.get('active_quiz')
    if not active: return
    index = active['index']-1
    q = active['quiz']['questions'][index]
    selected = poll_answer.option_ids[0] if poll_answer.option_ids else None
    if selected == q['correct']:
        active['scores'][user_id] = active['scores'].get(user_id,0)+1

# --------------------- MAIN ---------------------
def main():
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_create, pattern="^create$")],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_title)],
            DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_desc_or_skip)],
            QUESTION: [
                MessageHandler(filters.POLL, save_question),
                CallbackQueryHandler(add_question_button, pattern="^add_question$"),
                CallbackQueryHandler(done_quiz_button, pattern="^done_quiz$")
            ],
            SETTINGS: [CallbackQueryHandler(settings_handler, pattern="^(set_|start|group)_")]
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
