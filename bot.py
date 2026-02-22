# bot.py - Official-like Quiz Bot
import os
import uuid
import logging
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Poll
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    PollHandler,
    ConversationHandler,
    filters,
    ContextTypes
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# States
TITLE, DESC, CREATE_QUESTION = range(3)

# Environment
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("Please set TELEGRAM_TOKEN env variable!")

# Default per-question timer
QUESTION_TIMER = 30

# ---- Keyboards ----
def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📝 Create New Quiz", callback_data="create_quiz")],
        [InlineKeyboardButton("🎯 View My Quizzes", callback_data="view_quizzes")]
    ]
    return InlineKeyboardMarkup(keyboard)

def question_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Create Question", callback_data="add_question")],
        [InlineKeyboardButton("✅ Done", callback_data="done")]
    ]
    return InlineKeyboardMarkup(keyboard)

def post_done_keyboard(quiz_id):
    keyboard = [
        [InlineKeyboardButton("Start in Group", callback_data=f"start_group_{quiz_id}")],
        [InlineKeyboardButton("Share Quiz", callback_data=f"share_{quiz_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def timer_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("10 sec", callback_data="timer_10"),
         InlineKeyboardButton("20 sec", callback_data="timer_20"),
         InlineKeyboardButton("30 sec", callback_data="timer_30")],
        [InlineKeyboardButton("45 sec", callback_data="timer_45"),
         InlineKeyboardButton("60 sec", callback_data="timer_60")]
    ])

# ---- Handlers ----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome! Choose an option:",
        reply_markup=main_menu_keyboard()
    )

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "create_quiz":
        await query.message.reply_text("Send quiz title:")
        return TITLE
    elif query.data == "view_quizzes":
        quizzes = context.user_data.get("my_quizzes", {})
        if not quizzes:
            await query.message.reply_text("No quizzes found!")
        else:
            text = "\n".join([f"{qid}: {q['title']}" for qid, q in quizzes.items()])
            await query.message.reply_text(f"My Quizzes:\n{text}")
        return ConversationHandler.END

# ---- Title & Description ----
async def save_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["title"] = update.message.text
    await update.message.reply_text("Send quiz description or /skip")
    return DESC

async def save_desc_or_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text != "/skip":
        context.user_data["desc"] = update.message.text
    else:
        context.user_data["desc"] = ""
    context.user_data["questions"] = []
    await update.message.reply_text(
        "Now add questions using the button below:",
        reply_markup=question_keyboard()
    )
    return CREATE_QUESTION

# ---- Questions ----
async def question_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "add_question":
        await query.message.reply_text(
            "Send a quiz-type poll (non-anonymous). Correct answer must be marked."
        )
        return CREATE_QUESTION
    elif query.data == "done":
        quiz_id = str(uuid.uuid4())[:8]
        quiz = {
            "title": context.user_data["title"],
            "desc": context.user_data.get("desc", ""),
            "questions": context.user_data["questions"]
        }
        # Save in user_data for demo
        context.user_data.setdefault("my_quizzes", {})[quiz_id] = quiz
        await query.message.reply_text(
            f"Quiz created!\nID: {quiz_id}",
            reply_markup=post_done_keyboard(quiz_id)
        )
        context.user_data.pop("title", None)
        context.user_data.pop("desc", None)
        context.user_data.pop("questions", None)
        return ConversationHandler.END

# ---- Poll Handling ----
async def poll_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll = update.poll
    if poll.type != Poll.QUIZ:
        await update.effective_message.reply_text("Send only quiz-type poll!")
        return
    q = {
        "question": poll.question,
        "options": [o.text for o in poll.options],
        "correct": poll.correct_option_id
    }
    context.user_data["questions"].append(q)
    await update.effective_message.reply_text(
        f"Saved ({len(context.user_data['questions'])}) questions. Use button to add next or /done",
        reply_markup=question_keyboard()
    )

# ---- Main ----
def main():
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start), CallbackQueryHandler(main_menu_callback)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_title)],
            DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_desc_or_skip)],
            CREATE_QUESTION: [
                CallbackQueryHandler(question_callback),
                MessageHandler(filters.POLL, poll_handler)
            ]
        },
        fallbacks=[]
    )

    app.add_handler(conv)
    app.run_polling()

if __name__ == "__main__":
    main()
