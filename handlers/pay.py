from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import config
from core.permissions import require_seller, get_user_role
from core.format import code, esc, fmt_money_inr, fmt_money_usd
from core.state import state
from database.connection import get_sale_by_code, get_seller_id_by_user_id
from providers.fx import get_inr_per_usd, inr_to_usd
from handlers.linkgen import create_and_store, normalize_phone, DEFAULT_PHONE


def parse_codes(raw):
    return [c.strip().upper() for c in raw.replace(";", ",").split(",") if c.strip()]


def validate_codes(user_id, codes):
    """Returns (sales, problems). Sales are pending + owned (admin bypass)."""
    role = get_user_role(user_id)
    my_seller_id = get_seller_id_by_user_id(user_id)
    sales, problems = [], []
    for sc in codes:
        s = get_sale_by_code(sc)
        if not s:
            problems.append(f"❌ Not found: {code(sc)}")
            continue
        if s["payment_status"] == "paid":
            problems.append(f"✅ Already paid: {code(sc)}")
            continue
        if role != "admin" and s["seller_id"] != my_seller_id:
            problems.append(f"🔒 Not yours: {code(sc)}")
            continue
        sales.append(s)
    return sales, problems


def method_message(user_id, sales):
    """Store state + build (text, keyboard) for the method step."""
    total_inr = round(sum(float(s["price"]) for s in sales), 0)
    total_usd, rate, _ = inr_to_usd(total_inr)
    state.set(user_id, "pay_codes", [s["sale_code"] for s in sales])
    state.set(user_id, "pay_total_inr", total_inr)
    state.set(user_id, "pay_total_usd", total_usd)
    state.set(user_id, "pay_rate", rate)
    state.set(user_id, "pay_stage", "method")
    lines = [f"  • {code(s['sale_code'])} | {esc(s.get('username',''))} | Rs {float(s['price']):,.0f}" for s in sales]
    text = (
        f"💰 <b>Sale Payment Link</b>\n\n"
        f"📦 <b>Sales ({len(sales)}):</b>\n" + "\n".join(lines) + "\n\n"
        f"💵 Total: <b>{fmt_money_inr(total_inr)} / {fmt_money_usd(total_usd)}</b>\n"
        f"💱 Rate: Rs {rate:.2f}/$\n\n"
        f"👇 Choose payment method:"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💳 UPI (INR)", callback_data="pay:method:upi"),
            InlineKeyboardButton("🪙 Crypto (USD)", callback_data="pay:method:crypto"),
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="pay:cancel")],
    ])
    return text, kb


async def pay_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_seller(update):
        return
    user_id = update.effective_user.id
    raw = " ".join(context.args) if context.args else ""
    if not raw:
        await update.message.reply_text(
            f"📝 Send sale codes: {code('/pay SALE-A, SALE-B')}",
            parse_mode="HTML",
        )
        return
    sales, problems = validate_codes(user_id, parse_codes(raw))
    if problems:
        await update.message.reply_text("\n".join(problems), parse_mode="HTML")
        if not sales:
            return
    text, kb = method_message(user_id, sales)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def pay_method_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, method: str):
    query = update.callback_query
    user_id = update.effective_user.id
    codes = state.get(user_id, "pay_codes")
    if not codes:
        await query.edit_message_text("⚠️ Session expired. Run /pay again.")
        return
    state.set(user_id, "pay_method", method)
    state.set(user_id, "pay_stage", "amount")
    if state.get(user_id, "pay_phone") is None:
        state.set(user_id, "pay_phone", DEFAULT_PHONE)
    text, kb = amount_message(user_id)
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)


