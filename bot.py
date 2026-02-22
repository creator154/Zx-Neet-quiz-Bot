# bot.py - Official-like Telegram Quiz Bot with group start & leaderboard
# Heroku ready - CLEAN, no syntax error

import logging
import os
import uuid
from telegram import Update, Poll, ReplyKeyboardMarkup, KeyboardButton, KeyboardButtonPollType, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
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

# States
TITLE, DESC, QUESTION, TIMER, SHUFFLE, NEGATIVE = range(6)
QUESTION_TIMER = 30

TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set!")

# /start handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton("Create New Quiz")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Hi! Tap below to create your quiz:",
        reply_markup=reply_markup
    )

# Quiz creation flow
async def create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send quiz title")
    return TITLE

async def save_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['title'] = update.message.text
    await update.message.reply_text("Send description or /skip")
    return DESC

async def save_desc_or_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text != '/skip':
        context.user_data['desc'] = update.message.text

    # Poll button for first question
    keyboard = [[KeyboardButton("Add First Question", request_poll=KeyboardButtonPollType(type="quiz"))]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    context.user_data['questions'] = []

    await update.message.reply_text(
        "Now add your first question using the button below (Quiz mode ON, mark correct answer):",
        reply_markup=reply_markup
    )
    return QUESTION

async def save_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    # Next poll or done
    keyboard = [
        [KeyboardButton("Add Next Question", request_poll=KeyboardButtonPollType(type="quiz"))],
        [KeyboardButton("/done")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        f"Saved ({len(context.user_data['questions'])})\nAdd next or /done",
        reply_markup=reply_markup
    )
    return QUESTION

# Done → timer → shuffle → negative → summary
async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('questions'):
        await update.message.reply_text("No questions added")
        return ConversationHandler.END

    # Timer buttons
    keyboard = [
        [KeyboardButton("10 sec"), KeyboardButton("15 sec"), KeyboardButton("20 sec")],
        [KeyboardButton("30 sec"), KeyboardButton("45 sec"), KeyboardButton("60 sec")],
        [KeyboardButton("Skip timer")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Select time per question:",
        reply_markup=reply_markup
    )
    return TIMER

async def set_timer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    timer_map = {"10 sec":10, "15 sec":15, "20 sec":20, "30 sec":30, "45 sec":45, "60 sec":60}
    timer = timer_map.get(text, 30)
    context.user_data['timer'] = timer

    # Shuffle buttons
    keyboard = [
        [KeyboardButton("Shuffle All")],
        [KeyboardButton("No Shuffle")],
        [KeyboardButton("Only Questions"), KeyboardButton("Only Answers")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Shuffle questions/answers?", reply_markup=reply_markup)
    return SHUFFLE

async def set_shuffle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    shuffle = text != "No Shuffle"
    context.user_data['shuffle'] = shuffle

    # Negative marking buttons
    keyboard = [
        [KeyboardButton("No Negative"), KeyboardButton("0.25"), KeyboardButton("0.5")],
        [KeyboardButton("1")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Set negative marking (per wrong answer):", reply_markup=reply_markup)
    return NEGATIVE

async def set_negative(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    try:
        negative = float(text) if text != "No Negative" else 0.0
    except:
        negative = 0.0
    context.user_data['negative'] = negative

    # Save quiz
    title = context.user_data.get('title', 'Untitled')
    desc = context.user_data.get('desc', '')
    questions = context.user_data.get('questions', [])
    timer = context.user_data.get('timer', 30)
    shuffle = context.user_data.get('shuffle', False)

    quiz_id = str(uuid.uuid4())[:8]
    context.bot_data.setdefault('quizzes', {})[quiz_id] = {
        'title': title,
        'desc': desc,
        'questions': questions,
        'timer': timer,
        'shuffle': shuffle,
        'negative': negative
    }

    # Summary + inline buttons
    inline_keyboard = [
        [InlineKeyboardButton("▶️ Start Quiz", callback_data=f"start_{quiz_id}")],
        [InlineKeyboardButton("Start in Group", switch_inline_query_current_chat=f"startquiz {quiz_id}")],
        [InlineKeyboardButton("Quiz Stats", callback_data=f"stats_{quiz_id}")],
        [InlineKeyboardButton("View My Quizzes", callback_data="view_my_quizzes")],
        [InlineKeyboardButton("Back", callback_data="back_to_start")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard)

    await update.message.reply_text(
        f"Quiz saved successfully!\n\n📁 {title}\n{desc}\nQuestions: {len(questions)}\nTimer: {timer}s\nShuffle: {'Yes' if shuffle else 'No'}\nNegative: {negative}\nQuiz ID: {quiz_id}",
        reply_markup=reply_markup
    )
    context.user_data.clear()
    return ConversationHandler.END

# Start quiz in group or private
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("start_"):
        quiz_id = data.split("_")[1]
        quiz = context.bot_data.get('quizzes', {}).get(quiz_id)
        if quiz:
            context.chat_data['active_quiz'] = {'quiz': quiz, 'index': 0, 'scores': {}}
            await query.edit_message_text(f"Quiz started: {quiz['title']}")
            await send_next(context, query.message.chat.id)

    elif data.startswith("stats_"):
        quiz_id = data.split("_")[1]
        await query.edit_message_text(f"Stats for quiz {quiz_id} coming soon!")

    elif data == "view_my_quizzes":
        quizzes = context.bot_data.get('quizzes', {})
        if quizzes:
            text = "Your quizzes:\n" + "\n".join([f"{k}: {v['title']}" for k,v in quizzes.items()])
        else:
            text = "No quizzes found."
        await query.edit_message_text(text)

    elif data == "back_to_start":
        await start(update=query, context=context)

# Send next question
async def send_next(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    active = context.chat_data.get('active_quiz')
    if not active:
        return

    index = active['index']
    quiz = active['quiz']

    if index >= len(quiz['questions']):
        # Leaderboard
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

    conv = ConversationHandler(
        entry_points=[CommandHandler("create", create)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_title)],
            DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_desc_or_skip)],
            QUESTION: [MessageHandler(filters.POLL, save_question), CommandHandler("done", done)],
            TIMER: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_timer)],
            SHUFFLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_shuffle)],
            NEGATIVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_negative)]
        },
        fallbacks=[]
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("startquiz", lambda u,c: None))  # placeholder
    app.add_handler(PollAnswerHandler(handle_answer))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.run_polling()

if __name__ == '__main__':
    main()
