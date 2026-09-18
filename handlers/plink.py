"""Custom payment links. No sale verification - amount + label only.

Flow: /plink 100 [label...] -> method buttons -> review card
[Create] [Edit amount] -> link. One-shot: /plink 100 upi label.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from core.permissions import require_seller
from core.format import code, esc, fmt_money_inr, fmt_money_usd
from core.state import state
from handlers.linkgen import create_and_store


def _parse_args(args):
    """Returns (amount, method_or_None, label)."""
    if not args:
        return None, None, ""
    try:
        amount = float(args[0].replace(",", "").replace("Rs", "").replace("$", "").strip())
    except ValueError:
        return "bad", None, ""
    if amount <= 0:
        return "bad", None, ""
    rest = args[1:]
    method = None
    if rest and rest[0].lower() in ("upi", "crypto"):
        method = rest[0].lower()
        rest = rest[1:]
    return amount, method, " ".join(rest).strip()


def _amounts(amount, method, rate):
    if method == "upi":
        return float(amount), round(float(amount) / rate, 2) if rate else 0
    return round(float(amount) * rate, 0) if rate else 0, float(amount)


async def plink_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_seller(update):
        return
    user_id = update.effective_user.id
    amount, method, label = _parse_args(context.args or [])
    if amount is None:
        await update.message.reply_text(
            f"📝 Usage: {code('/plink 100')} or {code('/plink 100 upi VPS setup fee')}",
            parse_mode="HTML",
        )
        return
    if amount == "bad":
        await update.message.reply_text("⚠️ Invalid amount. Example: `/plink 500`", parse_mode="HTML")
        return
    if method:
        # One-shot: everything known, create immediately.
        await _create(update, context, user_id, method, amount, label or "Custom payment", edit=False)
        return
    state.set(user_id, "plink_amount", amount)
    state.set(user_id, "plink_label", label)
    state.set(user_id, "plink_stage", "method")

    from providers.fx import get_inr_per_usd
    rate, _, _ = get_inr_per_usd()
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("💳 UPI (INR)", callback_data="plink:method:upi"),
        InlineKeyboardButton("🪙 Crypto (USD)", callback_data="plink:method:crypto"),
    ]])
    await update.message.reply_text(
        f"💰 <b>New Custom Link</b>\n\n"
        f"💵 {fmt_money_inr(amount)} (~${round(amount / rate, 2) if rate else 0:,.2f})\n"
        f"📝 {esc(label) if label else '<i>no label yet</i>'}\n\n"
        f"👇 How should the buyer pay?",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def plink_method_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, method: str):
    query = update.callback_query
    user_id = update.effective_user.id
    if state.get(user_id, "plink_amount") is None:
        await query.edit_message_text("⚠️ Session expired. Run /plink again.")
        return
    state.set(user_id, "plink_method", method)
    state.set(user_id, "plink_stage", "review")
    await _show_review(update, context, user_id)


async def _show_review(update, context, user_id):
    from providers.fx import get_inr_per_usd
    from providers.cashfree import LINK_TTL_HOURS
    query = update.callback_query
    amount = state.get(user_id, "plink_amount")
    label = state.get(user_id, "plink_label", "")
    method = state.get(user_id, "plink_method", "upi")
    rate, _, _ = get_inr_per_usd()
    inr, usd = _amounts(amount, method, rate)
    method_line = "💳 <b>UPI</b> (INR)" if method == "upi" else "🪙 <b>Crypto</b> (USD)"
    expiry = f"⏰ Expires in {LINK_TTL_HOURS}h" if method == "upi" else "♾️ No expiry"
    text = (
        f"🔍 <b>Review Link</b>\n\n"
        f"{method_line}\n"
        f"💵 <b>{fmt_money_inr(inr)} / {fmt_money_usd(usd)}</b>\n"
        f"📝 {esc(label) if label else '<i>no label</i>'}\n"
        f"💱 Rs {rate:.2f}/$ · {expiry}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Create Link", callback_data="plink:review:create")],
        [InlineKeyboardButton("✏️ Edit Amount", callback_data="plink:review:edit")],
    ])
    if query:
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def plink_review_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str):
    query = update.callback_query
    user_id = update.effective_user.id
    if action == "edit":
        state.set(user_id, "plink_stage", "edit_amount")
        method = state.get(user_id, "plink_method", "upi")
        unit = "INR" if method == "upi" else "USD"
        await query.edit_message_text(
            f"✏️ Send new amount in <b>{unit}</b> (or /cancel to abort):",
            parse_mode="HTML",
        )
        return
    # create
    amount = state.get(user_id, "plink_amount")
    method = state.get(user_id, "plink_method", "upi")
    label = state.get(user_id, "plink_label", "")
    if amount is None:
        await query.edit_message_text("⚠️ Session expired. Run /plink again.")
        return
    await _create(update, context, user_id, method, amount, label or "Custom payment", edit=True)


async def plink_edit_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the edit-amount reply. Returns True if it consumed the message."""
    user_id = update.effective_user.id
    if state.get(user_id, "plink_stage") != "edit_amount":
        return False
    text = update.message.text.strip()
    try:
        amount = float(text.replace(",", "").replace("Rs", "").replace("$", "").strip())
    except ValueError:
        await update.message.reply_text("⚠️ Enter a valid number:")
        return True
    if amount <= 0:
        await update.message.reply_text("⚠️ Amount must be positive:")
        return True
    state.set(user_id, "plink_amount", amount)
    state.set(user_id, "plink_stage", "review")
    await _show_review(update, context, user_id)
    return True


async def _create(update, context, user_id, method, amount, label, edit):
    from providers.fx import get_inr_per_usd
    from providers.cashfree import LINK_TTL_HOURS
    rate, _, _ = get_inr_per_usd()
    currency = "INR" if method == "upi" else "USD"
    amount_inr, amount_usd = _amounts(amount, method, rate)
    try:
        link_id, url = create_and_store(
            "plink", method, amount, currency, [], label,
            user_id, amount_inr, amount_usd, rate,
        )
    except Exception as e:
        text = f"❌ Provider error: {esc(str(e))}\n\nTry again or /cancel."
        if edit and update.callback_query:
            await update.callback_query.edit_message_text(text, parse_mode="HTML")
        else:
            await update.message.reply_text(text, parse_mode="HTML")
        return
    for k in ("plink_amount", "plink_label", "plink_method", "plink_stage"):
        state.pop(user_id, k, None)
    method_line = "💳 <b>UPI</b>" if method == "upi" else "🪙 <b>Crypto</b>"
    expiry = f"⏰ Expires in {LINK_TTL_HOURS}h" if method == "upi" else "♾️ No expiry"
    text = (
        f"✅ <b>Link Ready</b>\n\n"
        f"{method_line} · 💵 <b>{fmt_money_inr(amount_inr)} / {fmt_money_usd(amount_usd)}</b>\n"
        f"📝 {esc(label)}\n"
        f"🔗 {code(link_id)} · {expiry}\n\n"
        f"📤 <b>Forward this to the buyer:</b>\n<code>{url}</code>"
    )
    if edit and update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="HTML")
    else:
        await update.message.reply_text(text, parse_mode="HTML")
