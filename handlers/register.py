import logging
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters,
)

from handlers.pay import pay_cmd, cancel_cmd
from handlers.plink import plink_cmd
from handlers.books import salesbook_cmd, plinkbook_cmd, invoice_cmd, books_cmd
from handlers.utils_cmds import start_cmd, ping_cmd, convert_cmd, rate_cmd, help_cmd
from handlers.callbacks import handle_callback
from handlers.messages import handle_text

logger = logging.getLogger(__name__)


def register_handlers(application: Application):
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("ping", ping_cmd))
    application.add_handler(CommandHandler("pay", pay_cmd))
    application.add_handler(CommandHandler("plink", plink_cmd))
    application.add_handler(CommandHandler("cancel", cancel_cmd))
    application.add_handler(CommandHandler("salesbook", salesbook_cmd))
    application.add_handler(CommandHandler("plinkbook", plinkbook_cmd))
    application.add_handler(CommandHandler("invoice", invoice_cmd))
    application.add_handler(CommandHandler("books", books_cmd))
    application.add_handler(CommandHandler("convert", convert_cmd))
    application.add_handler(CommandHandler("rate", rate_cmd))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("Payment handlers registered.")
