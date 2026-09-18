import sqlite3
import os
import logging

import config

logger = logging.getLogger(__name__)


def _ensure_dir(path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)


def connect_seller_db():
    """Read-only connection to tg-seller-pro shared DB (sales, sellers, accounts)."""
    _ensure_dir(config.DB_PATH)
    conn = sqlite3.connect(config.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def connect_payments_db():
    """Connection to payment bot's own DB (payment_links, payments)."""
    _ensure_dir(config.DB_PATH_PAYMENTS)
    conn = sqlite3.connect(config.DB_PATH_PAYMENTS, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def _d(row):
    if row is None:
        return {}
    if isinstance(row, dict):
        return row
    return dict(row)


def get_sale_by_code(sale_code):
    conn = connect_seller_db()
    try:
        row = conn.execute(
            """SELECT s.sale_code, s.price, s.payment_status, s.seller_id,
                      a.username, a.id as account_id
               FROM sales s JOIN accounts a ON a.id = s.account_id
               WHERE s.sale_code = ?""",
            (sale_code.strip(),),
        ).fetchone()
        return _d(row) if row else None
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()


def get_seller_id_by_user_id(user_id):
    conn = connect_seller_db()
    try:
        row = conn.execute(
            "SELECT id FROM sellers WHERE user_id = ? AND active = 1", (user_id,)
        ).fetchone()
        return row["id"] if row else None
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()


def mark_sales_paid(sale_codes):
    """Set sales paid + accounts sold in seller-pro DB. Idempotent."""
    if not sale_codes:
        return 0
    conn = connect_seller_db()
    try:
        n = 0
        for sc in sale_codes:
            sale = conn.execute(
                "SELECT id, account_id FROM sales WHERE sale_code = ?", (sc,)
            ).fetchone()
            if not sale:
                continue
            conn.execute(
                "UPDATE sales SET payment_status = 'paid' WHERE id = ?",
                (sale["id"],),
            )
            conn.execute(
                "UPDATE accounts SET status = 'sold' WHERE id = ?",
                (sale["account_id"],),
            )
            n += 1
        conn.commit()
        return n
    finally:
        conn.close()


def init_payments_db():
    """Create payment tables in the payments DB (not seller-pro DB)."""
    conn = connect_payments_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS payment_links (
                link_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL DEFAULT 'sale',
                method TEXT NOT NULL,
                url TEXT NOT NULL,
                provider_ref TEXT,
                amount_expected REAL NOT NULL,
                currency TEXT NOT NULL,
                amount_inr REAL NOT NULL DEFAULT 0,
                amount_usd REAL NOT NULL DEFAULT 0,
                rate REAL NOT NULL DEFAULT 0,
                sale_codes TEXT,
                purpose TEXT,
                creator_user_id INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                paid_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link_id TEXT NOT NULL UNIQUE,
                tx_id TEXT,
                amount_paid REAL NOT NULL DEFAULT 0,
                paid_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (link_id) REFERENCES payment_links(link_id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS ix_payment_links_creator
            ON payment_links (creator_user_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS ix_payment_links_status
            ON payment_links (status)
        """)
        conn.commit()
    finally:
        conn.close()
