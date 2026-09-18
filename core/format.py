import html


def esc(text):
    if text is None:
        return "-"
    return html.escape(str(text))


def code(text):
    return f"<code>{html.escape(str(text))}</code>"


def fmt_money_inr(amount):
    try:
        return f"Rs {float(amount):.0f}"
    except Exception:
        return "Rs -"


def fmt_money_usd(amount):
    try:
        return f"${float(amount):.2f}"
    except Exception:
        return "$-"


def _phone_line(link):
    phone = (link or {}).get("customer_phone", "")
    if phone and phone != "9999999999":
        return f"📱 Buyer: {code(phone)}\n"
    return ""


def fmt_sale_invoice(link, sales, tx_id, url, amount_paid=None):
    received = amount_paid if amount_paid is not None else link.get('amount_expected')
    lines = ["✅ <b>Payment Received (sale)</b>", ""]
    lines.append(f"🔗 Link: {code(link['link_id'])}")
    for s in sales:
        lines.append(f"  • {code(s.get('sale_code',''))} | {esc(s.get('username',''))} | Rs {float(s.get('price',0)):.0f}")
    lines += [
        "",
        f"💵 Expected: {code(str(link.get('amount_expected')) + ' ' + link.get('currency',''))}",
        f"💰 Received: {code(str(received) + ' ' + link.get('currency',''))}",
        f"🧾 TX: {code(tx_id or '-')}",
        f"🔗 Source: {esc(url or link.get('url',''))}",
    ]
    if _phone_line(link):
        lines.append(_phone_line(link))
    return "\n".join(lines)


def fmt_plink_invoice(link, tx_id, amount_paid=None):
    received = amount_paid if amount_paid is not None else link.get('amount_expected')
    lines = [
        "✅ <b>Payment Received (custom)</b>",
        "",
        f"🔗 Link: {code(link['link_id'])}",
        f"📝 Purpose: {esc(link.get('purpose') or '-')}",
        f"💵 Expected: {code(str(link.get('amount_expected')) + ' ' + link.get('currency',''))}",
        f"💰 Received: {code(str(received) + ' ' + link.get('currency',''))}",
        f"🧾 TX: {code(tx_id or '-')}",
        f"🔗 Source: {esc(link.get('url',''))}",
    ]
    if _phone_line(link):
        lines.append(_phone_line(link))
    return "\n".join(lines)
