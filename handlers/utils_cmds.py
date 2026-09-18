import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import config
from core.permissions import require_seller
from core.format import code
from providers.fx import get_inr_per_usd, inr_to_usd, usd_to_inr
from database.connection import connect_seller_db
from handlers.menu import menu_kb


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_seller(update):
        return
    await update.message.reply_text(
        "💰 <b>Payment Bot</b> - what do you need?",
        parse_mode="HTML",
        reply_markup=menu_kb(),
    )


async def ping_text():
    t0 = time.time()
    db_ok = False
    try:
        conn = connect_seller_db()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        db_ok = True
    except Exception:
        pass
    rate, src, _ = get_inr_per_usd()
    ms = int((time.time() - t0) * 1000)
    return f"🏓 pong {ms}ms\n🗄️ db={'✅ ok' if db_ok else '❌ fail'}\n💱 Rs {rate:.2f}/$ ({src})"


async def rate_text():
    rate, src, ttl = get_inr_per_usd()
    extra = f", cached {ttl}s left" if src.startswith("cache") else ""
    return f"📈 Rs {rate:.2f}/$ ({src}{extra})"


def convert_text(raw_amount, raw_cur):
    try:
        amount = float(str(raw_amount).replace(",", ""))
    except ValueError:
        return "⚠️ Invalid amount."
    cur = str(raw_cur).upper()
    if cur == "INR":
        usd, rate, src = inr_to_usd(amount)
        return f"💱 Rs {amount:,.0f} = ${usd:,.2f}\n📌 Rs {rate:.2f}/$ ({src})"
    if cur == "USD":
        inr, rate, src = usd_to_inr(amount)
        return f"💱 ${amount:,.2f} = Rs {inr:,.0f}\n📌 Rs {rate:.2f}/$ ({src})"
    return "⚠️ Use INR or USD."


async def ping_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu", callback_data="menu:home")]])
    await update.message.reply_text(await ping_text(), reply_markup=kb)


async def convert_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_seller(update):
        return
    if len(context.args) < 2:
        await update.message.reply_text(
            f"📝 Usage: {code('/convert 1200 INR')} or {code('/convert 15 USD')}",
            parse_mode="HTML",
        )
        return
    await update.message.reply_text(convert_text(context.args[0], context.args[1]))


async def rate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_seller(update):
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh", callback_data="menu:rate")],
        [InlineKeyboardButton("⬅️ Menu", callback_data="menu:home")],
    ])
    await update.message.reply_text(await rate_text(), reply_markup=kb)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_cmd(update, context)
