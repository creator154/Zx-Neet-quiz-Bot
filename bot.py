# bot.py - Official-style Telegram Quiz Bot
import logging
import os
import uuid
from telegram import (
    Update, Poll, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, PollAnswerHandler,
    ConversationHandler, CallbackQueryHandler, ContextTypes, filters
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TITLE, DESC, QUESTION, SETTINGS = range(4)
QUESTION_TIMER = 30

TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set!")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hi! Tap below to create your quiz:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Create New Quiz", callback_data="create_quiz")]
        ])
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "create_quiz":
        await query.message.reply_text("Send your quiz title:")
        return TITLE

    if data.startswith("add_question_"):
        await query.message.reply_text("Send your poll (Quiz mode ON, mark correct answer).")
        return QUESTION

    if data.startswith("done_quiz_"):
        quiz_id = data.split("_")[2]
        quiz = context.bot_data.get('quizzes', {}).get(quiz_id)
        if not quiz:
            await query.message.reply_text("Quiz not found!")
            return ConversationHandler.END

        # Inline buttons for settings (Timer, Shuffle, Negative, Start, Share)
        keyboard = [
            [InlineKeyboardButton("⏱ Set Timer", callback_data=f"set_timer_{quiz_id}")],
            [InlineKeyboardButton("🔀 Shuffle Questions", callback_data=f"shuffle_{quiz_id}")],
            [InlineKeyboardButton("➖ Negative Marking", callback_data=f"negative_{quiz_id}")],
            [InlineKeyboardButton("▶️ Start Quiz", callback_data=f"start_{quiz_id}")],
            [InlineKeyboardButton("📤 Share Quiz", switch_inline_query_current_chat=f"startquiz {quiz_id}")]
        ]
        await query.message.reply_text(f"Quiz created!\nID: {quiz_id}\nChoose options below:",
                                       reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END

    # Handle other settings here (optional)
    await query.message.reply_text(f"You clicked: {data}")

async def save_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['title'] = update.message.text
    await update.message.reply_text("Send description or /skip")
    return DESC

async def save_desc_or_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text != '/skip':
        context.user_data['desc'] = update.message.text

    # Create a new quiz id
    quiz_id = str(uuid.uuid4())[:8]
    context.user_data['quiz_id'] = quiz_id
    context.bot_data.setdefault('quizzes', {})[quiz_id] = {
        'title': context.user_data['title'],
        'desc': context.user_data.get('desc', ''),
        'questions': []
    }

    # Send inline button for first question
    keyboard = [
        [InlineKeyboardButton("➕ Add First Question", callback_data=f"add_question_{quiz_id}")]
    ]
    await update.message.reply_text("Now add your first question using the button below:",
                                    reply_markup=InlineKeyboardMarkup(keyboard))
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
    quiz_id = context.user_data['quiz_id']
    context.bot_data['quizzes'][quiz_id]['questions'].append(q)

    keyboard = [
        [InlineKeyboardButton("➕ Add Another Question", callback_data=f"add_question_{quiz_id}")],
        [InlineKeyboardButton("✅ Done", callback_data=f"done_quiz_{quiz_id}")]
    ]
    await update.message.reply_text(f"Saved ({len(context.bot_data['quizzes'][quiz_id]['questions'])}) questions.\nNext:",
                                    reply_markup=InlineKeyboardMarkup(keyboard))
    return QUESTION

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

async def send_next(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    active = context.chat_data.get('active_quiz')
    if not active: return

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
    if not active: return

    index = active['index'] - 1
    q = active['quiz']['questions'][index]
    selected = poll_answer.option_ids[0] if poll_answer.option_ids else None

    if selected == q['correct']:
        active['scores'][user_id] = active['scores'].get(user_id, 0) + 1

def main():
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^create_quiz$")],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_title)],
            DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_desc_or_skip)],
            QUESTION: [MessageHandler(filters.POLL, save_question)],
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
