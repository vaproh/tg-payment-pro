import json
from database.connection import connect, _d


def create_link(row):
    conn = connect()
    try:
        conn.execute(
            """INSERT INTO payment_links
               (link_id, kind, method, url, provider_ref, amount_expected, currency,
                amount_inr, amount_usd, rate, sale_codes, purpose, creator_user_id, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE')""",
            (
                row["link_id"], row["kind"], row["method"], row["url"],
                row.get("provider_ref"), row["amount_expected"], row["currency"],
                row.get("amount_inr", 0), row.get("amount_usd", 0), row.get("rate", 0),
                json.dumps(row.get("sale_codes") or []),
                row.get("purpose"), row["creator_user_id"],
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_link(link_id):
    conn = connect()
    try:
        row = conn.execute(
            """SELECT pl.*, p.tx_id, p.amount_paid as settled_amount
               FROM payment_links pl LEFT JOIN payments p ON p.link_id = pl.link_id
               WHERE pl.link_id = ?""",
            (link_id,),
        ).fetchone()
        d = _d(row) if row else None
        if d and d.get("sale_codes"):
            try:
                d["sale_codes"] = json.loads(d["sale_codes"])
            except Exception:
                d["sale_codes"] = []
        return d
    finally:
        conn.close()


def set_link_status(link_id, status, paid_at=None):
    conn = connect()
    try:
        if paid_at:
            conn.execute(
                "UPDATE payment_links SET status = ?, paid_at = ? WHERE link_id = ?",
                (status, paid_at, link_id),
            )
        else:
            conn.execute(
                "UPDATE payment_links SET status = ? WHERE link_id = ?", (status, link_id)
            )
        conn.commit()
    finally:
        conn.close()


def record_payment(link_id, tx_id, amount_paid):
    conn = connect()
    try:
        conn.execute(
            """INSERT OR IGNORE INTO payments (link_id, tx_id, amount_paid)
               VALUES (?, ?, ?)""",
            (link_id, tx_id, amount_paid),
        )
        conn.execute(
            "UPDATE payment_links SET status = 'PAID', paid_at = CURRENT_TIMESTAMP WHERE link_id = ?",
            (link_id,),
        )
        conn.commit()
    finally:
        conn.close()


def has_payment(link_id):
    conn = connect()
    try:
        row = conn.execute(
            "SELECT id FROM payments WHERE link_id = ?", (link_id,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def list_links(kind=None, creator_user_id=None, limit=20, offset=0):
    conn = connect()
    try:
        q = """SELECT pl.*, p.tx_id, p.amount_paid, p.paid_at as settled_at
               FROM payment_links pl LEFT JOIN payments p ON p.link_id = pl.link_id
               WHERE 1=1"""
        params = []
        if kind:
            q += " AND pl.kind = ?"
            params.append(kind)
        if creator_user_id is not None:
            q += " AND pl.creator_user_id = ?"
            params.append(creator_user_id)
        q += " ORDER BY pl.created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(q, params).fetchall()
        out = []
        for r in rows:
            d = _d(r)
            try:
                d["sale_codes"] = json.loads(d.get("sale_codes") or "[]")
            except Exception:
                d["sale_codes"] = []
            out.append(d)
        return out
    finally:
        conn.close()
