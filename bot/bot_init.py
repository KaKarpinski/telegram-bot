import os

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)

from .message_handlers import receive_categories, handle_category_action, handle_message, start, change_categories, get_requested_sum_handler, handle_sum_action, cancel, handle_subscriptions, handle_subscription_action
from logger import logger
from consts import WAITING_CATEGORIES, WAITING_CATEGORY_ACTION, WAITING_SUM_ACTION,  WAITING_SUB_ACTION

TOKEN = os.getenv("TELEGRAM_TOKEN")

CANCEL_FILTER = filters.Regex("(?i)^anuluj$")

def initialize_bot():
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("kategorie", change_categories),
            CommandHandler("suma", get_requested_sum_handler),
            CommandHandler("subskrypcje", handle_subscriptions)
        ],
        states={
            WAITING_CATEGORIES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~CANCEL_FILTER, receive_categories)
            ],
            WAITING_CATEGORY_ACTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~CANCEL_FILTER, handle_category_action)
            ],
            WAITING_SUM_ACTION: [
                CallbackQueryHandler(handle_sum_action)
            ],
            WAITING_SUB_ACTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~CANCEL_FILTER, handle_subscription_action)
            ]
        },
        fallbacks=[
            CommandHandler("anuluj", cancel),                              
            MessageHandler(CANCEL_FILTER, cancel),
        ],
    )

    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot uruchomiony ✅")
    app.run_polling()