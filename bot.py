# bot.py - Complete Telegram Quiz Bot
# Works like official quiz bot, with inline poll button for questions
# Heroku-ready

import logging
import os
import uuid
from telegram import Update, Poll, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    PollAnswerHandler,
    ConversationHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# States for conversation
TITLE, DESC, QUESTION = range(3)
QUESTION_TIMER = 30  # seconds per question

TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set!")

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("📝 Create New Quiz")],
        [KeyboardButton("🎯 View My Quizzes")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Hi! Manage your quizzes below:",
        reply_markup=reply_markup
    )

# Begin quiz creation
async def create_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Enter the *title* of your quiz:", parse_mode="Markdown")
    return TITLE

# Save title
async def save_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['title'] = update.message.text
    await update.message.reply_text("Send a *description* (or /skip):", parse_mode="Markdown")
    return DESC

# Save description
async def save_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text != '/skip':
        context.user_data['desc'] = update.message.text
    else:
        context.user_data['desc'] = ""
    context.user_data['questions'] = []

    # Inline button for first poll question
    keyboard = [
        [InlineKeyboardButton("➕ Add First Question", callback_data="add_question")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Now add your first question using the button below:", reply_markup=reply_markup)
    return QUESTION

# Handle add question button
async def add_question_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Send a poll in *quiz mode* (mark correct answer) for this question.", parse_mode="Markdown")
    return QUESTION

# Save poll question
async def save_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll = update.message.poll
    if poll.type != Poll.QUIZ:
        await update.message.reply_text("⚠️ Only *quiz mode polls* are accepted!", parse_mode="Markdown")
        return QUESTION

    q = {
        'question': poll.question,
        'options': [opt.text for opt in poll.options],
        'correct': poll.correct_option_id,
        'explanation': poll.explanation or ""
    }
    context.user_data['questions'].append(q)

    # Inline buttons for next question or done
    keyboard = [
        [InlineKeyboardButton("➕ Add Another Question", callback_data="add_question")],
        [InlineKeyboardButton("✅ Finish Quiz", callback_data="finish_quiz")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Saved ({len(context.user_data['questions'])}) questions. Send next poll or finish using buttons below:",
        reply_markup=reply_markup
    )
    return QUESTION

# Finish quiz
async def finish_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not context.user_data.get('questions'):
        await query.message.reply_text("No questions added. Quiz cancelled.")
        return ConversationHandler.END

    quiz_id = str(uuid.uuid4())[:8]
    context.bot_data.setdefault('quizzes', {})[quiz_id] = {
        'title': context.user_data.get('title', 'Untitled'),
        'desc': context.user_data.get('desc', ''),
        'questions': context.user_data['questions']
    }

    await query.message.reply_text(
        f"Quiz created!\nID: {quiz_id}\nShare in your group using /startquiz {quiz_id}"
    )
    context.user_data.clear()
    return ConversationHandler.END

# Start quiz in group
async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("Use this command in a *group chat*", parse_mode="Markdown")
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

# Send next question
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

# Handle poll answers
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

    # Conversation handler for creating quizzes
    conv = ConversationHandler(
        entry_points=[CommandHandler("create", create_quiz)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_title)],
            DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_desc)],
            QUESTION: [
                MessageHandler(filters.POLL, save_question),
                CallbackQueryHandler(add_question_button, pattern="add_question"),
                CallbackQueryHandler(finish_quiz, pattern="finish_quiz")
            ]
        },
        fallbacks=[]
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("startquiz", start_quiz))
    app.add_handler(PollAnswerHandler(handle_answer))

    logger.info("Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
