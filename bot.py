# bot.py - NEET Quiz Bot (Private Create + Group Play + Timer + Leaderboard)
# Heroku deploy ready - No \\~ error, clean code

import logging
import os
import uuid
from telegram import Update, Poll, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    PollAnswerHandler,
    ConversationHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TITLE, DESC, QUESTION = range(3)
QUESTION_TIMER = 30  # seconds per question

# Token Heroku Config Var se aayega
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable not set!")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    welcome = f"Hi {user.first_name}! 👋\nThis bot helps you create quizzes with multiple choice questions."

    # Bottom menu buttons (official jaisa)
    keyboard = [
        [KeyboardButton("Create New Quiz")],
        [KeyboardButton("View My Quizzes")],
        [KeyboardButton("Start quiz in group")],
        [KeyboardButton("Language: English")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

    await update.message.reply_text(welcome, reply_markup=reply_markup)

    # Inline quick actions
    inline_keyboard = [
        [InlineKeyboardButton("Create New Quiz", callback_data="create")],
        [InlineKeyboardButton("View My Quizzes", callback_data="view")],
    ]
    await update.message.reply_text("Quick actions:", reply_markup=InlineKeyboardMarkup(inline_keyboard))

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "create":
        await query.edit_message_text("Quiz title bhejo (e.g., NEET Biology Quiz)")
        return TITLE

    elif query.data == "view":
        quizzes = context.bot_data.get('quizzes', {})
        text = "Your quizzes:\n" + "\n".join([f"• {q['title']} (ID: {qid})" for qid, q in quizzes.items()]) if quizzes else "No quizzes yet"
        await query.edit_message_text(text)

# ───────────── Create Quiz Flow ─────────────

async def save_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['quiz_title'] = update.message.text
    await update.message.reply_text("Description bhejo ya /skip likh do")
    return DESC

async def save_desc_or_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text != '/skip':
        context.user_data['quiz_desc'] = update.message.text
    await update.message.reply_text(
        "Ab questions Telegram poll bana ke bhejo:\n"
        "→ Quiz mode ON\n"
        "→ Correct answer mark karo\n"
        "→ Explanation daal do (optional)\n\n"
        "Done hone pe /done likh dena"
    )
    context.user_data['questions'] = []
    return QUESTION

async def save_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    poll = update.message.poll
    if poll.type != Poll.QUIZ:
        await update.message.reply_text("Sirf quiz mode poll bhejo!")
        return QUESTION

    question_data = {
        'question': poll.question,
        'options': [opt.text for opt in poll.options],
        'correct_option_id': poll.correct_option_id,
        'explanation': poll.explanation or "No explanation"
    }
    context.user_data['questions'].append(question_data)

    await update.message.reply_text(f"Question saved! ({len(context.user_data['questions'])} ab tak)\nNext poll ya /done")
    return QUESTION

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    questions = context.user_data.get('questions', [])
    if not questions:
        await update.message.reply_text("Koi question nahi add kiya.")
        return ConversationHandler.END

    title = context.user_data.get('quiz_title', 'Untitled')
    desc = context.user_data.get('quiz_desc', '')

    quiz_id = str(uuid.uuid4())[:8]

    context.bot_data.setdefault('quizzes', {})[quiz_id] = {
        'title': title,
        'desc': desc,
        'questions': questions
    }

    await update.message.reply_text(
        f"Quiz ban gaya! 🎉\n"
        f"Title: {title}\n"
        f"ID: {quiz_id}\n"
        f"Questions: {len(questions)}\n\n"
        f"Group mein shuru karne ke liye:\n/startquiz {quiz_id}"
    )

    context.user_data.clear()
    return ConversationHandler.END

# ───────────── Group Quiz Start ─────────────

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("Yeh command sirf group mein chalega!")
        return

    if not context.args:
        await update.message.reply_text("Use: /startquiz <quiz_id>")
        return

    quiz_id = context.args[0]
    quiz = context.bot_data.get('quizzes', {}).get(quiz_id)
    if not quiz:
        await update.message.reply_text("Quiz nahi mila. /create se banao.")
        return

    context.chat_data['active_quiz'] = {
        'quiz_id': quiz_id,
        'quiz': quiz,
        'index': 0,
        'scores': {}
    }

    await update.message.reply_text(
        f"Quiz shuru ho raha hai! 🚀\n"
        f"**{quiz['title']}**\n"
        f"{quiz.get('desc', '')}\n"
        f"Total questions: {len(quiz['questions'])}\n"
        "Pehla question aa raha hai..."
    )

    await send_next_question(context, chat.id)

async def send_next_question(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    active = context.chat_data.get('active_quiz')
    if not active:
        return

    index = active['index']
    quiz = active['quiz']

    if index >= len(quiz['questions']):
        scores = active['scores']
        text = "🏆 Quiz Khatam! Leaderboard 🏆\n\n"
        if not scores:
            text += "Koi nahi khela 😢"
        else:
            sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            for pos, (uid, sc) in enumerate(sorted_scores, 1):
                text += f"{pos}. User {uid}: {sc}/{len(quiz['questions'])}\n"
        await context.bot.send_message(chat_id, text)

        context.chat_data.pop('active_quiz', None)
        return

    q = quiz['questions'][index]

    await context.bot.send_poll(
        chat_id=chat_id,
        question=q['question'],
        options=q['options'],
        type=Poll.QUIZ,
        correct_option_id=q['correct_option_id'],
        explanation=q['explanation'],
        is_anonymous=False,
        open_period=QUESTION_TIMER,
        protect_content=True
    )

    await context.bot.send_message(chat_id, f"⏳ Time limit: {QUESTION_TIMER} seconds! Jawab do jaldi!")

    active['index'] += 1

async def handle_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type not in ["group", "supergroup"]:
        return

    poll_answer = update.poll_answer
    user_id = poll_answer.user.id
    chat_id = update.effective_chat.id

    active = context.chat_data.get('active_quiz')
    if not active:
        return

    index = active['index'] - 1
    if index < 0:
        return

    q = active['quiz']['questions'][index]
    selected = poll_answer.option_ids[0] if poll_answer.option_ids else None

    if selected == q['correct_option_id']:
        active['scores'][user_id] = active['scores'].get(user_id, 0) + 1
        await context.bot.send_message(user_id, "✅ Sahi! +1")
    else:
        await context.bot.send_message(user_id, "❌ Galat!")

def main():
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("create", start)],
        states={
            TITLE: [MessageHandler(filters.TEXT & \~filters.COMMAND, save_title)],
            DESC: [MessageHandler(filters.TEXT & \~filters.COMMAND, save_desc_or_skip)],
            QUESTION: [MessageHandler(filters.POLL, save_question), CommandHandler("done", done)],
        },
        fallbacks=[]
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("startquiz", start_quiz))
    application.add_handler(PollAnswerHandler(handle_quiz_answer))
    application.add_handler(CallbackQueryHandler(callback_handler))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
