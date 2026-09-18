import time
from telegram import Update
from telegram.ext import ContextTypes

import config
from core.permissions import require_seller
from core.format import code
from providers.fx import get_inr_per_usd, inr_to_usd, usd_to_inr
from database.connection import connect_seller_db


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_seller(update):
        return
    await update.message.reply_text(
        "Payment bot.\n"
        f"{code('/pay SALE-XXX, SALE-YYY')} - sale links\n"
        f"{code('/plink 1200 upi Label')} - custom links\n"
        f"{code('/salesbook')} {code('/plinkbook')} {code('/books')} {code('/invoice PAY-XXXX')}\n"
        f"{code('/convert 1200 INR')} {code('/rate')} {code('/ping')} {code('/cancel PAY-XXXX')}",
        parse_mode="HTML",
    )


async def ping_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    await update.message.reply_text(
        f"pong {ms}ms | db={'ok' if db_ok else 'fail'} | Rs {rate:.2f}/$ ({src})",
    )


async def convert_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_seller(update):
        return
    if len(context.args) < 2:
        await update.message.reply_text(f"Usage: {code('/convert 1200 INR')}", parse_mode="HTML")
        return
    try:
        amount = float(context.args[0].replace(",", ""))
    except ValueError:
        await update.message.reply_text("Invalid amount.")
        return
    cur = context.args[1].upper()
    if cur == "INR":
        usd, rate, src = inr_to_usd(amount)
        await update.message.reply_text(f"Rs {amount:.0f} = ${usd:.2f} (Rs {rate:.2f}/$, {src})")
    elif cur == "USD":
        inr, rate, src = usd_to_inr(amount)
        await update.message.reply_text(f"${amount:.2f} = Rs {inr:.0f} (Rs {rate:.2f}/$, {src})")
    else:
        await update.message.reply_text("Use INR or USD.")


async def rate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_seller(update):
        return
    rate, src, ttl = get_inr_per_usd()
    extra = f", cached {ttl}s left" if src == "cache" else ""
    await update.message.reply_text(f"Rs {rate:.2f}/$ ({src}{extra})")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_cmd(update, context)
