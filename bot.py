# bot.py - Telegram Quiz Bot (Official style)
import logging
import os
import uuid
from telegram import (
    Update,
    Poll,
    ReplyKeyboardMarkup,
    KeyboardButton,
    KeyboardButtonPollType,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    PollAnswerHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Conversation states
TITLE, DESC, CREATE_QUESTION = range(3)
QUESTION_TIMER = 30  # default 30 sec per question

TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set!")

# ----- Start -----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("📝 Create New Quiz")],
        [KeyboardButton("🎯 View My Quizzes")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Welcome! Manage your quizzes below:",
        reply_markup=reply_markup
    )

# ----- Create Quiz -----
async def create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send the **quiz title**:")
    return TITLE

async def save_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['title'] = update.message.text
    await update.message.reply_text("Send a **description** or /skip:")
    return DESC

async def save_desc_or_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text != "/skip":
        context.user_data["desc"] = update.message.text
    else:
        context.user_data["desc"] = ""

    context.user_data["questions"] = []

    # ✅ Telegram native poll button for creating quiz questions
    poll_keyboard = [
        [KeyboardButton(
            text="➕ Create Question (Quiz Poll)",
            request_poll=KeyboardButtonPollType(type="quiz")
        )],
        [KeyboardButton("✅ Done")]
    ]
    reply_markup = ReplyKeyboardMarkup(poll_keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "Now add questions using the button below:",
        reply_markup=reply_markup
    )
    return CREATE_QUESTION

# ----- Handle Poll Questions -----
async def save_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll = update.message.poll
    if poll.type != Poll.QUIZ:
        await update.message.reply_text("⚠️ Only **quiz polls** are allowed!")
        return CREATE_QUESTION

    q = {
        "question": poll.question,
        "options": [opt.text for opt in poll.options],
        "correct": poll.correct_option_id,
        "explanation": poll.explanation or ""
    }
    context.user_data["questions"].append(q)
    await update.message.reply_text(
        f"Saved ({len(context.user_data['questions'])}) question(s).\nAdd next question or /done"
    )
    return CREATE_QUESTION

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    qs = context.user_data.get("questions", [])
    if not qs:
        await update.message.reply_text("No questions added. Quiz cancelled.")
        return ConversationHandler.END

    title = context.user_data.get("title", "Untitled")
    desc = context.user_data.get("desc", "")
    quiz_id = str(uuid.uuid4())[:8]

    context.bot_data.setdefault("quizzes", {})[quiz_id] = {
        "title": title,
        "desc": desc,
        "questions": qs
    }

    # ✅ Finish message + Start in group button
    start_group_btn = InlineKeyboardMarkup(
        [[InlineKeyboardButton("▶️ Start Quiz in Group", callback_data=f"start_{quiz_id}")]]
    )
    await update.message.reply_text(
        f"Quiz created!\nID: {quiz_id}",
        reply_markup=start_group_btn
    )

    context.user_data.clear()
    return ConversationHandler.END

# ----- Poll Answer Handling -----
async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll_answer = update.poll_answer
    user_id = poll_answer.user.id
    active = context.chat_data.get("active_quiz")
    if not active:
        return

    index = active["index"] - 1
    q = active["quiz"]["questions"][index]
    selected = poll_answer.option_ids[0] if poll_answer.option_ids else None

    if selected == q["correct"]:
        active["scores"][user_id] = active["scores"].get(user_id, 0) + 1

# ----- Main -----
def main():
    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("create", create)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_title)],
            DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_desc_or_skip)],
            CREATE_QUESTION: [
                MessageHandler(filters.POLL, save_question),
                MessageHandler(filters.Regex("✅ Done"), done)
            ],
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(PollAnswerHandler(handle_answer))

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
