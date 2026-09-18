"""FastAPI webhook receiver: verifies, marks sales paid, notifies seller."""
import hmac
import hashlib
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from telegram import Bot

import config
from database import payments as paydb
from database.connection import get_sale_by_code, mark_sales_paid
from core.format import fmt_sale_invoice, fmt_plink_invoice, code

logger = logging.getLogger(__name__)
app = FastAPI(title="tg-payment-pro webhooks")


def _verify_hmac(raw: bytes, signature: str, secret: str):
    if not secret or not signature:
        return False
    good = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(good, signature)


async def _settle(link_id, tx_id, amount_paid, source_url=""):
    link = paydb.get_link(link_id)
    if not link:
        return False, "unknown link"
    if paydb.has_payment(link_id):
        return True, "already settled"
    paydb.record_payment(link_id, tx_id, float(amount_paid or link["amount_expected"]))
    settled = float(amount_paid or link["amount_expected"])
    sale_codes = link.get("sale_codes") or []
    if link.get("kind") == "sale" and sale_codes:
        mark_sales_paid(sale_codes)
        sales = [get_sale_by_code(c) for c in sale_codes]
        sales = [s for s in sales if s]
        text = fmt_sale_invoice(link, sales, tx_id, source_url or link["url"], settled)
    else:
        text = fmt_plink_invoice(link, tx_id, settled)
    admin_text = text + f"\nSeller: {code(link['creator_user_id'])}"
    bot = Bot(token=config.BOT_TOKEN)
    try:
        await bot.send_message(chat_id=link["creator_user_id"], text=text, parse_mode="HTML")
    except Exception as e:
        logger.warning("notify creator failed: %s", e)
    try:
        if link["creator_user_id"] != config.ADMIN_USER_ID:
            await bot.send_message(chat_id=config.ADMIN_USER_ID, text=admin_text, parse_mode="HTML")
    except Exception as e:
        logger.warning("notify admin failed: %s", e)
    return True, "settled"


@app.post("/webhook/cashfree")
async def cashfree_webhook(request: Request):
    raw = await request.body()
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False}, status_code=400)
    data = body.get("data", body)
    link_id = str(data.get("link_id", ""))
    event = str(body.get("type", "")).upper()
    if config.CASHFREE_WEBHOOK_SECRET:
        sig = request.headers.get("x-cf-signature", "")
        if not _verify_hmac(raw, sig, config.CASHFREE_WEBHOOK_SECRET):
            return JSONResponse({"ok": False}, status_code=401)
    # Source of truth: fetch live status (covers PAID, EXPIRED, CANCELLED)
    try:
        from providers import cashfree
        live = cashfree.fetch_link(link_id) if link_id else {}
        status = str(live.get("link_status", "")).upper()
        paid = float(live.get("link_amount_paid", 0) or 0)
    except Exception:
        status, paid = event, float(data.get("link_amount_paid", 0) or 0)
    if status == "PAID" or event == "PAID":
        order = data.get("order", {}) or {}
        tx = str(order.get("transaction_id", "") or data.get("cf_link_id", ""))
        ok, msg = await _settle(link_id, tx, paid or data.get("link_amount"))
        return {"ok": ok, "msg": msg}
    if status in ("EXPIRED", "CANCELLED"):
        paydb.set_link_status(link_id, status)
        return {"ok": True, "msg": status.lower()}
    return {"ok": True, "msg": "ignored"}


@app.post("/webhook/request")
async def request_webhook(request: Request):
    raw = await request.body()
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False}, status_code=400)
    if config.RN_WEBHOOK_SECRET:
        sig = request.headers.get("x-request-network-signature", "")
        if not _verify_hmac(raw, sig, config.RN_WEBHOOK_SECRET):
            return JSONResponse({"ok": False}, status_code=401)
    if str(body.get("event", "")) != "payment.confirmed":
        return {"ok": True, "msg": "ignored"}
    # Reconcile by reference (we set reference=link_id) or requestId via provider_ref
    ref = str(body.get("reference", "") or "")
    link = paydb.get_link(ref) if ref else None
    if not link:
        # fallback: match provider_ref containing requestId
        req_id = str(body.get("requestId", ""))
        link = _find_by_request_id(req_id) if req_id else None
    if not link:
        return JSONResponse({"ok": False, "msg": "unknown link"}, status_code=404)
    tx = str(body.get("txHash", ""))
    ok, msg = await _settle(link["link_id"], tx, body.get("totalAmountPaid") or body.get("amount"))
    return {"ok": ok, "msg": msg}


def _find_by_request_id(request_id):
    from database.connection import connect_payments_db
    from database.connection import _d
    conn = connect_payments_db()
    try:
        row = conn.execute(
            "SELECT link_id FROM payment_links WHERE provider_ref LIKE ?", (f"%{request_id}%",)
        ).fetchone()
        if not row:
            return None
        return paydb.get_link(_d(row)["link_id"])
    finally:
        conn.close()


@app.get("/health")
async def health():
    return {"ok": True}


# Register mobile webview routes on the same app (/books/sales, /books/plink)
try:
    import webview.routes  # noqa: F401
except Exception:
    pass
