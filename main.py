import os
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)
from handlers import *
from states import *

TOKEN = os.getenv("BOT_TOKEN")

def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN missing in Heroku config")

    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("create", create)],
        states={
            WAITING_POLL: [
                MessageHandler(filters.POLL, receive_poll),
                CallbackQueryHandler(add_question, pattern="add_q"),
                CallbackQueryHandler(finish, pattern="finish"),
            ],
            WAITING_TIMER: [
                CallbackQueryHandler(timer_selected, pattern="timer_"),
            ],
            WAITING_SHUFFLE_Q: [
                CallbackQueryHandler(shuffle_q, pattern="shuffle_q_"),
            ],
            WAITING_SHUFFLE_OPT: [
                CallbackQueryHandler(shuffle_opt, pattern="shuffle_opt_"),
            ],
        },
        fallbacks=[]
    )

    app.add_handler(conv_handler)

    print("Bot running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
