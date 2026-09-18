import secrets
from providers import cashfree, requestnet
from database import payments as paydb


def new_link_id(prefix="PAY"):
    return f"{prefix}-" + secrets.token_hex(4).upper()


def create_and_store(kind, method, amount, currency, sale_codes, purpose,
                     creator_user_id, amount_inr, amount_usd, rate):
    link_id = new_link_id("PAY" if kind == "sale" else "PLINK")
    if method == "upi":
        res = cashfree.create_upi_link(link_id, amount, sale_codes or [])
    else:
        res = requestnet.create_crypto_link(link_id, amount, creator_user_id)
    paydb.create_link({
        "link_id": link_id,
        "kind": kind,
        "method": method,
        "url": res["url"],
        "provider_ref": res.get("provider_ref", ""),
        "amount_expected": float(amount),
        "currency": currency,
        "amount_inr": float(amount_inr),
        "amount_usd": float(amount_usd),
        "rate": float(rate),
        "sale_codes": sale_codes or [],
        "purpose": purpose,
        "creator_user_id": creator_user_id,
    })
    return link_id, res["url"]
