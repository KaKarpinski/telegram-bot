import os

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
)

from .message_handlers import receive_categories, handle_category_action, handle_message, start, change_categories
from logger import logger

WAITING_CATEGORIES = 1
WAITING_CATEGORY_ACTION = 2

TOKEN = os.getenv("TELEGRAM_TOKEN")

def initialize_bot():
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("kategorie", change_categories),
        ],
        states={
            WAITING_CATEGORIES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_categories)
            ],
            WAITING_CATEGORY_ACTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_category_action)
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot uruchomiony ✅")
    app.run_polling()