from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import config
from core.permissions import require_seller, get_user_role
from core.format import code, esc, fmt_money_inr, fmt_money_usd
from core.state import state
from database.connection import get_sale_by_code, get_seller_id_by_user_id
from providers.fx import get_inr_per_usd, inr_to_usd
from handlers.linkgen import create_and_store


def parse_codes(raw):
    return [c.strip().upper() for c in raw.replace(";", ",").split(",") if c.strip()]


async def pay_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_seller(update):
        return
    user_id = update.effective_user.id
    raw = " ".join(context.args) if context.args else ""
    if not raw:
        await update.message.reply_text(f"Usage: {code('/pay SALE-XXX, SALE-YYY')}", parse_mode="HTML")
        return
    codes = parse_codes(raw)
    role = get_user_role(user_id)
    my_seller_id = get_seller_id_by_user_id(user_id)

    sales, problems = [], []
    for sc in codes:
        s = get_sale_by_code(sc)
        if not s:
            problems.append(f"Not found: {code(sc)}")
            continue
        if s["payment_status"] == "paid":
            problems.append(f"Already paid: {code(sc)}")
            continue
        if role != "admin" and s["seller_id"] != my_seller_id:
            problems.append(f"Not yours: {code(sc)}")
            continue
        sales.append(s)
    if problems:
        await update.message.reply_text("\n".join(problems), parse_mode="HTML")
        if not sales:
            return
    total_inr = round(sum(float(s["price"]) for s in sales), 0)
    total_usd, rate, _ = inr_to_usd(total_inr)

    state.set(user_id, "pay_codes", [s["sale_code"] for s in sales])
    state.set(user_id, "pay_total_inr", total_inr)
    state.set(user_id, "pay_total_usd", total_usd)
    state.set(user_id, "pay_rate", rate)
    state.set(user_id, "pay_stage", "method")

    lines = [f"{code(s['sale_code'])} | {esc(s.get('username',''))} | Rs {float(s['price']):.0f}" for s in sales]
    text = (
        f"<b>Sales ({len(sales)}):</b>\n" + "\n".join(lines) + "\n\n"
        f"Total: <b>{fmt_money_inr(total_inr)} / {fmt_money_usd(total_usd)}</b>\n"
        f"Rate: Rs {rate:.2f}/$\n\nChoose payment method:"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("UPI (INR)", callback_data="pay:method:upi"),
        InlineKeyboardButton("Crypto (USD)", callback_data="pay:method:crypto"),
    ]])
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def pay_method_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, method: str):
    query = update.callback_query
    user_id = update.effective_user.id
    codes = state.get(user_id, "pay_codes")
    if not codes:
        await query.edit_message_text("Session expired. Run /pay again.")
        return
    state.set(user_id, "pay_method", method)
    state.set(user_id, "pay_stage", "amount")
    total_inr = state.get(user_id, "pay_total_inr", 0)
    total_usd = state.get(user_id, "pay_total_usd", 0)
    rate = state.get(user_id, "pay_rate", 0)
    if method == "upi":
        prompt = (
            f"Method: <b>UPI</b> - enter amount in <b>INR</b>\n"
            f"Total: {fmt_money_inr(total_inr)} (~{fmt_money_usd(total_usd)})\n"
            f"Rate: Rs {rate:.2f}/$"
        )
    else:
        prompt = (
            f"Method: <b>Crypto</b> - enter amount in <b>USD</b>\n"
            f"Total: {fmt_money_usd(total_usd)} (~{fmt_money_inr(total_inr)})\n"
            f"Rate: Rs {rate:.2f}/$"
        )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(f"Use total ({total_inr:.0f} INR)" if method == "upi" else f"Use total ({total_usd:.2f} USD)",
                             callback_data="pay:amt:full"),
        InlineKeyboardButton("Custom", callback_data="pay:amt:custom"),
    ]])
    await query.edit_message_text(prompt, parse_mode="HTML", reply_markup=kb)


async def pay_amount_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, choice: str):
    query = update.callback_query
    user_id = update.effective_user.id
    if choice == "custom":
        state.set(user_id, "pay_stage", "custom_amount")
        method = state.get(user_id, "pay_method", "upi")
        unit = "INR" if method == "upi" else "USD"
        await query.edit_message_text(f"Send custom amount in {unit}:")
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
    if not codes:
        target = query.edit_message_text if query else update.message.reply_text
        await target("Session expired. Run /pay again.")
        return

    if custom is None:
        amount = total_inr if method == "upi" else total_usd
    else:
        amount = custom
    currency = "INR" if method == "upi" else "USD"
    if method == "upi":
        amount_inr, amount_usd = float(amount), round(float(amount) / rate, 2) if rate else 0
    else:
        amount_usd, amount_inr = float(amount), round(float(amount) * rate, 0) if rate else 0

    try:
        link_id, url = create_and_store(
            "sale", method, amount, currency, codes, None,
            user_id, amount_inr, amount_usd, rate,
        )
    except Exception as e:
        msg = f"Provider error: {esc(str(e))}"
        if query:
            await query.edit_message_text(msg, parse_mode="HTML")
        else:
            await update.message.reply_text(msg, parse_mode="HTML")
        return
    for k in ("pay_codes", "pay_total_inr", "pay_total_usd", "pay_rate", "pay_method", "pay_stage"):
        state.pop(user_id, k, None)
    text = (
        f"Send this link to buyer:\n{code(url)}\n\n"
        f"Link: {code(link_id)}\nSales: {', '.join(code(c) for c in codes)}\n"
        f"Amount: <b>{amount} {currency}</b> ({fmt_money_inr(amount_inr)} / {fmt_money_usd(amount_usd)})"
    )
    if query:
        await query.edit_message_text(text, parse_mode="HTML")
    else:
        await update.message.reply_text(text, parse_mode="HTML")


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_seller(update):
        return
    from providers import cashfree
    from database import payments as paydb
    if not context.args:
        await update.message.reply_text(f"Usage: {code('/cancel PAY-XXXX')}", parse_mode="HTML")
        return
    link = paydb.get_link(context.args[0].strip().upper())
    if not link:
        await update.message.reply_text("Link not found.")
        return
    if link["method"] == "upi":
        try:
            cashfree.cancel_link(link["link_id"])
        except Exception as e:
            await update.message.reply_text(f"Cancel failed: {esc(str(e))}", parse_mode="HTML")
            return
    paydb.set_link_status(link["link_id"], "CANCELLED")
    await update.message.reply_text(f"Cancelled {code(link['link_id'])}", parse_mode="HTML")
