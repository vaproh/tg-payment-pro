from telegram import Update
from telegram.ext import ContextTypes

from core.permissions import require_seller
from handlers.pay import pay_method_cb, pay_amount_cb
from handlers.plink import plink_method_cb, plink_review_cb


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_seller(update):
        return
    query = update.callback_query
    data = query.data or ""
    await query.answer()
    if data.startswith("pay:method:"):
        await pay_method_cb(update, context, data.split(":")[-1])
    elif data.startswith("pay:amt:"):
        await pay_amount_cb(update, context, data.split(":")[-1])
    elif data.startswith("plink:method:"):
        await plink_method_cb(update, context, data.split(":")[-1])
    elif data.startswith("plink:review:"):
        await plink_review_cb(update, context, data.split(":")[-1])
