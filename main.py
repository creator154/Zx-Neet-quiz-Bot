from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters
)

from config import BOT_TOKEN
from handlers import (
    start, create,
    receive_title,
    receive_description,
    skip_description,
    receive_poll,
    finish
)

from states import WAITING_TITLE, WAITING_DESCRIPTION, WAITING_POLL


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("create", create)],
        states={
            WAITING_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_title)
            ],
            WAITING_DESCRIPTION: [
                CommandHandler("skip", skip_description),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_description)
            ],
            WAITING_POLL: [
                MessageHandler(filters.POLL, receive_poll)
            ],
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(finish, pattern="finish"))

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
