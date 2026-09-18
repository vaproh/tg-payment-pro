from telegram import Update
from telegram.ext import ContextTypes

from core.permissions import require_seller
from handlers.pay import pay_method_cb, pay_amount_cb, pay_back_cb, pay_cancel_cb, cancel_confirm_cb
from handlers.plink import plink_method_cb, plink_review_cb, plink_back_cb, plink_cancel_cb
from handlers.books import invoice_cb, books_refresh_cb
from handlers.menu import menu_cb


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
    elif data == "pay:back:method" or data == "pay:back:amount":
        await pay_back_cb(update, context)
    elif data == "pay:cancel":
        await pay_cancel_cb(update, context)
    elif data.startswith("cancel:yes:"):
        await cancel_confirm_cb(update, context, data.split(":", 2)[-1])
    elif data == "cancel:no":
        await cancel_confirm_cb(update, context, "")
    elif data.startswith("plink:method:"):
        await plink_method_cb(update, context, data.split(":")[-1])
    elif data.startswith("plink:review:"):
        await plink_review_cb(update, context, data.split(":")[-1])
    elif data == "plink:back:method" or data == "plink:back:review":
        await plink_back_cb(update, context)
    elif data == "plink:cancel":
        await plink_cancel_cb(update, context)
    elif data.startswith("invoice:"):
        await invoice_cb(update, context, data.split(":", 1)[-1])
    elif data.startswith("books:refresh:"):
        await books_refresh_cb(update, context, data.split(":")[-1])
    elif data.startswith("menu:"):
        await menu_cb(update, context, data.split(":", 1)[-1])
