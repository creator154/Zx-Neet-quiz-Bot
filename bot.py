import logging
import os
import uuid
import random
from collections import defaultdict

from telegram import (
    Update, Poll,
    InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, KeyboardButtonPollType,
    ReplyKeyboardMarkup
)

from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    PollAnswerHandler, ConversationHandler,
    CallbackQueryHandler, ContextTypes, filters
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TITLE, DESC, QUESTION, TIMER, SHUFFLE, NEGATIVE = range(6)
DEFAULT_TIMER = 30

TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set!")

# ================= HOME =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("Create New Quiz")],
        [KeyboardButton("View My Quizzes")]
    ]
    await update.message.reply_text(
        "🏠 Welcome to Quiz Bot",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# ================= CREATE FLOW =================

async def create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Send quiz title:")
    return TITLE

async def save_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["title"] = update.message.text
    await update.message.reply_text("Send description or /skip")
    return DESC

async def save_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["desc"] = update.message.text
    return await ask_question(update, context)

async def skip_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["desc"] = ""
    return await ask_question(update, context)

async def ask_question(update, context):
    context.user_data["questions"] = []

    keyboard = [[KeyboardButton(
        "➕ Add Question",
        request_poll=KeyboardButtonPollType(type="quiz")
    )]]

    await update.message.reply_text(
        "Add quiz questions.\nType /done when finished.",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return QUESTION

async def save_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll = update.message.poll

    if poll.type != Poll.QUIZ:
        await update.message.reply_text("Send QUIZ type poll only.")
        return QUESTION

    context.user_data["questions"].append({
        "question": poll.question,
        "options": [o.text for o in poll.options],
        "correct": poll.correct_option_id,
        "explanation": poll.explanation or ""
    })

    await update.message.reply_text(
        f"✅ Question Saved ({len(context.user_data['questions'])})"
    )
    return QUESTION

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("questions"):
        await update.message.reply_text("Add at least 1 question.")
        return QUESTION

    keyboard = [
        [KeyboardButton("15 sec"), KeyboardButton("30 sec")],
        [KeyboardButton("45 sec"), KeyboardButton("60 sec")]
    ]

    await update.message.reply_text(
        "Select timer:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return TIMER

async def set_timer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    timer_map = {"15 sec":15, "30 sec":30, "45 sec":45, "60 sec":60}
    context.user_data["timer"] = timer_map.get(update.message.text, DEFAULT_TIMER)

    keyboard = [
        [KeyboardButton("Shuffle"), KeyboardButton("No Shuffle")]
    ]

    await update.message.reply_text(
        "Shuffle questions?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return SHUFFLE

async def set_shuffle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["shuffle"] = update.message.text == "Shuffle"

    keyboard = [
        [KeyboardButton("Negative 0"),
         KeyboardButton("Negative 0.5"),
         KeyboardButton("Negative 1")]
    ]

    await update.message.reply_text(
        "Select negative marking:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return NEGATIVE

async def set_negative(update: Update, context: ContextTypes.DEFAULT_TYPE):
    neg_map = {"Negative 0":0, "Negative 0.5":0.5, "Negative 1":1}
    context.user_data["negative"] = neg_map.get(update.message.text, 0)

    quiz_id = str(uuid.uuid4())[:8]

    context.bot_data.setdefault("quizzes", {})[quiz_id] = {
        "owner": update.effective_user.id,
        "title": context.user_data["title"],
        "desc": context.user_data.get("desc",""),
        "questions": context.user_data["questions"],
        "timer": context.user_data.get("timer", DEFAULT_TIMER),
        "shuffle": context.user_data.get("shuffle", False),
        "negative": context.user_data.get("negative", 0)
    }

    quiz = context.bot_data["quizzes"][quiz_id]

    text = (
        f"📘 {quiz['title']}\n"
        f"{quiz['desc']}\n\n"
        f"Questions: {len(quiz['questions'])}\n"
        f"⏱ {quiz['timer']} sec\n"
        f"Shuffle: {quiz['shuffle']}\n"
        f"Negative: {quiz['negative']}"
    )

    keyboard = [
        [InlineKeyboardButton("▶ Start Quiz in Group", callback_data=f"start_{quiz_id}")],
        [InlineKeyboardButton("🔙 Back", callback_data="home")]
    ]

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    context.user_data.clear()
    return ConversationHandler.END

# ================= READY SYSTEM =================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "home":
        await start(query, context)
        return

    if data.startswith("start_"):
        quiz_id = data.split("_")[1]
        quiz = context.bot_data["quizzes"].get(quiz_id)

        context.chat_data["waiting"] = {
            "quiz": quiz,
            "ready": set()
        }

        keyboard = [
            [InlineKeyboardButton("✅ I'm Ready", callback_data="ready")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
        ]

        await query.edit_message_text(
            "👥 Players Ready: 0/2\nPress I'm Ready",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "ready":
        waiting = context.chat_data.get("waiting")
        if not waiting:
            return

        waiting["ready"].add(query.from_user.id)
        count = len(waiting["ready"])

        if count >= 2:
            context.chat_data["active"] = {
                "quiz": waiting["quiz"],
                "index": 0,
                "scores": defaultdict(float)
            }
            context.chat_data.pop("waiting")
            await query.edit_message_text("🚀 Quiz Starting...")
            await send_next(context, query.message.chat.id)
        else:
            keyboard = [
                [InlineKeyboardButton("✅ I'm Ready", callback_data="ready")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
            ]
            await query.edit_message_text(
                f"👥 Players Ready: {count}/2",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    elif data == "cancel":
        context.chat_data.pop("waiting", None)
        await query.edit_message_text("❌ Quiz Cancelled")

# ================= QUIZ ENGINE =================

async def send_next(context, chat_id):
    active = context.chat_data.get("active")
    quiz = active["quiz"]
    index = active["index"]

    if quiz["shuffle"]:
        random.shuffle(quiz["questions"])

    if index >= len(quiz["questions"]):
        text = "🏆 Leaderboard:\n\n"
        for uid, score in sorted(active["scores"].items(), key=lambda x:x[1], reverse=True):
            text += f"{uid}: {score}\n"
        await context.bot.send_message(chat_id, text)
        context.chat_data.clear()
        return

    q = quiz["questions"][index]

    await context.bot.send_poll(
        chat_id,
        question=q["question"],
        options=q["options"],
        type=Poll.QUIZ,
        correct_option_id=q["correct"],
        explanation=q["explanation"],
        is_anonymous=False,
        open_period=quiz["timer"]
    )

    active["index"] += 1

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll_answer = update.poll_answer
    active = context.chat_data.get("active")
    if not active:
        return

    index = active["index"] - 1
    quiz = active["quiz"]
    question = quiz["questions"][index]

    selected = poll_answer.option_ids[0] if poll_answer.option_ids else None
    uid = poll_answer.user.id

    if selected == question["correct"]:
        active["scores"][uid] += 1
    else:
        active["scores"][uid] -= quiz["negative"]

# ================= MAIN =================

def main():
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Create New Quiz$"), create)],
        states={
            TITLE:[MessageHandler(filters.TEXT & ~filters.COMMAND, save_title)],
            DESC:[
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_desc),
                CommandHandler("skip", skip_desc)
            ],
            QUESTION:[
                MessageHandler(filters.POLL, save_question),
                CommandHandler("done", done)
            ],
            TIMER:[MessageHandler(filters.TEXT, set_timer)],
            SHUFFLE:[MessageHandler(filters.TEXT, set_shuffle)],
            NEGATIVE:[MessageHandler(filters.TEXT, set_negative)],
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(PollAnswerHandler(handle_answer))

    app.run_polling()

if __name__ == "__main__":
    main()
