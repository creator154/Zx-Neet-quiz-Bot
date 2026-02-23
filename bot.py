import logging import os import uuid from telegram import Update, Poll, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton, KeyboardButtonPollType from telegram.ext import Application, CommandHandler, MessageHandler, PollAnswerHandler, ConversationHandler, CallbackQueryHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO) logger = logging.getLogger(name)

TITLE, DESC, QUESTION, TIMER, SHUFFLE, NEGATIVE = range(6) QUESTION_TIMER = 30

TOKEN = os.environ.get('TELEGRAM_TOKEN') if not TOKEN: raise ValueError('TELEGRAM_TOKEN not set!')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE): keyboard = [[KeyboardButton('Create New Quiz')]] await update.message.reply_text('Hi! Tap below to create your quiz:', reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: await update.message.reply_text('Send quiz title') return TITLE

async def save_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: context.user_data['title'] = update.message.text await update.message.reply_text('Send description or /skip') return DESC

async def save_desc_or_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: if update.message.text != '/skip': context.user_data['desc'] = update.message.text

keyboard = [[KeyboardButton('Add First Question', request_poll=KeyboardButtonPollType(type='quiz'))]]
await update.message.reply_text('Now add your first question using the button below:', reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
context.user_data['questions'] = []
return QUESTION

async def save_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: poll = update.message.poll if poll.type != Poll.QUIZ: await update.message.reply_text('Send only quiz mode poll!') return QUESTION

q = {
    'question': poll.question,
    'options': [opt.text for opt in poll.options],
    'correct': poll.correct_option_id,
    'explanation': poll.explanation or ''
}
context.user_data['questions'].append(q)

keyboard = [[KeyboardButton('Add Next Question', request_poll=KeyboardButtonPollType(type='quiz'))], [KeyboardButton('/done')]]
await update.message.reply_text(f'Saved ({len(context.user_data["questions"])})\nAdd next or /done', reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
return QUESTION

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: qs = context.user_data.get('questions', []) if not qs: await update.message.reply_text('No questions added') return ConversationHandler.END

keyboard = [[KeyboardButton('10 sec'), KeyboardButton('15 sec'), KeyboardButton('20 sec')],
            [KeyboardButton('30 sec'), KeyboardButton('45 sec'), KeyboardButton('60 sec')],
            [KeyboardButton('Skip timer')]]
await update.message.reply_text('Select time per question:', reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
return TIMER

async def set_timer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: text = update.message.text timer = 30 if text == 'Skip timer' else int(text.split()[0]) context.user_data['timer'] = timer

keyboard = [[KeyboardButton('Shuffle All')], [KeyboardButton('No Shuffle')], [KeyboardButton('Only Questions'), KeyboardButton('Only Answers')]]
await update.message.reply_text('Shuffle questions and answer options?', reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
return SHUFFLE

async def set_shuffle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: text = update.message.text shuffle = text != 'No Shuffle' context.user_data['shuffle'] = shuffle

keyboard = [[KeyboardButton('No Negative')], [KeyboardButton('0.25'), KeyboardButton('0.5'), KeyboardButton('1')]]
await update.message.reply_text('Select negative marking:', reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
return NEGATIVE

async def set_negative(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: text = update.message.text negative = 0 if text == 'No Negative' else float(text) context.user_data['negative'] = negative

title = context.user_data['title']
desc = context.user_data.get('desc','')
qs = context.user_data['questions']
timer = context.user_data.get('timer',30)
shuffle = context.user_data.get('shuffle',False)

quiz_id = str(uuid.uuid4())[:8]
context.bot_data.setdefault('quizzes',{})[quiz_id] = {
    'title': title,
    'desc': desc,
    'questions': qs,
    'timer': timer,
    'shuffle': shuffle,
    'negative': negative
}

inline_keyboard = [
    [InlineKeyboardButton('▶️ Start Quiz in Group', switch_inline_query_current_chat=f'startgroup_{quiz_id}')],
    [InlineKeyboardButton('Quiz Stats', callback_data=f'stats_{quiz_id}')],
    [InlineKeyboardButton('View My Quizzes', callback_data='view_my_quizzes')]
]
reply_markup = InlineKeyboardMarkup(inline_keyboard)

summary = f'Quiz saved successfully!\n\n📁 {title}\n{desc or ""}\nTotal questions: {len(qs)}\n⏱ Time per question: {timer} sec\nShuffle: {shuffle}\nNegative marking: {negative}'
await update.message.reply_text(summary, reply_markup=reply_markup)
context.user_data.clear()
return ConversationHandler.END

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE): query = update.callback_query await query.answer() data = query.data

if data.startswith('stats_'):
    quiz_id = data.split('_')[1]
    quiz = context.bot_data.get('quizzes',{}).get(quiz_id)
    if quiz:
        await query.edit_message_text(f'Stats for quiz {quiz["title"]}: Total Questions: {len(quiz["questions"])}')

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE): if update.effective_chat.type not in ['group','supergroup']: await update.message.reply_text('Use in a group!') return if not context.args: await update.message.reply_text('/startquiz <quiz_id>') return quiz_id = context.args[0] quiz = context.bot_data.get('quizzes',{}).get(quiz_id) if not quiz: await update.message.reply_text('Quiz not found') return context.chat_data['active_quiz'] = {'quiz': quiz,'index':0,'scores':{}} await update.message.reply_text(f'Quiz started: {quiz["title"]}') await send_next(context, update.effective_chat.id)

async def send_next(context: ContextTypes.DEFAULT_TYPE, chat_id:int): active = context.chat_data.get('active_quiz') if not active: return index = active['index'] quiz = active['quiz'] if index>=len(quiz['questions']): scores = active['scores'] text='Leaderboard:\n'+ '\n'.join([f'{uid}: {score}' for uid,score in sorted(scores.items(),key=lambda x:x[1],reverse=True)]) await context.bot.send_message(chat_id,text) context.chat_data.pop('active_quiz',None) return q=quiz['questions'][index] await context.bot.send_poll(chat_id,q['question'],q['options'],Poll.QUIZ,q['correct'],q['explanation'],is_anonymous=False,open_period=quiz.get('timer',QUESTION_TIMER)) active['index']+=1

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE): poll_answer = update.poll_answer user_id = poll_answer.user.id active = context.chat_data.get('active_quiz') if not active: return index = active['index']-1 q=active['quiz']['questions'][index] selected = poll_answer.option_ids[0] if poll_answer.option_ids else None if selected==q['correct']: active['scores'][user_id] = active['scores'].get(user_id,0)+1

def main(): app=Application.builder().token(TOKEN).build()

conv=ConversationHandler(
    entry_points=[CommandHandler('create',create)],
    states={
        TITLE:[MessageHandler(filters.TEXT & ~filters.COMMAND,save_title)],
        DESC:[MessageHandler(filters.TEXT & ~filters.COMMAND,save_desc_or_skip)],
        QUESTION:[MessageHandler(filters.POLL,save_question),CommandHandler('done',done)],
        TIMER:[MessageHandler(filters.TEXT,set_timer)],
        SHUFFLE:[MessageHandler(filters.TEXT,set_shuffle)],
        NEGATIVE:[MessageHandler(filters.TEXT,set_negative)]
    },
    fallbacks=[]
)

app.add_handler(conv)
app.add_handler(CommandHandler('start',start))
app.add_handler(CommandHandler('startquiz',start_quiz))
app.add_handler(PollAnswerHandler(handle_answer))
app.add_handler(CallbackQueryHandler(button_handler))

app.run_polling()

if name=='main': main()
