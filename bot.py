# bot.py - Telegram Quiz Bot (official-like) - Heroku ready
import logging
import os
import uuid
from telegram import Update, Poll, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, PollAnswerHandler,
    ConversationHandler, CallbackQueryHandler, filters, ContextTypes
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# States
TITLE, DESC, QUESTION = range(3)
QUESTION_TIMER = 30

# Token
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set!")

# --- START / MAIN MENU ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("Create New Quiz")],
        [KeyboardButton("View My Quizzes")],
        [KeyboardButton("Start Quiz in Group")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Hi! Use the menu below to create or start quizzes:",
        reply_markup=reply_markup
    )

# --- CREATE QUIZ FLOW ---
async def create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Send quiz title:")
    return TITLE

async def save_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['title'] = update.message.text
    await update.message.reply_text("Send quiz description or /skip")
    return DESC

async def save_desc_or_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text != '/skip':
        context.user_data['desc'] = update.message.text
    context.user_data['questions'] = []

    # Inline button for first poll
    inline_kb = [
        [InlineKeyboardButton("📝 Add First Question", callback_data="add_poll")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_kb)
    await update.message.reply_text(
        "Now add your first question using the button below:",
        reply_markup=reply_markup
    )
    return QUESTION

# --- SAVE POLL QUESTION ---
async def save_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    poll = update.message.poll
    if poll.type != Poll.QUIZ:
        await update.message.reply_text("Send a quiz-mode poll only!")
        return QUESTION

    q = {
        'question': poll.question,
        'options': [opt.text for opt in poll.options],
        'correct': poll.correct_option_id,
        'explanation': poll.explanation or ""
    }
    context.user_data['questions'].append(q)

    # Inline buttons for next
    inline_kb = [
        [InlineKeyboardButton("➕ Add Another Question", callback_data="add_poll")],
        [InlineKeyboardButton("✅ Done", callback_data="done_quiz")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_kb)
    await update.message.reply_text(
        f"Saved ({len(context.user_data['questions'])}) question(s).\nUse buttons below to add more or finish:",
        reply_markup=reply_markup
    )
    return QUESTION

# --- FINISH QUIZ ---
async def done_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    qs = context.user_data.get('questions', [])
    if not qs:
        await query.edit_message_text("No questions added. Quiz cancelled.")
        return ConversationHandler.END

    title = context.user_data.get('title', 'Untitled')
    desc = context.user_data.get('desc', '')

    quiz_id = str(uuid.uuid4())[:8]
    context.bot_data.setdefault('quizzes', {})[quiz_id] = {
        'title': title,
        'desc': desc,
        'questions': qs
    }

    summary = f"Quiz created successfully!\n\n" \
              f"📁 {title}\n{desc or ''}\n" \
              f"Total questions: {len(qs)}\nQuiz ID: {quiz_id}"

    # Buttons like official bot
    inline_kb = [
        [InlineKeyboardButton("▶️ Start Quiz", callback_data=f"start_{quiz_id}")],
        [InlineKeyboardButton("Start in Group", switch_inline_query_current_chat=f"startquiz {quiz_id}")],
        [InlineKeyboardButton("Share Quiz", switch_inline_query_current_chat=f"share {quiz_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_kb)
    await query.edit_message_text(summary, reply_markup=reply_markup)

    context.user_data.clear()
    return ConversationHandler.END

# --- INLINE BUTTON HANDLER ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "add_poll":
        await query.edit_message_text("Send your next quiz poll now:")
    elif data == "done_quiz":
        await done_quiz(update, context)
    elif data.startswith("start_"):
        quiz_id = data.split("_")[1]
        await query.edit_message_text(f"Quiz started: {quiz_id}\nUse /startquiz <id> in your group to play.")

# --- POLL ANSWER HANDLER ---
async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll_answer = update.poll_answer
    user_id = poll_answer.user.id
    active = context.chat_data.get('active_quiz')
    if not active:
        return
    index = active['index'] - 1
    q = active['quiz']['questions'][index]
    selected = poll_answer.option_ids[0] if poll_answer.option_ids else None
    if selected == q['correct']:
        active['scores'][user_id] = active['scores'].get(user_id, 0) + 1

# --- START QUIZ IN GROUP ---
async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("Use this command in a group only!")
        return

    if not context.args:
        await update.message.reply_text("/startquiz <quiz_id>")
        return

    quiz_id = context.args[0]
    quiz = context.bot_data.get('quizzes', {}).get(quiz_id)
    if not quiz:
        await update.message.reply_text("Quiz not found!")
        return

    context.chat_data['active_quiz'] = {'quiz': quiz, 'index': 0, 'scores': {}}
    await update.message.reply_text(f"Quiz started: {quiz['title']}")

# --- MAIN ---
def main():
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("create", create)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_title)],
            DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_desc_or_skip)],
            QUESTION: [MessageHandler(filters.POLL, save_question)],
        },
        fallbacks=[]
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("startquiz", start_quiz))
    app.add_handler(PollAnswerHandler(handle_answer))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.run_polling()

if __name__ == '__main__':
    main()
