# bot.py - Official-style NEET Quiz Bot for Telegram

import logging
import os
import uuid
from telegram import Update, Poll, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    PollAnswerHandler,
    ConversationHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)
from config import TOKEN, MUST_JOIN_CHANNEL

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TITLE, DESC, QUESTION = range(3)
QUESTION_TIMER = 30

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id

    # Must join check
    try:
        member = await context.bot.get_chat_member(MUST_JOIN_CHANNEL, user.id)
        if member.status in ['left', 'kicked']:
            await update.message.reply_text(f"Please join our channel first: {MUST_JOIN_CHANNEL}")
            return
    except:
        await update.message.reply_text("Channel join check failed, contact admin.")
        return

    welcome = f"Hi {user.first_name}! 👋\nThis bot helps you create quizzes."

    keyboard = [
        [KeyboardButton("Create New Quiz")],
        [KeyboardButton("View My Quizzes")],
        [KeyboardButton("Start quiz in group")],
        [KeyboardButton("Language: English")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(welcome, reply_markup=reply_markup)

    inline = [
        [InlineKeyboardButton("Create New Quiz", callback_data="create")],
        [InlineKeyboardButton("View My Quizzes", callback_data="view")],
    ]
    await update.message.reply_text("Quick actions:", reply_markup=InlineKeyboardMarkup(inline))

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "create":
        await query.edit_message_text("Quiz title bhejo")
        return TITLE

    elif query.data == "view":
        quizzes = context.bot_data.get('quizzes', {})
        text = "Your quizzes:\n" + "\n".join([f"• {q['title']} (ID: {qid})" for qid, q in quizzes.items()]) if quizzes else "No quizzes yet"
        await query.edit_message_text(text)

# ... (baaki functions same as before: save_title, save_desc_or_skip, save_question, done, start_quiz, send_next, handle_answer)

def main():
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("create", start)],
        states={
            TITLE: [MessageHandler(filters.TEXT & \~filters.COMMAND, save_title)],
            DESC: [MessageHandler(filters.TEXT & \~filters.COMMAND, save_desc_or_skip)],
            QUESTION: [MessageHandler(filters.POLL, save_question), CommandHandler("done", done)],
        },
        fallbacks=[]
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("startquiz", start_quiz))
    application.add_handler(PollAnswerHandler(handle_answer))
    application.add_handler(CallbackQueryHandler(callback_handler))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
