import logging
import os
import uuid
import random
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
    ConversationHandler,
    ContextTypes,
    filters,
)

TOKEN = os.environ.get("TELEGRAM_TOKEN")
logging.basicConfig(level=logging.INFO)

# ===== STATES =====
TITLE, DESCRIPTION, QUESTION, TIMER, SHUFFLE = range(5)


# ================= START ================= #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # group start
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
            f"🎲 {quiz['title']}\n\n"
            f"{quiz['description']}\n\n"
            f"Waiting for 2 players...",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    buttons = [
        [InlineKeyboardButton("Create New Quiz", callback_data="create")],
        [InlineKeyboardButton("View My Quizzes", callback_data="myquizzes")],
    ]

    await update.message.reply_text(
        "Welcome to Quiz Creator Bot",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ================= CREATE FLOW ================= #

async def create_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data.clear()
    context.user_data["quiz"] = {"questions": []}

    await query.edit_message_text("Send quiz title:")
    return TITLE


async def receive_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["quiz"]["title"] = update.message.text
    await update.message.reply_text("Send quiz description:")
    return DESCRIPTION


async def receive_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["quiz"]["description"] = update.message.text
    await update.message.reply_text(
        "Now send me quiz questions as QUIZ polls.\n\n"
        "Use Telegram poll → Select QUIZ → Send.\n\n"
        "When done type /done\n"
        "Use /undo to remove last question."
    )
    return QUESTION


async def receive_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll = update.message.poll

    if poll.type != "quiz":
        await update.message.reply_text("Send QUIZ type poll only.")
        return QUESTION

    context.user_data["quiz"]["questions"].append({
        "question": poll.question,
        "options": [o.text for o in poll.options],
        "correct": poll.correct_option_id,
    })

    await update.message.reply_text(
        f"Question added ✅ ({len(context.user_data['quiz']['questions'])})"
    )
    return QUESTION


async def undo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data["quiz"]["questions"]:
        context.user_data["quiz"]["questions"].pop()
        await update.message.reply_text("Last question removed.")
    return QUESTION


async def done_questions(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.user_data["quiz"]["questions"]:
        await update.message.reply_text("Add at least one question.")
        return QUESTION

    buttons = [
        [InlineKeyboardButton("15 sec", callback_data="15")],
        [InlineKeyboardButton("30 sec", callback_data="30")],
        [InlineKeyboardButton("60 sec", callback_data="60")],
    ]

    await update.message.reply_text(
        "Select timer per question:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return TIMER


async def set_timer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data["quiz"]["timer"] = int(query.data)

    buttons = [
        [InlineKeyboardButton("Shuffle Questions", callback_data="shuffle_yes")],
        [InlineKeyboardButton("Keep Order", callback_data="shuffle_no")],
    ]

    await query.edit_message_text(
        "Shuffle questions?",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return SHUFFLE


async def set_shuffle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data["quiz"]["shuffle"] = query.data == "shuffle_yes"

    quiz_id = str(uuid.uuid4())[:8]
    context.bot_data.setdefault("quizzes", {})[quiz_id] = context.user_data["quiz"]

    await show_summary(update, context, quiz_id)

    return ConversationHandler.END


# ================= SUMMARY ================= #

async def show_summary(update, context, quiz_id):

    quiz = context.bot_data["quizzes"][quiz_id]

    text = (
        f"📘 {quiz['title']}\n\n"
        f"{quiz['description']}\n\n"
        f"Questions: {len(quiz['questions'])}\n"
        f"Timer: {quiz['timer']} sec\n"
        f"Shuffle: {quiz['shuffle']}\n\n"
        f"Link:\n"
        f"https://t.me/{context.bot.username}?start={quiz_id}"
    )

    buttons = [
        [InlineKeyboardButton("Start Quiz (Private)", callback_data=f"start_{quiz_id}")],
        [InlineKeyboardButton(
            "Start Quiz in Group",
            url=f"https://t.me/{context.bot.username}?startgroup={quiz_id}"
        )],
    ]

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))


# ================= READY + QUIZ ENGINE ================= #

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
            "scores": defaultdict(int)
        }
        await query.edit_message_text("🚀 Quiz Starting!")
        await send_question(context, query.message.chat_id)


async def send_question(context, chat_id):

    session = context.chat_data["quiz"]
    quiz = context.bot_data["quizzes"][session["quiz_id"]]

    questions = quiz["questions"]

    if quiz["shuffle"]:
        random.shuffle(questions)

    if session["index"] >= len(questions):
        result = "🏆 Results:\n\n"
        for user, score in session["scores"].items():
            result += f"{user}: {score}\n"

        await context.bot.send_message(chat_id, result)
        context.chat_data.clear()
        return

    q = questions[session["index"]]

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

    if answer.poll_id != session["current_poll"]:
        return

    if answer.option_ids[0] == session["correct"]:
        session["scores"][answer.user.first_name] += 1

    await send_question(context, update.effective_chat.id)


# ================= MAIN ================= #

def main():
    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(create_quiz, pattern="^create$")],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_title)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_description)],
            QUESTION: [
                MessageHandler(filters.POLL, receive_question),
                CommandHandler("done", done_questions),
                CommandHandler("undo", undo),
            ],
            TIMER: [CallbackQueryHandler(set_timer)],
            SHUFFLE: [CallbackQueryHandler(set_shuffle)],
        },
        fallbacks=[],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(ready, pattern="^ready$"))
    app.add_handler(PollAnswerHandler(answer_handler))

    app.run_polling()


if __name__ == "__main__":
    main()
