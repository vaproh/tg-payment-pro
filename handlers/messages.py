from telegram import Update
from telegram.ext import ContextTypes

from core.permissions import require_seller, get_user_role
from core.format import code, esc
from core.state import state
from handlers.pay import _finalize_pay


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_seller(update):
        return
    user_id = update.effective_user.id
    text = update.message.text.strip()
    if state.get(user_id, "pay_stage") == "custom_amount":
        try:
            amount = float(text.replace(",", "").replace("Rs", "").replace("$", "").strip())
        except ValueError:
            await update.message.reply_text("Enter a valid number:")
            return
        if amount <= 0:
            await update.message.reply_text("Amount must be positive:")
            return
        state.pop(user_id, "pay_stage", None)
        from handlers.pay import _finalize_pay as fin
        await fin(update, context, custom=custom)
        return
