from telegram.ext import ConversationHandler, MessageHandler, CallbackQueryHandler, CommandHandler, filters
from keyboards import poll_keyboard, finish_keyboard, timer_keyboard, shuffle_keyboard
from telegram import Update
from telegram.ext import ContextTypes
from database import DB_FILE
import sqlite3

# States
WAITING_POLL, WAITING_TIMER, WAITING_SHUFFLE_Q, WAITING_SHUFFLE_OPT = range(4)

# Start /create command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome! Create your first question:", reply_markup=poll_keyboard())
    return WAITING_POLL

# Handle poll creation
async def receive_poll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll = update.message.poll
    context.user_data['current_poll'] = poll
    await update.message.reply_text("Please set a timer for this question:", reply_markup=timer_keyboard())
    return WAITING_TIMER

# Timer selected
async def timer_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    timer = int(query.data.split("_")[1])
    context.user_data['current_poll_timer'] = timer
    await query.edit_message_text("Shuffle questions?", reply_markup=shuffle_keyboard())
    return WAITING_SHUFFLE_Q

# Shuffle questions
async def shuffle_q(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['shuffle_q'] = query.data == "shuffle_yes"
    await query.edit_message_text("Shuffle options?", reply_markup=shuffle_keyboard())
    return WAITING_SHUFFLE_OPT

# Shuffle options and finish
async def shuffle_opt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['shuffle_opt'] = query.data == "shuffle_yes"

    poll = context.user_data['current_poll']
    timer = context.user_data['current_poll_timer']
    shuffle_q_val = context.user_data['shuffle_q']
    shuffle_opt_val = context.user_data['shuffle_opt']

    # Save to DB
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO quizzes (title) VALUES (?)", ("My Quiz",))
    quiz_id = c.lastrowid
    c.execute("""
        INSERT INTO questions (quiz_id, question, options, correct_option, timer, shuffle_q, shuffle_opt)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        quiz_id,
        poll.question,
        str(poll.options),
        poll.correct_option_id,
        timer,
        int(shuffle_q_val),
        int(shuffle_opt_val)
    ))
    conn.commit()
    conn.close()

    await query.edit_message_text("✅ Question saved! Send /create for next question or /done to finish.", reply_markup=finish_keyboard())
    return WAITING_POLL

# Conversation handler
conv_handler = ConversationHandler(
    entry_points=[CommandHandler("create", start)],
    states={
        WAITING_POLL: [MessageHandler(filters.POLL, receive_poll)],
        WAITING_TIMER: [CallbackQueryHandler(timer_selected)],
        WAITING_SHUFFLE_Q: [CallbackQueryHandler(shuffle_q)],
        WAITING_SHUFFLE_OPT: [CallbackQueryHandler(shuffle_opt)],
    },
    fallbacks=[]
)
