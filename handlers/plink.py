from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from core.permissions import require_seller
from core.format import code, fmt_money_inr, fmt_money_usd
from core.state import state
from providers.fx import get_inr_per_usd
from handlers.linkgen import create_and_store


async def plink_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_seller(update):
        return
    user_id = update.effective_user.id
    if len(context.args) < 2:
        await update.message.reply_text(
            f"Usage: {code('/plink 1200 upi Label here')} or {code('/plink 25 crypto Label')}",
            parse_mode="HTML",
        )
        return
    try:
        amount = float(context.args[0].replace(",", ""))
    except ValueError:
        await update.message.reply_text("Invalid amount.")
        return
    maybe_method = context.args[1].lower()
    if maybe_method in ("upi", "crypto"):
        method = maybe_method
        label = " ".join(context.args[2:]) or "Custom payment"
    else:
        # No method given: ask via buttons, stash pending
        label = " ".join(context.args[1:])
        state.set(user_id, "plink_amount", amount)
        state.set(user_id, "plink_label", label)
        state.set(user_id, "plink_stage", "method")
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("UPI (INR)", callback_data="plink:method:upi"),
            InlineKeyboardButton("Crypto (USD)", callback_data="plink:method:crypto"),
        ]])
        rate, _, _ = get_inr_per_usd()
        await update.message.reply_text(
            f"Amount: {amount} (~Rs {amount:.0f} / ${amount:.2f}, rate Rs {rate:.2f}/$)\n"
            f"Label: {label}\n\nChoose method:",
            reply_markup=kb,
        )
        return
    await _make_plink(update, user_id, method, amount, " ".join(context.args[2:]) or "Custom payment")


async def plink_method_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, method: str):
    query = update.callback_query
    user_id = update.effective_user.id
    amount = state.get(user_id, "plink_amount")
    label = state.get(user_id, "plink_label", "Custom payment")
    if amount is None:
        await query.edit_message_text("Session expired. Run /plink again.")
        return
    for k in ("plink_amount", "plink_label", "plink_stage"):
        state.pop(user_id, k, None)
    # Reuse query message for output
    await _make_plink(update, user_id, method, amount, label, edit=True)


async def _make_plink(update, user_id, method, amount, label, edit=False):
    from providers.fx import get_inr_per_usd
    from providers.cashfree import LINK_TTL_HOURS
    rate, _, _ = get_inr_per_usd()
    currency = "INR" if method == "upi" else "USD"
    if method == "upi":
        amount_inr, amount_usd = float(amount), round(float(amount) / rate, 2) if rate else 0
    else:
        amount_usd, amount_inr = float(amount), round(float(amount) * rate, 0) if rate else 0
    try:
        link_id, url = create_and_store(
            "plink", method, amount, currency, [], label,
            user_id, amount_inr, amount_usd, rate,
        )
    except Exception as e:
        text = f"Provider error: {e}"
        if edit:
            await update.callback_query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return
    expiry_note = f"Expires in {LINK_TTL_HOURS}h" if method == "upi" else "No expiry"
    text = (
        f"Send this link to buyer:\n<code>{url}</code>\n\n"
        f"Link: <code>{link_id}</code>\nPurpose: {label}\n"
        f"Amount: <b>{amount} {currency}</b> ({fmt_money_inr(amount_inr)} / {fmt_money_usd(amount_usd)})\n"
        f"{expiry_note}"
    )
    if edit:
        await update.callback_query.edit_message_text(text, parse_mode="HTML")
    else:
        await update.message.reply_text(text, parse_mode="HTML")
