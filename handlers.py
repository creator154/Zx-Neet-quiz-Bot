from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    filters,
)
from states import *
from keyboards import *

# Start quiz creation
async def create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["questions"] = []
    await update.message.reply_text(
        "Send your first question using button below:",
        reply_markup=poll_keyboard()
    )
    return WAITING_POLL


# Receive poll
async def receive_poll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll = update.message.poll
    context.user_data["questions"].append(poll)

    await update.message.reply_text(
        f"✅ Question Added ({len(context.user_data['questions'])})",
        reply_markup=finish_keyboard()
    )

    return WAITING_POLL


# Add Question again
async def add_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "Send next question:",
        reply_markup=poll_keyboard()
    )

    return WAITING_POLL


# Finish pressed
async def finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not context.user_data["questions"]:
        await query.message.reply_text("Add at least one question.")
        return WAITING_POLL

    await query.message.reply_text(
        "Select timer for questions:",
        reply_markup=timer_keyboard()
    )

    return WAITING_TIMER


# Timer selected
async def timer_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    timer = int(query.data.split("_")[1])
    context.user_data["timer"] = timer

    await query.message.reply_text(
        "Shuffle questions?",
        reply_markup=yes_no_keyboard("shuffle_q")
    )

    return WAITING_SHUFFLE_Q


# Shuffle questions
async def shuffle_q(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data["shuffle_q"] = query.data.endswith("yes")

    await query.message.reply_text(
        "Shuffle answer options?",
        reply_markup=yes_no_keyboard("shuffle_opt")
    )

    return WAITING_SHUFFLE_OPT


# Shuffle options
async def shuffle_opt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data["shuffle_opt"] = query.data.endswith("yes")

    total = len(context.user_data["questions"])

    await query.message.reply_text(
        f"🎉 Quiz Created Successfully!\n\n"
        f"Total Questions: {total}\n"
        f"Timer: {context.user_data['timer']} sec\n"
        f"Shuffle Questions: {context.user_data['shuffle_q']}\n"
        f"Shuffle Options: {context.user_data['shuffle_opt']}\n\n"
        f"Now use /startquiz in group to begin."
    )

    context.user_data.clear()
    return ConversationHandler.END
