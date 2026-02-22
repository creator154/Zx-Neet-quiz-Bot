conv_handler = ConversationHandler(
    entry_points=[CommandHandler("create", create)],
    states={
        WAITING_POLL: [
            MessageHandler(filters.POLL, receive_poll),
            CallbackQueryHandler(add_question, pattern="add_q"),
            CallbackQueryHandler(finish, pattern="finish"),
        ],
        WAITING_TIMER: [
            CallbackQueryHandler(timer_selected, pattern="timer_")
        ],
        WAITING_SHUFFLE_Q: [
            CallbackQueryHandler(shuffle_q, pattern="shuffle_q_")
        ],
        WAITING_SHUFFLE_OPT: [
            CallbackQueryHandler(shuffle_opt, pattern="shuffle_opt_")
        ],
    },
    fallbacks=[],
)

application.add_handler(conv_handler)
