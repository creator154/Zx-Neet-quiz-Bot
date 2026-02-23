import logging
import os
import uuid
import random

from telegram import (
    Update,
    Poll,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
    KeyboardButtonPollType,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    PollAnswerHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ---------------- CONFIG ---------------- #

TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set!")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

TITLE, DESC, QUESTION, TIMER, SHUFFLE = range(5)

# ---------------- START ---------------- #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # Deep link group start
    if context.args:
        quiz_id = context.args[0]
        quiz = context.bot_data.get("quizzes", {}).get(quiz_id)

        if not quiz:
            await update.message.reply_text("Quiz not found.")
            return

        context.chat_data["quiz"] = {
            "index": 0,
            "data": quiz,
        }

        await update.message.reply_text(
            f"Starting: {quiz['title']}",
            reply_markup=ReplyKeyboardRemove(),
        )

        await send_question(context, update.effective_chat.id)
        return

    keyboard = [[KeyboardButton("Create Quiz")]]
    await update.message.reply_text(
        "Welcome!\nClick below to create quiz.",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )


# ---------------- CREATE FLOW ---------------- #

async def create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send quiz title:", reply_markup=ReplyKeyboardRemove())
    return TITLE


async def save_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["title"] = update.message.text
    context.user_data["questions"] = []
    await update.message.reply_text("Send description or /skip")
    return DESC


async def save_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["desc"] = update.message.text
    return await ask_question(update)


async def skip_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["desc"] = ""
    return await ask_question(update)


async def ask_question(update):
    keyboard = [[KeyboardButton("Add Question", request_poll=KeyboardButtonPollType(type="quiz"))]]
    await update.message.reply_text(
        "Add question using Quiz Poll.",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )
    return QUESTION


async def save_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll = update.message.poll

    if poll.type != "quiz":
        await update.message.reply_text("Only quiz type allowed.")
        return QUESTION

    question_data = {
        "question": poll.question,
        "options": [opt.text for opt in poll.options],
        "correct": poll.correct_option_id,
        "explanation": poll.explanation or "",
    }

    context.user_data["questions"].append(question_data)

    await update.message.reply_text(
        f"Saved {len(context.user_data['questions'])} questions.\nSend next or /done"
    )

    return QUESTION


# ---------------- DONE ---------------- #

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data["questions"]:
        await update.message.reply_text("No questions added.")
        return ConversationHandler.END

    keyboard = [
        [KeyboardButton("10"), KeyboardButton("15"), KeyboardButton("20")],
        [KeyboardButton("30"), KeyboardButton("45"), KeyboardButton("1 min")],
    ]

    await update.message.reply_text(
        "Select timer per question:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )

    return TIMER


async def set_timer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "1 min":
        context.user_data["timer"] = 60
    else:
        context.user_data["timer"] = int(text)

    keyboard = [
        [KeyboardButton("Shuffle All")],
        [KeyboardButton("No Shuffle")],
    ]

    await update.message.reply_text(
        "Shuffle questions?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )

    return SHUFFLE


async def set_shuffle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "Shuffle All":
        random.shuffle(context.user_data["questions"])

    quiz_id = str(uuid.uuid4())[:8]

    context.bot_data.setdefault("quizzes", {})[quiz_id] = {
        "title": context.user_data["title"],
        "desc": context.user_data["desc"],
        "questions": context.user_data["questions"],
        "timer": context.user_data["timer"],
    }

    buttons = [
        [InlineKeyboardButton("Start Quiz", callback_data=f"start_{quiz_id}")],
        [InlineKeyboardButton(
            "Start In Group",
            url=f"https://t.me/{context.bot.username}?startgroup={quiz_id}"
        )],
    ]

    await update.message.reply_text(
        "Quiz Created Successfully!",
        reply_markup=InlineKeyboardMarkup(buttons),
    )

    context.user_data.clear()
    return ConversationHandler.END


# ---------------- START QUIZ ---------------- #

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    quiz_id = query.data.split("_")[1]
    quiz = context.bot_data.get("quizzes", {}).get(quiz_id)

    if not quiz:
        await query.edit_message_text("Quiz not found.")
        return

    context.chat_data["quiz"] = {
        "index": 0,
        "data": quiz,
    }

    await query.edit_message_text(f"Starting: {quiz['title']}")
    await send_question(context, query.message.chat_id)


async def send_question(context, chat_id):
    quiz_session = context.chat_data.get("quiz")
    if not quiz_session:
        return

    quiz = quiz_session["data"]

    if quiz_session["index"] >= len(quiz["questions"]):
        await context.bot.send_message(chat_id, "Quiz Finished!")
        context.chat_data.pop("quiz")
        return

    q = quiz["questions"][quiz_session["index"]]

    await context.bot.send_poll(
        chat_id=chat_id,
        question=q["question"],
        options=q["options"],
        type=Poll.QUIZ,
        correct_option_id=q["correct"],
        explanation=q["explanation"],
        is_anonymous=False,
        open_period=quiz["timer"],
    )

    quiz_session["index"] += 1


async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for chat_id in list(context.application.chat_data.keys()):
        await send_question(context, chat_id)


# ---------------- MAIN ---------------- #

def main():
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("create", create),
            MessageHandler(filters.Regex("^Create Quiz$"), create),
        ],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_title)],
            DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_desc),
                CommandHandler("skip", skip_desc),
            ],
            QUESTION: [
                MessageHandler(filters.POLL, save_question),
                CommandHandler("done", done),
            ],
            TIMER: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_timer)],
            SHUFFLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_shuffle)],
        },
        fallbacks=[],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(start_quiz, pattern="^start_"))
    app.add_handler(PollAnswerHandler(handle_answer))

    app.run_polling()


if __name__ == "__main__":
    main()
