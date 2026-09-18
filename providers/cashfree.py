"""Cashfree Payment Links (UPI-only). Docs: POST /pg/links."""
import logging
import requests
from datetime import datetime, timedelta, timezone

import config

logger = logging.getLogger(__name__)

LINK_TTL_HOURS = 1


def _headers():
    return {
        "x-api-version": "2022-09-01",
        "x-client-id": config.CASHFREE_CLIENT_ID,
        "x-client-secret": config.CASHFREE_CLIENT_SECRET,
        "Content-Type": "application/json",
    }


def _raise_for_status(r):
    """Like raise_for_status but surfaces Cashfree's code/message in the error."""
    try:
        r.raise_for_status()
    except requests.HTTPError as e:
        try:
            body = r.json()
            detail = body.get("message") or body.get("code") or r.text
        except Exception:
            detail = r.text[:300]
        raise RuntimeError(f"Cashfree {r.status_code}: {detail}") from e


def _expiry_iso():
    return (datetime.now(timezone.utc) + timedelta(hours=LINK_TTL_HOURS)).strftime(
        "%Y-%m-%dT%H:%M:%S+00:00"
    )


def create_upi_link(link_id, amount_inr, sale_codes, notify_url="", customer_phone="9999999999"):
    payload = {
        "link_id": link_id,
        "link_amount": float(amount_inr),
        "link_currency": "INR",
        "link_purpose": f"Sale {', '.join(sale_codes)}" if sale_codes else "Custom payment",
        "link_partial_payments": False,
        "link_expiry_time": _expiry_iso(),
        "link_auto_reminders": True,
        "link_notify": {"send_email": False, "send_sms": False},
        "link_meta": {
            "payment_methods": "upi",
            "upi_intent": True,
            "notify_url": notify_url or config.CASHFREE_NOTIFY_URL,
        },
        "customer_details": {"customer_phone": customer_phone or "9999999999"},
    }
    r = requests.post(
        f"{config.CASHFREE_BASE}/pg/links", json=payload, headers=_headers(), timeout=20
    )
    _raise_for_status(r)
    data = r.json()
    return {"url": data["link_url"], "provider_ref": str(data.get("cf_link_id", ""))}


def fetch_link(link_id):
    r = requests.get(
        f"{config.CASHFREE_BASE}/pg/links/{link_id}", headers=_headers(), timeout=15
    )
    _raise_for_status(r)
    return r.json()


def cancel_link(link_id):
    r = requests.post(
        f"{config.CASHFREE_BASE}/pg/links/{link_id}/cancel",
        headers=_headers(), timeout=15,
    )
    _raise_for_status(r)
    return r.json()
