from telegram import Update
from telegram.ext import ContextTypes

from core.permissions import require_seller
from core.state import state
from core.format import code
from handlers.pay import _finalize_pay, validate_codes, method_message, pay_got_phone
from handlers.plink import plink_edit_text, plink_got_amount
from handlers.utils_cmds import convert_text


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_seller(update):
        return
    user_id = update.effective_user.id
    if await pay_got_phone(update, context):
        return
    stage = state.get(user_id, "pay_stage")
    if stage == "await_codes":
        from handlers.pay import parse_codes
        sales, problems = validate_codes(user_id, parse_codes(update.message.text.strip()))
        if problems:
            await update.message.reply_text("\n".join(problems), parse_mode="HTML")
            if not sales:
                return
        state.pop(user_id, "pay_stage", None)
        text, kb = method_message(user_id, sales)
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)
        return
    if stage == "custom_amount":
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
        await _finalize_pay(update, context, custom=amount)
        return
    if state.get(user_id, "plink_stage") == "await_amount":
        if await plink_got_amount(update, context):
            return
    if await plink_edit_text(update, context):
        return
    if state.get(user_id, "misc_stage") == "await_convert":
        parts = update.message.text.strip().split()
        if len(parts) < 2:
            await update.message.reply_text(
                f"📝 Send like {code('1200 INR')} or {code('15 USD')}:", parse_mode="HTML",
            )
            return
        state.pop(user_id, "misc_stage", None)
        await update.message.reply_text(convert_text(parts[0], parts[1]))
        return
