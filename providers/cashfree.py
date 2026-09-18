"""Cashfree Payment Links (UPI-only). Docs: POST /pg/links."""
import logging
import requests

import config

logger = logging.getLogger(__name__)


def _headers():
    return {
        "x-api-version": "2022-09-01",
        "x-client-id": config.CASHFREE_CLIENT_ID,
        "x-client-secret": config.CASHFREE_CLIENT_SECRET,
        "Content-Type": "application/json",
    }


def create_upi_link(link_id, amount_inr, sale_codes, notify_url=""):
    payload = {
        "link_id": link_id,
        "link_amount": float(amount_inr),
        "link_currency": "INR",
        "link_purpose": f"Sale {', '.join(sale_codes)}" if sale_codes else "Custom payment",
        "link_partial_payments": False,
        "link_notify": {"send_email": False, "send_sms": False},
        "link_meta": {
            "payment_methods": "upi",
            "upi_intent": True,
            "notify_url": notify_url or config.CASHFREE_NOTIFY_URL,
        },
        "customer_details": {"customer_phone": "9999999999"},
    }
    r = requests.post(
        f"{config.CASHFREE_BASE}/pg/links", json=payload, headers=_headers(), timeout=20
    )
    r.raise_for_status()
    data = r.json()
    return {"url": data["link_url"], "provider_ref": str(data.get("cf_link_id", ""))}


def fetch_link(link_id):
    r = requests.get(
        f"{config.CASHFREE_BASE}/pg/links/{link_id}", headers=_headers(), timeout=15
    )
    r.raise_for_status()
    return r.json()


def cancel_link(link_id):
    r = requests.post(
        f"{config.CASHFREE_BASE}/pg/links/{link_id}/cancel",
        headers=_headers(), timeout=15,
    )
    r.raise_for_status()
    return r.json()
