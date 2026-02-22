from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove

# After NEGATIVE marking is set
async def set_negative(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    neg_map = {"Negative 0":0, "Negative 0.5":0.5, "Negative 1":1}
    context.user_data['negative'] = neg_map.get(text,0)

    # Save quiz
    title = context.user_data['title']
    desc = context.user_data.get('desc','')
    qs = context.user_data['questions']
    timer = context.user_data.get('timer', DEFAULT_TIMER)
    shuffle = context.user_data.get('shuffle', False)
    negative = context.user_data.get('negative',0)
    quiz_id = str(uuid.uuid4())[:8]

    context.bot_data.setdefault('quizzes',{})[quiz_id] = {
        'title': title, 'desc': desc, 'questions': qs, 'timer': timer, 'shuffle': shuffle, 'negative': negative
    }

    # Official style summary buttons
    keyboard = [
        [InlineKeyboardButton("▶️ Start Quiz", callback_data=f"start_{quiz_id}")],
        [InlineKeyboardButton("📊 Quiz Stats", callback_data=f"stats_{quiz_id}")],
        [InlineKeyboardButton("🗂 View My Quizzes", callback_data=f"my_{quiz_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    summary = f"Quiz saved!\n📁 {title}\n{desc or ''}\nQuestions: {len(qs)}\n⏱ {timer} sec\nShuffle: {'Yes' if shuffle else 'No'}\nNegative: {negative}"
    await update.message.reply_text(summary, reply_markup=reply_markup)
    context.user_data.clear()
    return ConversationHandler.END

# Update callback handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("start_"):
        quiz_id = data.split("_")[1]
        quiz = context.bot_data.get('quizzes', {}).get(quiz_id)
        if not quiz:
            await query.edit_message_text("Quiz not found")
            return
        chat_id = query.message.chat.id
        context.chat_data['active_quiz'] = {'quiz': quiz, 'index':0, 'scores':{}}
        await query.edit_message_text(f"Quiz started: {quiz['title']}")
        await send_next(context, chat_id)

    elif data.startswith("stats_"):
        quiz_id = data.split("_")[1]
        quiz = context.bot_data.get('quizzes', {}).get(quiz_id)
        if not quiz:
            await query.edit_message_text("Quiz not found")
            return
        # Show simple stats
        text = f"📊 Stats for {quiz['title']}\nTotal Questions: {len(quiz['questions'])}\nTime per question: {quiz.get('timer',DEFAULT_TIMER)}s\nShuffle: {'Yes' if quiz.get('shuffle') else 'No'}\nNegative: {quiz.get('negative',0)}"
        await query.edit_message_text(text)

    elif data.startswith("my_"):
        quiz_id = data.split("_")[1]
        quiz = context.bot_data.get('quizzes', {}).get(quiz_id)
        if not quiz:
            await query.edit_message_text("Quiz not found")
            return
        # View detailed quiz info
        text = f"🗂 Quiz: {quiz['title']}\nQuestions:\n"
        for i,q in enumerate(quiz['questions'],1):
            text += f"{i}. {q['question']} ({len(q['options'])} options)\n"
        await query.edit_message_text(text)