def amount_message(user_id):
    """Build (text, keyboard) for the amount step. Re-renders after phone set."""
    total_inr = state.get(user_id, "pay_total_inr", 0)
    total_usd = state.get(user_id, "pay_total_usd", 0)
    rate = state.get(user_id, "pay_rate", 0)
    method = state.get(user_id, "pay_method", "upi")
    phone = state.get(user_id, "pay_phone", DEFAULT_PHONE)
    phone_line = f"📱 Buyer: <code>{phone}</code>" if phone != DEFAULT_PHONE else "📱 Buyer: <i>not set</i>"
    if method == "upi":
        prompt = (
            f"💳 <b>UPI Method</b> - amount in <b>INR</b>\n\n"
            f"💵 Total: <b>{fmt_money_inr(total_inr)}</b> (~{fmt_money_usd(total_usd)})\n"
            f"{phone_line}\n"
            f"💱 Rate: Rs {rate:.2f}/$\n\n👇 Choose amount:"
        )
    else:
        prompt = (
            f"🪙 <b>Crypto Method</b> - amount in <b>USD</b>\n\n"
            f"💵 Total: <b>{fmt_money_usd(total_usd)}</b> (~{fmt_money_inr(total_inr)})\n"
            f"💱 Rate: Rs {rate:.2f}/$\n\n👇 Choose amount:"
        )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"✅ Use {fmt_money_inr(total_inr)}" if method == "upi" else f"✅ Use {fmt_money_usd(total_usd)}",
            callback_data="pay:amt:full",
        )],
        [
            InlineKeyboardButton("✏️ Custom", callback_data="pay:amt:custom"),
            InlineKeyboardButton("📱 Phone", callback_data="pay:phone"),
        ],
        [InlineKeyboardButton("⬅️ Method", callback_data="pay:back:method")],
    ])
    return prompt, kb


async def pay_phone_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    state.set(user_id, "pay_stage", "phone")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="pay:back:amount")]])
    await query.edit_message_text(
        "📱 Send buyer's 10-digit mobile number\n(or /skip to leave unset):",
        parse_mode="HTML", reply_markup=kb,
    )


async def pay_got_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Text entry for phone step. Returns True if consumed."""
    user_id = update.effective_user.id
    if state.get(user_id, "pay_stage") != "phone":
        return False
    text = update.message.text.strip()
    if text.lower() == "/skip":
        state.set(user_id, "pay_phone", DEFAULT_PHONE)
    else:
        phone = normalize_phone(text)
        if not phone:
            await update.message.reply_text("⚠️ Invalid number. Send 10 digits (e.g. <code>9876543210</code>) or /skip:", parse_mode="HTML")
            return True
        state.set(user_id, "pay_phone", phone)
    state.set(user_id, "pay_stage", "amount")
    text, kb = amount_message(user_id)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)
    return True


async def pay_back_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Back to method step from amount step."""
    query = update.callback_query
    user_id = update.effective_user.id
    codes = state.get(user_id, "pay_codes", [])
    sales = [s for s in (get_sale_by_code(c) for c in codes) if s]
    if not sales:
        await query.edit_message_text("⚠️ Session expired. Run /pay again.")
        return
    # Rebuild method step without resetting (keeps same totals)
    total_inr = state.get(user_id, "pay_total_inr", 0)
    total_usd = state.get(user_id, "pay_total_usd", 0)
    rate = state.get(user_id, "pay_rate", 0)
    state.set(user_id, "pay_stage", "method")
    lines = [f"  • {code(s['sale_code'])} | Rs {float(s['price']):,.0f}" for s in sales]
    text = (
        f"💰 <b>Sale Payment Link</b>\n\n"
        f"📦 <b>Sales ({len(sales)}):</b>\n" + "\n".join(lines) + "\n\n"
        f"💵 Total: <b>{fmt_money_inr(total_inr)} / {fmt_money_usd(total_usd)}</b>\n"
        f"💱 Rate: Rs {rate:.2f}/$\n\n👇 Choose payment method:"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💳 UPI (INR)", callback_data="pay:method:upi"),
            InlineKeyboardButton("🪙 Crypto (USD)", callback_data="pay:method:crypto"),
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="pay:cancel")],
    ])
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)


async def pay_cancel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    for k in ("pay_codes", "pay_total_inr", "pay_total_usd", "pay_rate", "pay_method", "pay_stage", "pay_phone"):
        state.pop(user_id, k, None)
    await update.callback_query.edit_message_text("❌ Cancelled. Run /pay to start over.")


async def pay_amount_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, choice: str):
    query = update.callback_query
    user_id = update.effective_user.id
    if choice == "custom":
        state.set(user_id, "pay_stage", "custom_amount")
        method = state.get(user_id, "pay_method", "upi")
        unit = "INR" if method == "upi" else "USD"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="pay:back:amount")]])
        await query.edit_message_text(
            f"✏️ Send custom amount in <b>{unit}</b>:", parse_mode="HTML", reply_markup=kb,
        )
        return
    await _finalize_pay(update, context, custom=None)


