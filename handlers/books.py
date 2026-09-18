import hmac
import hashlib
import time

from telegram import Update
from telegram.ext import ContextTypes

import config
from core.permissions import require_seller, get_user_role
from core.format import code, esc
from database import payments as paydb


def sign_token(user_id):
    exp = int(time.time()) + 86400
    msg = f"{user_id}:{exp}"
    sig = hmac.new(config.BOT_TOKEN.encode(), msg.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{user_id}:{exp}:{sig}"


def verify_token(token):
    try:
        uid, exp, sig = token.split(":")
        if int(exp) < time.time():
            return None
        msg = f"{uid}:{exp}"
        good = hmac.new(config.BOT_TOKEN.encode(), msg.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(good, sig):
            return None
        return int(uid)
    except Exception:
        return None


def _scope(user_id):
    return None if get_user_role(user_id) == "admin" else user_id


async def salesbook_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_seller(update):
        return
    rows = paydb.list_links(kind="sale", creator_user_id=_scope(update.effective_user.id), limit=20)
    if not rows:
        await update.message.reply_text("No sale links yet.")
        return
    lines = ["<b>Sale book (latest 20)</b>"]
    for r in rows:
        codes = ",".join(r.get("sale_codes") or [])
        lines.append(
            f"{code(r['link_id'])} | {r['method']} | {r['amount_expected']:.0f} {r['currency']} "
            f"| {r['status']} | {esc(codes)}"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def plinkbook_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_seller(update):
        return
    rows = paydb.list_links(kind="plink", creator_user_id=_scope(update.effective_user.id), limit=20)
    if not rows:
        await update.message.reply_text("No custom links yet.")
        return
    lines = ["<b>Plink book (latest 20)</b>"]
    for r in rows:
        lines.append(
            f"{code(r['link_id'])} | {r['method']} | {r['amount_expected']:.0f} {r['currency']} "
            f"| {r['status']} | {esc(r.get('purpose') or '-')}"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def invoice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_seller(update):
        return
    if not context.args:
        await update.message.reply_text(f"Usage: {code('/invoice PAY-XXXX')}", parse_mode="HTML")
        return
    link = paydb.get_link(context.args[0].strip().upper())
    if not link:
        await update.message.reply_text("Link not found.")
        return
    if get_user_role(update.effective_user.id) != "admin" and link["creator_user_id"] != update.effective_user.id:
        await update.message.reply_text("Not yours.")
        return
    from core.format import fmt_sale_invoice, fmt_plink_invoice
    from database.connection import get_sale_by_code
    settled = link.get("settled_amount") or link.get("amount_expected")
    if link.get("kind") == "sale":
        sales = [get_sale_by_code(c) for c in (link.get("sale_codes") or [])]
        # get_link returns sale_codes as list already
        sales = [s for s in sales if s]
        text = fmt_sale_invoice(link, sales, link.get("tx_id", ""), link.get("url", ""), settled)
    else:
        text = fmt_plink_invoice(link, link.get("tx_id", ""), settled)
    await update.message.reply_text(text, parse_mode="HTML")


async def books_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_seller(update):
        return
    if not config.WEBAPP_BASE_URL:
        await update.message.reply_text("Webview not configured (WEBAPP_BASE_URL). Use /salesbook and /plinkbook.")
        return
    token = sign_token(update.effective_user.id)
    await update.message.reply_text(
        f"Sales book:\n{code(f'{config.WEBAPP_BASE_URL}/sales?token={token}')}\n\n"
        f"Plink book:\n{code(f'{config.WEBAPP_BASE_URL}/plink?token={token}')}",
        parse_mode="HTML",
    )
