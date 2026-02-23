import logging
import os
import uuid
from collections import defaultdict

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Poll,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    PollAnswerHandler,
    ContextTypes,
    filters,
)

TOKEN = os.environ.get("TELEGRAM_TOKEN")

logging.basicConfig(level=logging.INFO)

# ---------------- START ---------------- #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # Group start with ready system
    if context.args:
        quiz_id = context.args[0]
        quiz = context.bot_data.get("quizzes", {}).get(quiz_id)

        if not quiz:
            await update.message.reply_text("Quiz not found.")
            return

        context.chat_data["waiting"] = {
            "quiz_id": quiz_id,
            "ready": set()
        }

        buttons = [[InlineKeyboardButton("I am ready!", callback_data="ready")]]

        await update.message.reply_text(
            f"🎲 Get ready for '{quiz['title']}'\n\n"
            f"⏱ {quiz['timer']} sec per question\n\n"
            f"Quiz starts when 2 players are ready.",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    # Home screen
    buttons = [
        [InlineKeyboardButton("Create New Quiz", callback_data="create")],
        [InlineKeyboardButton("View My Quizzes", callback_data="myquizzes")],
    ]

    await update.message.reply_text(
        "This bot will help you create a quiz with multiple choice questions.",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ---------------- CREATE QUIZ ---------------- #

async def create_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data["creating"] = True
    await query.edit_message_text("Send quiz title:")


async def receive_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("creating"):
        return

    quiz_id = str(uuid.uuid4())[:8]

    context.bot_data.setdefault("quizzes", {})[quiz_id] = {
        "owner": update.effective_user.id,
        "title": update.message.text,
        "questions": [],
        "timer": 15,
        "shuffle": False,
    }

    context.user_data["creating"] = False

    await show_summary(update, context, quiz_id)


# ---------------- VIEW MY QUIZZES ---------------- #

async def view_my_quizzes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    quizzes = context.bot_data.get("quizzes", {})

    buttons = []

    for qid, quiz in quizzes.items():
        if quiz["owner"] == user_id:
            buttons.append(
                [InlineKeyboardButton(quiz["title"], callback_data=f"open_{qid}")]
            )

    if not buttons:
        await query.edit_message_text("You have no quizzes.")
        return

    buttons.append([InlineKeyboardButton("« Back", callback_data="home")])

    await query.edit_message_text(
        "Your Quizzes:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ---------------- SUMMARY ---------------- #

async def show_summary(update, context, quiz_id):

    quiz = context.bot_data["quizzes"][quiz_id]

    text = (
        f"*{quiz['title']}*\n\n"
        f"🖊 {len(quiz['questions'])} question\n"
        f"⏱ {quiz['timer']} sec\n"
        f"🔀 {'yes' if quiz['shuffle'] else 'no'} shuffle\n\n"
        f"External link:\n"
        f"https://t.me/{context.bot.username}?start={quiz_id}"
    )

    buttons = [
        [InlineKeyboardButton("Start this quiz", callback_data=f"start_{quiz_id}")],
        [InlineKeyboardButton("Start quiz in group",
         url=f"https://t.me/{context.bot.username}?startgroup={quiz_id}")],
        [InlineKeyboardButton("Edit quiz", callback_data=f"edit_{quiz_id}")],
        [InlineKeyboardButton("« Back", callback_data="home")],
    ]

    if hasattr(update, "callback_query"):
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown"
        )


# ---------------- READY SYSTEM ---------------- #

async def ready(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    waiting = context.chat_data.get("waiting")
    if not waiting:
        return

    waiting["ready"].add(query.from_user.id)

    if len(waiting["ready"]) >= 2:
        quiz_id = waiting["quiz_id"]

        context.chat_data["quiz"] = {
            "quiz_id": quiz_id,
            "index": 0,
            "scores": defaultdict(int),
        }

        await query.edit_message_text("🚀 Quiz Starting!")
        await send_question(context, query.message.chat_id)
    else:
        await query.answer("Waiting for 2 players...")


# ---------------- QUIZ ENGINE ---------------- #

async def send_question(context, chat_id):
    session = context.chat_data.get("quiz")
    if not session:
        return

    quiz = context.bot_data["quizzes"][session["quiz_id"]]

    if not quiz["questions"]:
        await context.bot.send_message(chat_id, "No questions added.")
        return

    if session["index"] >= len(quiz["questions"]):
        result = "🏆 Results:\n\n"
        for user, score in session["scores"].items():
            result += f"{user}: {score}\n"

        await context.bot.send_message(chat_id, result)
        context.chat_data.pop("quiz")
        return

    q = quiz["questions"][session["index"]]

    poll = await context.bot.send_poll(
        chat_id,
        question=q["question"],
        options=q["options"],
        type=Poll.QUIZ,
        correct_option_id=q["correct"],
        is_anonymous=False,
        open_period=quiz["timer"],
    )

    session["current_poll"] = poll.poll.id
    session["correct"] = q["correct"]
    session["index"] += 1


async def answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.poll_answer
    session = context.chat_data.get("quiz")
    if not session:
        return

    if answer.poll_id != session.get("current_poll"):
        return

    if answer.option_ids[0] == session["correct"]:
        session["scores"][answer.user.first_name] += 1

    await send_question(context, update.effective_chat.id)


# ---------------- BACK HOME ---------------- #

async def go_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    buttons = [
        [InlineKeyboardButton("Create New Quiz", callback_data="create")],
        [InlineKeyboardButton("View My Quizzes", callback_data="myquizzes")],
    ]

    await query.edit_message_text(
        "This bot will help you create a quiz with multiple choice questions.",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ---------------- MAIN ---------------- #

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(create_quiz, pattern="^create$"))
    app.add_handler(CallbackQueryHandler(view_my_quizzes, pattern="^myquizzes$"))
    app.add_handler(CallbackQueryHandler(go_home, pattern="^home$"))
    app.add_handler(CallbackQueryHandler(ready, pattern="^ready$"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_title))
    app.add_handler(PollAnswerHandler(answer_handler))

    app.run_polling()


if __name__ == "__main__":
    main()
