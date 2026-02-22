# quizbot_official_style.py
import os
import uuid
import logging
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, Poll
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    PollAnswerHandler, ConversationHandler, filters, ContextTypes
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# States
TITLE, DESC, QUESTION, TIMER, NEG_MARK, SHUFFLE, NEXT_DONE = range(7)

# Default quiz timer
DEFAULT_TIMER = 30

TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set!")

# ====== START ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📝 Create New Quiz", callback_data="create_quiz")],
        [InlineKeyboardButton("🎯 Start Quiz in Group", callback_data="start_group")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Hi! Create and share quizzes like official @quizbot.\nChoose an option:",
        reply_markup=reply_markup
    )

# ====== CREATE FLOW ======
async def create_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Enter your quiz title:")
    return TITLE

async def save_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['title'] = update.message.text
    keyboard = [[InlineKeyboardButton("Skip Description", callback_data="skip_desc")]]
    await update.message.reply_text(
        "Send description of your quiz or skip:", 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return DESC

async def save_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        context.user_data['desc'] = ""
    else:
        context.user_data['desc'] = update.message.text
    context.user_data['questions'] = []
    await update.effective_chat.send_message(
        "Send first question as a quiz poll in chat (choose correct answer)."
    )
    return QUESTION

async def save_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll = update.message.poll
    if poll.type != Poll.QUIZ:
        await update.message.reply_text("Please send a **quiz poll**!")
        return QUESTION

    q = {
        'question': poll.question,
        'options': [opt.text for opt in poll.options],
        'correct': poll.correct_option_id,
        'explanation': poll.explanation or ""
    }
    context.user_data['questions'].append(q)

    keyboard = [
        [InlineKeyboardButton("➕ Add Next Question", callback_data="next_question")],
        [InlineKeyboardButton("✅ Finish Quiz", callback_data="finish_quiz")]
    ]
    await update.effective_chat.send_message(
        f"Saved ({len(context.user_data['questions'])}) questions.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return NEXT_DONE

# ====== NEXT / DONE ======
async def next_done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "next_question":
        await query.message.reply_text("Send next quiz poll.")
        return QUESTION
    elif query.data == "finish_quiz":
        quiz_id = str(uuid.uuid4())[:8]
        context.bot_data.setdefault('quizzes', {})[quiz_id] = {
            'title': context.user_data.get('title'),
            'desc': context.user_data.get('desc', ""),
            'questions': context.user_data['questions']
        }
        await query.message.reply_text(
            f"Quiz created!\nID: {quiz_id}\nStart in group using /startquiz {quiz_id}"
        )
        context.user_data.clear()
        return ConversationHandler.END

# ====== START QUIZ IN GROUP ======
async def startquiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("This command works only in groups!")
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
        open_period=DEFAULT_TIMER
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

# ====== MAIN ======
def main():
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(create_callback, pattern="create_quiz")],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_title)],
            DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_desc),
                CallbackQueryHandler(save_desc, pattern="skip_desc")
            ],
            QUESTION: [MessageHandler(filters.POLL, save_question)],
            NEXT_DONE: [CallbackQueryHandler(next_done_callback)]
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("startquiz", startquiz_command))
    app.add_handler(PollAnswerHandler(handle_answer))
    app.add_handler(conv)

    app.run_polling()

if __name__ == "__main__":
    main()
