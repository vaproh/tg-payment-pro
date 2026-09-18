from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from core.permissions import require_seller
from core.format import code, esc, fmt_money_inr, fmt_money_usd
from core.state import state
from handlers.linkgen import create_and_store


async def plink_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_seller(update):
        return
    user_id = update.effective_user.id
    if len(context.args) < 1:
        await update.message.reply_text(
            f"📝 Usage: {code('/plink 1200')} or {code('/plink 1200 upi VPS setup')}",
            parse_mode="HTML",
        )
        return
    try:
        amount = float(context.args[0].replace(",", "").replace("Rs", "").replace("$", "").strip())
    except ValueError:
        await update.message.reply_text("⚠️ Invalid amount.")
        return
    if amount <= 0:
        await update.message.reply_text("⚠️ Amount must be positive.")
        return

    label = " ".join(context.args[1:]) if len(context.args) > 1 else ""
    state.set(user_id, "plink_amount", amount)
    state.set(user_id, "plink_label", label)
    state.set(user_id, "plink_stage", "method")

    from providers.fx import get_inr_per_usd
    rate, _, _ = get_inr_per_usd()
    usd_est = round(amount / rate, 2) if rate else 0
    inr_est = round(amount * rate, 0) if rate else 0

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("💳 UPI (INR)", callback_data="plink:method:upi"),
        InlineKeyboardButton("🪙 Crypto (USD)", callback_data="plink:method:crypto"),
    ]])
    await update.message.reply_text(
        f"💰 <b>Custom Payment Link</b>\n\n"
        f"💵 Amount: <b>Rs {amount:,.0f}</b> (~${usd_est:,.2f})\n"
        f"📝 Purpose: {esc(label) if label else '<i>none</i>'}\n"
        f"💱 Rate: Rs {rate:.2f}/$\n\n"
        f"👇 Choose payment method:",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def plink_method_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, method: str):
    query = update.callback_query
    user_id = update.effective_user.id
    amount = state.get(user_id, "plink_amount")
    label = state.get(user_id, "plink_label", "")
    if amount is None:
        await query.edit_message_text("⚠️ Session expired. Run /plink again.")
        return
    state.set(user_id, "plink_method", method)
    state.set(user_id, "plink_stage", "amount")
    from providers.fx import get_inr_per_usd
    rate, _, _ = get_inr_per_usd()

    if method == "upi":
        usd_est = round(amount / rate, 2) if rate else 0
        prompt = (
            f"💳 <b>UPI Method Selected</b>\n\n"
            f"💵 Amount: <b>Rs {amount:,.0f}</b> (~${usd_est:,.2f})\n"
            f"📝 Purpose: {esc(label) if label else '<i>none</i>'}\n"
            f"💱 Rate: Rs {rate:.2f}/$\n\n"
            f"👇 Choose amount:"
        )
    else:
        inr_est = round(amount * rate, 0) if rate else 0
        prompt = (
            f"🪙 <b>Crypto Method Selected</b>\n\n"
            f"💵 Amount: <b>${amount:,.2f}</b> (~Rs {inr_est:,.0f})\n"
            f"📝 Purpose: {esc(label) if label else '<i>none</i>'}\n"
            f"💱 Rate: Rs {rate:.2f}/$\n\n"
            f"👇 Choose amount:"
        )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(f"✅ Use {amount:,.0f} INR" if method == "upi" else f"✅ Use {amount:,.2f} USD",
                             callback_data="plink:amt:full"),
        InlineKeyboardButton("✏️ Custom Amount", callback_data="plink:amt:custom"),
    ]])
    await query.edit_message_text(prompt, parse_mode="HTML", reply_markup=kb)


async def plink_amount_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, choice: str):
    query = update.callback_query
    user_id = update.effective_user.id
    if choice == "custom":
        state.set(user_id, "plink_stage", "custom_amount")
        method = state.get(user_id, "plink_method", "upi")
        unit = "INR" if method == "upi" else "USD"
        await query.edit_message_text(f"✏️ Send custom amount in <b>{unit}</b>:", parse_mode="HTML")
        return
    await _finalize_plink(update, context, custom=None)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from core.permissions import require_seller
    if not await require_seller(update):
        return
    user_id = update.effective_user.id
    text = update.message.text.strip()
    if state.get(user_id, "plink_stage") == "custom_amount":
        try:
            amount = float(text.replace(",", "").replace("Rs", "").replace("$", "").strip())
        except ValueError:
            await update.message.reply_text("⚠️ Enter a valid number:")
            return
        if amount <= 0:
            await update.message.reply_text("⚠️ Amount must be positive:")
            return
        state.pop(user_id, "plink_stage", None)
        state.set(user_id, "plink_amount", amount)
        # Re-enter method selection with new amount
        method = state.get(user_id, "plink_method", "upi")
        await _finalize_plink(update, context, custom=amount)


async def _finalize_plink(update, context, custom=None):
    query = update.callback_query if update.callback_query else None
    user_id = update.effective_user.id
    amount = state.get(user_id, "plink_amount")
    method = state.get(user_id, "plink_method", "upi")
    label = state.get(user_id, "plink_label", "Custom payment")

    if amount is None:
        msg = "⚠️ Session expired. Run /plink again."
        if query:
            await query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
        return

    if custom is not None:
        amount = custom

    currency = "INR" if method == "upi" else "USD"
    from providers.fx import get_inr_per_usd
    rate, _, _ = get_inr_per_usd()
    if method == "upi":
        amount_inr, amount_usd = float(amount), round(float(amount) / rate, 2) if rate else 0
    else:
        amount_usd, amount_inr = float(amount), round(float(amount) * rate, 0) if rate else 0

    try:
        link_id, url = create_and_store(
            "plink", method, amount, currency, [], label or "Custom payment",
            user_id, amount_inr, amount_usd, rate,
        )
    except Exception as e:
        text = f"❌ Provider error: {esc(str(e))}"
        if query:
            await query.edit_message_text(text, parse_mode="HTML")
        else:
            await update.message.reply_text(text, parse_mode="HTML")
        return

    for k in ("plink_amount", "plink_label", "plink_method", "plink_stage"):
        state.pop(user_id, k, None)

    from providers.cashfree import LINK_TTL_HOURS
    expiry_note = f"⏰ Expires in {LINK_TTL_HOURS}h" if method == "upi" else "♾️ No expiry"
    method_emoji = "💳" if method == "upi" else "🪙"
    text = (
        f"✅ <b>Payment Link Created</b>\n\n"
        f"{method_emoji} Method: <b>{method.upper()}</b>\n"
        f"💵 Amount: <b>{fmt_money_inr(amount_inr)} / {fmt_money_usd(amount_usd)}</b>\n"
        f"📝 Purpose: {esc(label) if label else '<i>none</i>'}\n"
        f"🔗 Link: <code>{link_id}</code>\n"
        f"{expiry_note}\n\n"
        f"👇 <b>Send this to buyer:</b>\n<code>{url}</code>"
    )
    if query:
        await query.edit_message_text(text, parse_mode="HTML")
    else:
        await update.message.reply_text(text, parse_mode="HTML")
