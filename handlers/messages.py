from telegram import Update
from telegram.ext import ContextTypes

from core.permissions import require_seller
from core.state import state
from handlers.pay import _finalize_pay
from handlers.plink import handle_text as plink_handle_text


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_seller(update):
        return
    user_id = update.effective_user.id
    # Check if plink custom amount flow is active
    if state.get(user_id, "plink_stage") == "custom_amount":
        await plink_handle_text(update, context)
        return
    # Check if pay custom amount flow is active
    if state.get(user_id, "pay_stage") == "custom_amount":
        text = update.message.text.strip()
        try:
            amount = float(text.replace(",", "").replace("Rs", "").replace("$", "").strip())
        except ValueError:
            await update.message.reply_text("⚠️ Enter a valid number:")
            return
        if amount <= 0:
            await update.message.reply_text("⚠️ Amount must be positive:")
            return
        state.pop(user_id, "pay_stage", None)
        update.callback_query = None
        await _finalize_pay(update, context, custom=amount)
        return
