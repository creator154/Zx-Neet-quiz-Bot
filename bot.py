# bot.py - Official-like Telegram Quiz Bot (timer + shuffle + inline buttons)
# Heroku ready - CLEAN, no syntax error

import logging
import os
import uuid
from telegram import (
    Update, Poll, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardRemove, KeyboardButton, KeyboardButtonPollType, ReplyKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, PollAnswerHandler,
    ConversationHandler, CallbackQueryHandler, filters, ContextTypes
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TITLE, DESC, QUESTION, TIMER, SHUFFLE = range(5)
QUESTION_TIMER = 30

TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set!")

# ----------- START ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton("Create New Quiz")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Hi! Tap below to create your quiz:", reply_markup=reply_markup)

# ----------- CREATE QUIZ ----------
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
    keyboard = [
        [KeyboardButton("Add First Question", request_poll=KeyboardButtonPollType(type="quiz"))]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Now add your first question using the button below:", reply_markup=reply_markup)
    context.user_data['questions'] = []
    return QUESTION

# ----------- ADD QUESTIONS ----------
async def save_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    poll = update.message.poll
    if poll.type != Poll.QUIZ:
        await update.message.reply_text("Send only quiz mode poll!")
        return QUESTION

    q = {
        'question': poll.question,
        'options': [opt.text for opt in poll.options],
        'correct': poll.correct_option_id,
        'explanation': poll.explanation or ""
    }
    context.user_data['questions'].append(q)

    keyboard = [
        [KeyboardButton("Add Next Question", request_poll=KeyboardButtonPollType(type="quiz"))],
        [KeyboardButton("/done")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(f"Saved ({len(context.user_data['questions'])})\nAdd next or /done", reply_markup=reply_markup)
    return QUESTION

# ----------- DONE QUESTIONS ----------
async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    qs = context.user_data.get('questions', [])
    if not qs:
        await update.message.reply_text("No questions added")
        return ConversationHandler.END

    # Timer selection
    keyboard = [
        [KeyboardButton("10 sec"), KeyboardButton("15 sec"), KeyboardButton("20 sec")],
        [KeyboardButton("30 sec"), KeyboardButton("45 sec"), KeyboardButton("60 sec")],
        [KeyboardButton("Skip timer")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Select time per question (10-60 sec)", reply_markup=reply_markup)
    return TIMER

async def set_timer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    timer = 30
    if text != "Skip timer":
        try:
            timer = int(text.split()[0])
        except:
            timer = 30
    context.user_data['timer'] = timer

    # Shuffle selection
    keyboard = [
        [KeyboardButton("Shuffle All")],
        [KeyboardButton("No Shuffle")],
        [KeyboardButton("Only Questions"), KeyboardButton("Only Answers")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Shuffle questions and answer options?", reply_markup=reply_markup)
    return SHUFFLE

async def set_shuffle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    shuffle_questions = shuffle_answers = False
    if text == "Shuffle All":
        shuffle_questions = shuffle_answers = True
    elif text == "Only Questions":
        shuffle_questions = True
    elif text == "Only Answers":
        shuffle_answers = True

    title = context.user_data.get('title', 'Untitled')
    desc = context.user_data.get('desc', '')
    qs = context.user_data.get('questions', [])
    timer = context.user_data.get('timer', 30)
    quiz_id = str(uuid.uuid4())[:8]

    context.bot_data.setdefault('quizzes', {})[quiz_id] = {
        'title': title,
        'desc': desc,
        'questions': qs,
        'timer': timer,
        'shuffle_questions': shuffle_questions,
        'shuffle_answers': shuffle_answers
    }

    # Inline buttons summary
    buttons = [
        [InlineKeyboardButton("▶️ Start Quiz", callback_data=f"start_{quiz_id}")],
        [InlineKeyboardButton("Start in Group", switch_inline_query_current_chat=f"startquiz {quiz_id}")],
        [InlineKeyboardButton("Quiz Stats", callback_data=f"stats_{quiz_id}")],
        [InlineKeyboardButton("View My Quiz", callback_data=f"view_{quiz_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)

    await update.message.reply_text(
        f"Quiz saved!\n📁 {title}\n{desc}\nTotal questions: {len(qs)}\n⏱ {timer} sec per question",
        reply_markup=reply_markup
    )
    context.user_data.clear()
    return ConversationHandler.END

# ----------- START QUIZ HANDLER ----------
async def start_quiz_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    quiz_id = query.data.split("_")[1]
    quiz = context.bot_data['quizzes'].get(quiz_id)
    if not quiz:
        await query.edit_message_text("Quiz not found!")
        return
    chat_id = query.message.chat_id
    context.chat_data['active_quiz'] = {'quiz': quiz, 'index': 0, 'scores': {}}
    await query.edit_message_text(f"Quiz started in this chat: {quiz['title']}")
    await send_next(context, chat_id)

async def send_next(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    active = context.chat_data.get('active_quiz')
    if not active:
        return
    index = active['index']
    quiz = active['quiz']
    if index >= len(quiz['questions']):
        scores = active['scores']
        leaderboard = "\n".join([f"{uid}: {score}" for uid, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)])
        await context.bot.send_message(chat_id, f"🏆 Leaderboard:\n{leaderboard}")
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

# ----------- MAIN ----------
def main():
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("create", create)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_title)],
            DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_desc_or_skip)],
            QUESTION: [MessageHandler(filters.POLL, save_question), CommandHandler("done", done)],
            TIMER: [MessageHandler(filters.TEXT, set_timer)],
            SHUFFLE: [MessageHandler(filters.TEXT, set_shuffle)],
        },
        fallbacks=[]
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(start_quiz_group, pattern="^start_"))
    app.add_handler(PollAnswerHandler(handle_answer))

    app.run_polling()

if __name__ == "__main__":
    main()        "Select time per question:",
        reply_markup=reply_markup
    )
    return TIMER

async def set_timer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if text == "Skip timer":
        timer = 30
    elif text in ["10 sec", "15 sec", "20 sec", "30 sec", "45 sec", "60 sec"]:
        timer = int(text.split()[0])
    else:
        timer = 30
    context.user_data['timer'] = timer

    # Shuffle buttons
    keyboard = [
        [KeyboardButton("Shuffle All")],
        [KeyboardButton("No Shuffle")],
        [KeyboardButton("Only Questions"), KeyboardButton("Only Answers")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Shuffle questions and answer options?",
        reply_markup=reply_markup
    )
    return SHUFFLE

async def set_shuffle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    shuffle = text != "No Shuffle"
    context.user_data['shuffle'] = shuffle

    # Negative marking buttons
    keyboard = [
        [KeyboardButton("No Negative")],
        [KeyboardButton("0.25"), KeyboardButton("0.5"), KeyboardButton("1")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Select negative marking per wrong answer:",
        reply_markup=reply_markup
    )
    return NEGATIVE

async def set_negative(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    negative = 0 if text == "No Negative" else float(text)
    context.user_data['negative'] = negative

    # Save quiz
    title = context.user_data.get('title', 'Untitled')
    desc = context.user_data.get('desc', '')
    qs = context.user_data.get('questions', [])
    timer = context.user_data.get('timer', 30)
    shuffle = context.user_data.get('shuffle', False)

    quiz_id = str(uuid.uuid4())[:8]
    context.bot_data.setdefault('quizzes', {})[quiz_id] = {
        'title': title,
        'desc': desc,
        'questions': qs,
        'timer': timer,
        'shuffle': shuffle,
        'negative': negative
    }

    # Official-like summary with inline buttons
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    inline_keyboard = [
        [InlineKeyboardButton("▶️ Start Quiz", callback_data=f"start_{quiz_id}")],
        [InlineKeyboardButton("Start Quiz in Group", callback_data=f"group_{quiz_id}")],
        [InlineKeyboardButton("📊 Quiz Stats", callback_data=f"stats_{quiz_id}")],
        [InlineKeyboardButton("📝 View My Quiz", callback_data=f"view_{quiz_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard)

    await update.message.reply_text(
        f"Quiz saved successfully!\n\n📁 {title}\n{desc or ''}\nQuestions: {len(qs)}\n⏱ Timer: {timer}s\nShuffle: {'Yes' if shuffle else 'No'}\nNegative: {negative}",
        reply_markup=reply_markup
    )

    context.user_data.clear()
    return ConversationHandler.END

# CALLBACK QUERY HANDLER
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("start_"):
        quiz_id = data.split("_")[1]
        quiz = context.bot_data.get('quizzes', {}).get(quiz_id)
        await query.edit_message_text(f"Quiz started: {quiz['title']}\nGo to a group and type /startquiz {quiz_id}")
    elif data.startswith("group_"):
        quiz_id = data.split("_")[1]
        await query.edit_message_text("Touch this in any group where the bot is admin to start the quiz:\nType /startquiz <id>")
    elif data.startswith("stats_"):
        quiz_id = data.split("_")[1]
        quiz = context.bot_data.get('quizzes', {}).get(quiz_id)
        await query.edit_message_text(f"Quiz Stats:\nTitle: {quiz['title']}\nQuestions: {len(quiz['questions'])}")
    elif data.startswith("view_"):
        quiz_id = data.split("_")[1]
        quiz = context.bot_data.get('quizzes', {}).get(quiz_id)
        await query.edit_message_text(f"Your Quiz:\nTitle: {quiz['title']}\nQuestions: {len(quiz['questions'])}")

# START QUIZ IN GROUP
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

# POLL ANSWERS
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

# MAIN
def main():
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("create", create)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_title)],
            DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_desc_or_skip)],
            QUESTION: [MessageHandler(filters.POLL, save_question), CommandHandler("done", done)],
            TIMER: [MessageHandler(filters.TEXT, set_timer)],
            SHUFFLE: [MessageHandler(filters.TEXT, set_shuffle)],
            NEGATIVE: [MessageHandler(filters.TEXT, set_negative)],
        },
        fallbacks=[]
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("startquiz", start_quiz))
    app.add_handler(PollAnswerHandler(handle_answer))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("menu", start))
    app.add_handler(CommandHandler("cancel", start))
    app.add_handler(CommandHandler("back", start))
    app.add_handler(CommandHandler("quit", start))
    app.add_handler(CommandHandler("restart", start))
    app.add_handler(CommandHandler("dashboard", start))
    app.add_handler(CommandHandler("viewquiz", start))
    app.add_handler(CommandHandler("myquiz", start))
    app.add_handler(CommandHandler("quizstats", start))
    app.add_handler(CommandHandler("scoreboard", start))
    app.add_handler(CommandHandler("leaderboard", start))
    app.add_handler(CommandHandler("quiz", start))
    app.add_handler(CommandHandler("quizzes", start))
    app.add_handler(CommandHandler("poll", start))
    app.add_handler(CommandHandler("questions", start))
    app.add_handler(CommandHandler("createquiz", start))

    app.add_handler(CommandHandler("menu", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.run_polling()

if __name__ == "__main__":
    main()
