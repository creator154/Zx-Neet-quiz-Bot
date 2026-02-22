from telegram import Update
from telegram.ext import ContextTypes
from states import *
from keyboards import *
from database import get_connection, init_db

# Initialize database on bot startup
init_db()


# -----------------------
# Start quiz creation
# -----------------------
async def create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["questions"] = []
    await update.message.reply_text(
        "Send your first question using button below:",
        reply_markup=poll_keyboard()
    )
    return WAITING_POLL


# -----------------------
# Receive poll/question
# -----------------------
async def receive_poll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll = update.message.poll
    context.user_data["questions"].append(poll)

    await update.message.reply_text(
        f"✅ Question Added ({len(context.user_data['questions'])})",
        reply_markup=finish_keyboard()
    )
    return WAITING_POLL


# -----------------------
# Add Question Again
# -----------------------
async def add_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "Send next question:",
        reply_markup=poll_keyboard()
    )
    return WAITING_POLL


# -----------------------
# Finish quiz creation
# -----------------------
async def finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not context.user_data.get("questions"):
        await query.message.reply_text("Add at least one question.")
        return WAITING_POLL

    await query.message.reply_text(
        "Please select timer for each question:",
        reply_markup=timer_keyboard()
    )
    return WAITING_TIMER


# -----------------------
# Timer selected
# -----------------------
async def timer_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["timer"] = int(query.data.split("_")[1])

    await query.message.reply_text(
        "Shuffle questions?",
        reply_markup=yes_no_keyboard("shuffle_q")
    )
    return WAITING_SHUFFLE_Q


# -----------------------
# Shuffle questions
# -----------------------
async def shuffle_q(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["shuffle_q"] = query.data.endswith("yes")

    await query.message.reply_text(
        "Shuffle answer options?",
        reply_markup=yes_no_keyboard("shuffle_opt")
    )
    return WAITING_SHUFFLE_OPT


# -----------------------
# Shuffle options & Save to DB
# -----------------------
async def shuffle_opt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["shuffle_opt"] = query.data.endswith("yes")

    # -----------------------
    # Save Quiz to DB
    # -----------------------
    questions = context.user_data.get("questions", [])
    timer_sec = context.user_data.get("timer", 20)
    shuffle_q_flag = context.user_data.get("shuffle_q", False)
    shuffle_opt_flag = context.user_data.get("shuffle_opt", False)

    conn = get_connection()
    cursor = conn.cursor()

    # Save quiz
    cursor.execute(
        "INSERT INTO quizzes (title, timer, shuffle_questions, shuffle_options) VALUES (?, ?, ?, ?)",
        ("My Quiz", timer_sec, int(shuffle_q_flag), int(shuffle_opt_flag))
    )
    quiz_id = cursor.lastrowid

    # Save questions
    for poll in questions:
        options = ",".join([opt.text for opt in poll.options])
        correct = poll.correct_option_id
        cursor.execute(
            "INSERT INTO questions (quiz_id, question_text, options, correct_option) VALUES (?, ?, ?, ?)",
            (quiz_id, poll.question, options, correct)
        )

    conn.commit()
    conn.close()

    await query.message.reply_text(
        f"🎉 Quiz Created Successfully!\n\n"
        f"Total Questions: {len(questions)}\n"
        f"Timer: {timer_sec} sec\n"
        f"Shuffle Questions: {shuffle_q_flag}\n"
        f"Shuffle Options: {shuffle_opt_flag}\n\n"
        f"Use /startquiz in your group to begin."
    )

    # Clear temp data
    context.user_data.clear()
    return -1
