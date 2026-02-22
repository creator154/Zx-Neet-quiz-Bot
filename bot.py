# bot.py - Official-style Telegram Quiz Bot
# Heroku ready - Clean, inline buttons, timer, shuffle, negative marking, leaderboard

import logging
import os
import uuid
from telegram import Update, Poll, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    PollAnswerHandler, ConversationHandler, CallbackQueryHandler,
    filters, ContextTypes
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TITLE, DESC, QUESTION, SETTINGS = range(4)
QUESTION_TIMER = 30

TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set!")

# Start message with main keyboard
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi! Create quizzes with multiple choice questions.\nUse /create to start a new quiz."
    )

# Step 1: create title
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
    await update.message.reply_text("Send quiz poll (Quiz mode ON, correct answer mark kar ke)")
    context.user_data['questions'] = []
    return QUESTION

async def save_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    poll = update.message.poll
    if poll.type != Poll.QUIZ:
        await update.message.reply_text("Sirf quiz mode poll bhejo!")
        return QUESTION

    q = {
        'question': poll.question,
        'options': [opt.text for opt in poll.options],
        'correct': poll.correct_option_id,
        'explanation': poll.explanation or ""
    }
    context.user_data['questions'].append(q)

    await update.message.reply_text(f"Saved ({len(context.user_data['questions'])})\nNext poll ya /done")
    return QUESTION

# Step done: show settings buttons
async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
        'shuffle': False,
        'negative': 0
    }

    summary = f"Quiz saved!\n\n📁 {title}\n{desc or ''}\nTotal questions: {len(qs)}\nID: {quiz_id}"

    # Buttons for settings (official style)
    inline_keyboard = [
        [InlineKeyboardButton("⏱ Set Timer", callback_data=f"timer_{quiz_id}")],
        [InlineKeyboardButton("🔀 Shuffle Options", callback_data=f"shuffle_{quiz_id}")],
        [InlineKeyboardButton("➖ Negative Marking", callback_data=f"negative_{quiz_id}")],
        [InlineKeyboardButton("▶️ Start Quiz", callback_data=f"start_{quiz_id}")],
        [InlineKeyboardButton("Start in Group", callback_data=f"group_{quiz_id}")],
        [InlineKeyboardButton("Share Quiz", switch_inline_query_current_chat=f"startquiz {quiz_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard)

    await update.message.reply_text(summary, reply_markup=reply_markup)
    context.user_data.clear()
    return ConversationHandler.END

# Callback handler for inline buttons
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    quizzes = context.bot_data.get('quizzes', {})

    if data.startswith("timer_"):
        quiz_id = data.split("_")[1]
        await query.edit_message_text(f"Set timer for quiz {quiz_id} (currently {quizzes[quiz_id]['timer']}s). Type number in seconds:")
        context.chat_data['setting_quiz'] = quiz_id
        context.chat_data['setting_type'] = 'timer'

    elif data.startswith("shuffle_"):
        quiz_id = data.split("_")[1]
        quizzes[quiz_id]['shuffle'] = not quizzes[quiz_id]['shuffle']
        await query.edit_message_text(f"Shuffle set to {quizzes[quiz_id]['shuffle']} for quiz {quiz_id}")

    elif data.startswith("negative_"):
        quiz_id = data.split("_")[1]
        await query.edit_message_text(f"Set negative marking for quiz {quiz_id}. Type value:")

        context.chat_data['setting_quiz'] = quiz_id
        context.chat_data['setting_type'] = 'negative'

    elif data.startswith("start_"):
        quiz_id = data.split("_")[1]
        quiz = quizzes.get(quiz_id)
        if not quiz:
            await query.edit_message_text("Quiz not found")
            return
        await query.edit_message_text(f"Quiz started: {quiz['title']}")
        context.chat_data['active_quiz'] = {'quiz': quiz, 'index': 0, 'scores': {}}
        await send_next(context, query.message.chat_id)

    elif data.startswith("group_"):
        quiz_id = data.split("_")[1]
        await query.edit_message_text(f"Use in group by sending: /startquiz {quiz_id}")

# Group start
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

    context.chat_data['active_quiz'] = {'quiz': quiz, 'index': 0, 'scores': {}}
    await update.message.reply_text(f"Quiz started: {quiz['title']}")
    await send_next(context, update.effective_chat.id)

# Send questions
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
    options = q['options'].copy()
    if quiz.get('shuffle'):
        import random
        random.shuffle(options)

    await context.bot.send_poll(
        chat_id=chat_id,
        question=q['question'],
        options=options,
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

def main():
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("create", create)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_title)],
            DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_desc_or_skip)],
            QUESTION: [MessageHandler(filters.POLL, save_question), CommandHandler("done", done)]
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
