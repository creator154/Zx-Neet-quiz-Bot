# bot.py - Official-like Telegram Quiz Bot (timer, shuffle, negative, start in group)
import logging
import os
import uuid
from telegram import (
    Update,
    Poll,
    KeyboardButton,
    KeyboardButtonPollType,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
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

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TITLE, DESC, QUESTION, TIMER, SHUFFLE, NEGATIVE, FINAL_MENU = range(7)
QUESTION_TIMER = 30

TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set!")


# ------------------ Start Command ------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton("Create New Quiz")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Hi! Tap below to create your quiz:", reply_markup=reply_markup)


# ------------------ Create Quiz ------------------
async def create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send quiz title")
    return TITLE


async def save_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['title'] = update.message.text
    await update.message.reply_text("Send description or /skip")
    return DESC


async def save_desc_or_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text != "/skip":
        context.user_data['desc'] = update.message.text

    # Direct poll button
    keyboard = [[KeyboardButton("Add First Question", request_poll=KeyboardButtonPollType(type="quiz"))]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Now add your first question using the button below:", reply_markup=reply_markup)
    context.user_data['questions'] = []
    return QUESTION


async def save_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll = update.message.poll
    if poll.type != Poll.QUIZ:
        await update.message.reply_text("Only quiz mode poll allowed!")
        return QUESTION

    context.user_data['questions'].append({
        'question': poll.question,
        'options': [opt.text for opt in poll.options],
        'correct': poll.correct_option_id,
        'explanation': poll.explanation or ""
    })

    # Next poll / done
    keyboard = [
        [KeyboardButton("Add Next Question", request_poll=KeyboardButtonPollType(type="quiz"))],
        [KeyboardButton("/done")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(f"Saved ({len(context.user_data['questions'])})\nAdd next or /done", reply_markup=reply_markup)
    return QUESTION


# ------------------ Timer ------------------
async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    qs = context.user_data.get('questions', [])
    if not qs:
        await update.message.reply_text("No questions added")
        return ConversationHandler.END

    # Timer selection buttons
    keyboard = [
        [KeyboardButton("10 sec"), KeyboardButton("15 sec"), KeyboardButton("20 sec")],
        [KeyboardButton("30 sec"), KeyboardButton("45 sec"), KeyboardButton("60 sec")],
        [KeyboardButton("Skip timer")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Select time per question (10-60 sec)", reply_markup=reply_markup)
    return TIMER


async def set_timer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "Skip timer":
        timer = 30
    else:
        timer = int(text.split()[0])
    context.user_data['timer'] = timer

    # Shuffle buttons
    keyboard = [
        [KeyboardButton("Shuffle All")],
        [KeyboardButton("No Shuffle")],
        [KeyboardButton("Only Questions"), KeyboardButton("Only Answers")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Shuffle questions and answer options?", reply_markup=reply_markup)
    return SHUFFLE


async def set_shuffle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    shuffle = text != "No Shuffle"
    context.user_data['shuffle'] = shuffle

    # Negative marking buttons
    keyboard = [
        [KeyboardButton("0"), KeyboardButton("0.25"), KeyboardButton("0.5")],
        [KeyboardButton("Skip")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Negative marking per wrong answer?", reply_markup=reply_markup)
    return NEGATIVE


async def set_negative(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "Skip":
        negative = 0
    else:
        negative = float(text)
    context.user_data['negative'] = negative

    # Save quiz and show final menu
    title = context.user_data.get('title')
    desc = context.user_data.get('desc', '')
    qs = context.user_data['questions']
    timer = context.user_data['timer']
    shuffle = context.user_data['shuffle']

    quiz_id = str(uuid.uuid4())[:8]
    context.bot_data.setdefault('quizzes', {})[quiz_id] = {
        'title': title,
        'desc': desc,
        'questions': qs,
        'timer': timer,
        'shuffle': shuffle,
        'negative': negative
    }

    # Final official-like menu
    keyboard = [
        [InlineKeyboardButton("▶ Start Quiz", callback_data=f"start_{quiz_id}")],
        [InlineKeyboardButton("Start Quiz in Group", switch_inline_query_current_chat=f"startquiz {quiz_id}")],
        [InlineKeyboardButton("Quiz Stats", callback_data=f"stats_{quiz_id}")],
        [InlineKeyboardButton("View My Quizzes", callback_data="view_my")],
        [InlineKeyboardButton("Back", callback_data=f"back_{quiz_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"Quiz '{title}' created!", reply_markup=reply_markup)

    context.user_data.clear()
    return ConversationHandler.END


# ------------------ Callback Query Handler ------------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("start_"):
        quiz_id = data.split("_")[1]
        quiz = context.bot_data['quizzes'].get(quiz_id)
        if not quiz:
            await query.edit_message_text("Quiz not found!")
            return
        # Direct start in current chat
        context.chat_data['active_quiz'] = {'quiz': quiz, 'index': 0, 'scores': {}}
        await query.edit_message_text(f"Quiz started: {quiz['title']}")
        await send_next(context, query.message.chat.id)

    elif data.startswith("stats_"):
        quiz_id = data.split("_")[1]
        quiz = context.bot_data['quizzes'].get(quiz_id)
        if not quiz:
            await query.edit_message_text("Quiz not found!")
            return
        await query.edit_message_text(f"Quiz Stats:\nTitle: {quiz['title']}\nQuestions: {len(quiz['questions'])}")

    elif data == "view_my":
        quizzes = context.bot_data.get('quizzes', {})
        text = "My Quizzes:\n" + "\n".join([f"{qid}: {q['title']}" for qid, q in quizzes.items()])
        await query.edit_message_text(text)

    elif data.startswith("back_"):
        quiz_id = data.split("_")[1]
        quiz = context.bot_data['quizzes'].get(quiz_id)
        if quiz:
            # Go back to final menu
            keyboard = [
                [InlineKeyboardButton("▶ Start Quiz", callback_data=f"start_{quiz_id}")],
                [InlineKeyboardButton("Start Quiz in Group", switch_inline_query_current_chat=f"startquiz {quiz_id}")],
                [InlineKeyboardButton("Quiz Stats", callback_data=f"stats_{quiz_id}")],
                [InlineKeyboardButton("View My Quizzes", callback_data="view_my")],
                [InlineKeyboardButton("Back", callback_data=f"back_{quiz_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(f"Quiz '{quiz['title']}' created!", reply_markup=reply_markup)


# ------------------ Send Quiz Questions ------------------
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


# ------------------ Main ------------------
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
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(PollAnswerHandler(handle_answer))

    app.run_polling()


if __name__ == "__main__":
    main()
