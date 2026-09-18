import os
import sys
import logging
import time
from logging.handlers import RotatingFileHandler
from telegram import BotCommand
from telegram.ext import Application

import config
from database.connection import init_payments_db
from handlers.register import register_handlers

os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs"), exist_ok=True)

root_logger = logging.getLogger()
root_logger.setLevel(logging.WARNING)
fh = RotatingFileHandler("logs/payment-bot.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
fh.setLevel(logging.INFO)
fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
root_logger.addHandler(fh)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
ch.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
root_logger.addHandler(ch)
for name in ("telegram", "urllib3", "asyncio"):
    logging.getLogger(name).setLevel(logging.WARNING)

logger = logging.getLogger("tg-payment-pro")


async def post_init(application):
    application.bot_data["start_time"] = time.time()
    commands = [
        BotCommand("start", "Start"),
        BotCommand("pay", "Sale links: /pay SALE-A, SALE-B"),
        BotCommand("plink", "Custom: /plink 1200 upi Label"),
        BotCommand("salesbook", "Sale links ledger"),
        BotCommand("plinkbook", "Custom links ledger"),
        BotCommand("books", "Mobile webview links"),
        BotCommand("invoice", "Resend invoice"),
        BotCommand("cancel", "Cancel a link"),
        BotCommand("convert", "INR <> USD"),
        BotCommand("rate", "Current rate"),
        BotCommand("ping", "Health check"),
        BotCommand("help", "Help"),
    ]
    await application.bot.set_my_commands(commands)


def main():
    if not config.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing in .env")
    if not config.ADMIN_USER_ID:
        raise RuntimeError("ADMIN_USER_ID is missing or invalid in .env")
    init_payments_db()
    application = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .post_init(post_init)
        .read_timeout(30).write_timeout(30).connect_timeout(10)
        .build()
    )
    register_handlers(application)
    logger.info("Starting payment bot...")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
