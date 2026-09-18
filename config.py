import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
try:
    ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))
except ValueError:
    ADMIN_USER_ID = 0

_default_db = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "tg-seller-pro",
    "data", "reddit_accounts.db",
)
DB_PATH = os.path.abspath(os.getenv("DB_PATH", _default_db))

CASHFREE_ENV = os.getenv("CASHFREE_ENV", "sandbox").lower()
CASHFREE_CLIENT_ID = os.getenv("CASHFREE_CLIENT_ID", "").strip()
CASHFREE_CLIENT_SECRET = os.getenv("CASHFREE_CLIENT_SECRET", "").strip()
CASHFREE_WEBHOOK_SECRET = os.getenv("CASHFREE_WEBHOOK_SECRET", "").strip()
CASHFREE_NOTIFY_URL = os.getenv("CASHFREE_NOTIFY_URL", "").strip()

RN_CLIENT_ID = os.getenv("RN_CLIENT_ID", "").strip()
RN_WEBHOOK_SECRET = os.getenv("RN_WEBHOOK_SECRET", "").strip()
RN_DESTINATION_ID = os.getenv("RN_DESTINATION_ID", "").strip()
RN_NOTIFY_URL = os.getenv("RN_NOTIFY_URL", "").strip()

INR_PER_USD_OVERRIDE = os.getenv("INR_PER_USD", "").strip()
WEBAPP_BASE_URL = os.getenv("WEBAPP_BASE_URL", "").rstrip("/")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")

CASHFREE_BASE = (
    "https://api.cashfree.com" if CASHFREE_ENV == "prod" else "https://sandbox.cashfree.com"
)

# Validated in main.py so tests/imports don't crash on empty .env.