async def _finalize_pay(update: Update, context, custom):
    query = update.callback_query if update.callback_query else None
    user_id = update.effective_user.id
    codes = state.get(user_id, "pay_codes", [])
    method = state.get(user_id, "pay_method", "upi")
    total_inr = state.get(user_id, "pay_total_inr", 0)
    total_usd = state.get(user_id, "pay_total_usd", 0)
    rate = state.get(user_id, "pay_rate", 0)
    phone = state.get(user_id, "pay_phone", DEFAULT_PHONE)
    if not codes:
        msg = "⚠️ Session expired. Run /pay again."
        if query:
            await query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
        return

    amount = total_inr if (custom is None and method == "upi") else \
        total_usd if custom is None else custom
    currency = "INR" if method == "upi" else "USD"
    if method == "upi":
        amount_inr, amount_usd = float(amount), round(float(amount) / rate, 2) if rate else 0
    else:
        amount_usd, amount_inr = float(amount), round(float(amount) * rate, 0) if rate else 0

    try:
        link_id, url = create_and_store(
            "sale", method, amount, currency, codes, None,
            user_id, amount_inr, amount_usd, rate, customer_phone=phone,
        )
    except Exception as e:
        msg = f"❌ Provider error: {esc(str(e))}\n\nTry again or /cancel."
        if query:
            await query.edit_message_text(msg, parse_mode="HTML")
        else:
            await update.message.reply_text(msg, parse_mode="HTML")
        return
    for k in ("pay_codes", "pay_total_inr", "pay_total_usd", "pay_rate", "pay_method", "pay_stage", "pay_phone"):
        state.pop(user_id, k, None)

    method_line = "💳 <b>UPI</b>" if method == "upi" else "🪙 <b>Crypto</b>"
    if method == "upi":
        from providers.cashfree import LINK_TTL_HOURS
        expiry_note = f"⏰ Expires in {LINK_TTL_HOURS}h"
    else:
        expiry_note = "♾️ No expiry"
    text = (
        f"✅ <b>Link Ready</b>\n\n"
        f"{method_line} · 💵 <b>{fmt_money_inr(amount_inr)} / {fmt_money_usd(amount_usd)}</b>\n"
        f"📦 {', '.join(code(c) for c in codes)}\n"
        + (f"📱 Buyer: {code(phone)}\n" if phone != DEFAULT_PHONE else "")
        + f"🔗 {code(link_id)} · {expiry_note}\n\n"
        f"📤 <b>Forward this to the buyer:</b>\n<code>{url}</code>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Open Payment Page", url=url)],
        [InlineKeyboardButton("🧾 Invoice", callback_data=f"invoice:{link_id}")],
    ])
    if query:
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_seller(update):
        return
    if not context.args:
        await update.message.reply_text(
            f"📝 Usage: {code('/cancel PAY-XXXX')}", parse_mode="HTML",
        )
        return
    from database import payments as paydb
    link = paydb.get_link(context.args[0].strip().upper())
    if not link:
        await update.message.reply_text("🔍 Link not found.")
        return
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Yes, cancel", callback_data=f"cancel:yes:{link['link_id']}"),
        InlineKeyboardButton("❌ Keep it", callback_data="cancel:no"),
    ]])
    await update.message.reply_text(
        f"🗑️ Cancel {code(link['link_id'])} ({link['amount_expected']:.0f} {link['currency']})?\n"
        f"Buyer won't be able to pay.",
        parse_mode="HTML", reply_markup=kb,
    )


async def cancel_confirm_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, link_id: str):
    from providers import cashfree
    from database import payments as paydb
    if link_id:
        link = paydb.get_link(link_id)
        if link and link["method"] == "upi" and link["status"] == "ACTIVE":
            try:
                cashfree.cancel_link(link_id)
            except Exception as e:
                await update.callback_query.edit_message_text(
                    f"❌ Cancel failed: {esc(str(e))}", parse_mode="HTML",
                )
                return
        if link:
            paydb.set_link_status(link_id, "CANCELLED")
        await update.callback_query.edit_message_text(f"🗑️ Cancelled {code(link_id)}", parse_mode="HTML")
    else:
        await update.callback_query.edit_message_text("Kept. Link still active ✅")
