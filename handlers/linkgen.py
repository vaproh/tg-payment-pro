import secrets
from providers import cashfree, requestnet
from database import payments as paydb

DEFAULT_PHONE = "9999999999"


def normalize_phone(text):
    """Indian mobile -> 10 digits, or None. Accepts +91/91/0 prefixes, spaces, dashes."""
    d = "".join(c for c in str(text or "") if c.isdigit())
    if d.startswith("91") and len(d) == 12:
        d = d[2:]
    if d.startswith("0") and len(d) == 11:
        d = d[1:]
    if len(d) == 10 and d[0] in "6789":
        return d
    return None


def new_link_id(prefix="PAY"):
    return f"{prefix}-" + secrets.token_hex(4).upper()


def create_and_store(kind, method, amount, currency, sale_codes, purpose,
                     creator_user_id, amount_inr, amount_usd, rate, customer_phone="9999999999"):
    link_id = new_link_id("PAY" if kind == "sale" else "PLINK")
    if method == "upi":
        res = cashfree.create_upi_link(link_id, amount, sale_codes or [], customer_phone=customer_phone)
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
        "customer_phone": customer_phone or "9999999999",
    })
    return link_id, res["url"]
