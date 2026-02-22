import os

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from handlers import (
    create,
    receive_poll,
    add_question,
    finish,
    timer_selected,
    shuffle_q,
    shuffle_opt,
)

from states import (
    WAITING_POLL,
    WAITING_TIMER,
    WAITING_SHUFFLE_Q,
    WAITING_SHUFFLE_OPT,
)


# =============================
# BOT TOKEN
# =============================
TOKEN = os.getenv("BOT_TOKEN")


# =============================
# MAIN FUNCTION
# =============================
def main():

    application = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("create", create),
        ],
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
        fallbacks=[],
    )

    application.add_handler(conv_handler)

    print("Bot is running...")
    application.run_polling()


# =============================
# START
# =============================
if __name__ == "__main__":
    main()
