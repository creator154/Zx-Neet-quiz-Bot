# bot.py - Official-style Quiz Bot with Button-driven Poll Creation
# Heroku-ready, PTB v20+, Inline Buttons for everything

import os
import uuid
import logging
from telegram import (
    Update, Poll, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, PollHandler,
    ConversationHandler, ContextTypes, MessageHandler, filters
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
TITLE, DESC, ADD_Q = range(3)
QUESTION_TIMER = 30  # default 30 sec

TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable not set!")

# --- Keyboards ---
def main_menu():
    keyboard = [
        [InlineKeyboardButton("📝 Create New Quiz", callback_data="create_quiz")],
        [InlineKeyboardButton("🎯 View My Quizzes", callback_data="view_quizzes")]
    ]
    return InlineKeyboardMarkup(keyboard)

def quiz_options():
    keyboard = [
        [InlineKeyboardButton("➕ Add Question (Poll)", callback_data="add_question")],
        [InlineKeyboardButton("✅ Finish & Share Quiz", callback_data="finish_quiz")]
    ]
    return InlineKeyboardMarkup(keyboard)

def timer_options():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("10 sec", callback_data="timer_10"),
         InlineKeyboardButton("20 sec", callback_data="timer_20"),
         InlineKeyboardButton("30 sec", callback_data="timer_30")],
        [InlineKeyboardButton("45 sec", callback_data="timer_45"),
         InlineKeyboardButton("60 sec", callback_data="timer_60")]
    ])

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            "Welcome to Quiz Bot! Choose an option:", 
            reply_markup=main_menu()
        )
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text(
            "Welcome to Quiz Bot! Choose an option:", 
            reply_markup=main_menu()
        )

# Callback for main menu buttons
async def main_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "create_quiz":
        await query.message.reply_text("Send the Quiz Title:")
        return TITLE
    elif query.data == "view_quizzes":
        quizzes = context.user_data.get('quizzes', {})
        if not quizzes:
            await query.message.reply_text("You have no quizzes yet.")
        else:
            text = "Your Quizzes:\n" + "\n".join([f"{k}: {v['title']}" for k, v in quizzes.items()])
            await query.message.reply_text(text)
        return ConversationHandler.END

# Save title
async def save_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['title'] = update.message.text
    await update.message.reply_text("Send a description (or /skip):")
    return DESC

# Save description
async def save_desc_or_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text != "/skip":
        context.user_data['desc'] = update.message.text
    else:
        context.user_data['desc'] = ""
    context.user_data['questions'] = []
    await update.message.reply_text(
        "Now add your first question using button below:", 
        reply_markup=quiz_options()
    )
    return ADD_Q

# Quiz option callbacks (Add Question / Finish)
async def quiz_options_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "add_question":
        await query.message.reply_text(
            "Send a poll in QUIZ mode with correct answer marked!"
        )
        return ADD_Q
    elif query.data == "finish_quiz":
        questions = context.user_data.get('questions', [])
        if not questions:
            await query.message.reply_text("Add at least one question before finishing.")
            return ADD_Q
        quiz_id = str(uuid.uuid4())[:8]
        context.bot_data.setdefault('quizzes', {})[quiz_id] = {
            'title': context.user_data.get('title', 'Untitled'),
            'desc': context.user_data.get('desc', ''),
            'questions': questions
        }
        await query.message.reply_text(
            f"Quiz Created!\nID: {quiz_id}\nStart in group: /startquiz {quiz_id}"
        )
        context.user_data.clear()
        return ConversationHandler.END

# Save poll question
async def save_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll = update.message.poll
    if poll.type != Poll.QUIZ:
        await update.message.reply_text("Send only QUIZ type poll!")
        return ADD_Q
    q = {
        'question': poll.question,
        'options': [o.text for o in poll.options],
        'correct': poll.correct_option_id,
        'explanation': poll.explanation or ""
    }
    context.user_data['questions'].append(q)
    await update.message.reply_text(
        f"Saved ({len(context.user_data['questions'])}) questions. Add another or finish using buttons below.",
        reply_markup=quiz_options()
    )
    return ADD_Q

# Start quiz in group
async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    await send_next_question(context, update.effective_chat.id)

# Send next poll question
async def send_next_question(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
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
        is_anonymous=False,
        open_period=QUESTION_TIMER
    )
    active['index'] += 1

# Poll answers
async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ans = update.poll_answer
    user_id = ans.user.id
    active = context.chat_data.get('active_quiz')
    if not active:
        return
    index = active['index'] - 1
    q = active['quiz']['questions'][index]
    selected = ans.option_ids[0] if ans.option_ids else None
    if selected == q['correct']:
        active['scores'][user_id] = active['scores'].get(user_id, 0) + 1

# --- Main ---
def main():
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start), CallbackQueryHandler(main_menu_cb, pattern="^create_quiz|view_quizzes$")],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_title)],
            DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_desc_or_skip)],
            ADD_Q: [
                CallbackQueryHandler(quiz_options_cb, pattern="^add_question|finish_quiz$"),
                MessageHandler(filters.POLL, save_question)
            ]
        },
        fallbacks=[]
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("startquiz", start_quiz))
    app.add_handler(PollHandler(handle_answer))

    app.run_polling()

if __name__ == "__main__":
    main()
