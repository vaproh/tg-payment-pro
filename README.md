# TG Payment Pro

Payment-link extension bot for [tg-seller-pro](../tg-seller-pro). Sellers generate a link from a sale, forward it to the buyer, and the bot auto-marks the sale `paid` when money lands. UPI via Cashfree, crypto via Request Network. No frontend needed for paying.

## How it works

```
tg-seller-pro                    tg-payment-pro                  buyer
  /sell -> SALE-XXXX
               -- /pay SALE-XXXX --> link PAY-XXXX (Cashfree / Request)
                                     -- forward URL --> pays in browser
  sales.payment_status                        webhook -> mark paid + invoice
   pending_payment -> paid                     seller + admin notified
```

- Amounts come from the seller-pro `sales` table, never from typed input (except explicit custom override).
- One link can cover multiple sales: `/pay SALE-A, SALE-B`.
- Off-book items use `/plink`, kept in a separate ledger.

## Commands

| Command | Description |
|---------|-------------|
| `/pay SALE-A, SALE-B` | Validate codes (must be `pending`, yours unless admin), show total Rs + $, pick method, pick total/custom, get link |
| `/plink 1200 upi Label` | Custom payment link (no sale rows) |
| `/cancel PAY-XXXX` | Cancel an active link |
| `/salesbook` | Sale-linked ledger (latest 20) |
| `/plinkbook` | Custom ledger (latest 20) |
| `/books` | Personal mobile webview URLs (signed, 24h) |
| `/invoice PAY-XXXX` | Resend invoice + TX details |
| `/convert 1200 INR` | INR <> USD at cached rate |
| `/rate` | Current Rs/$ rate + source |
| `/ping` | Bot + DB + FX health |
| `/start`, `/help` | Help |

Sellers see only their own links. Admin sees all.

## Quick start

```bash
cd tg-payment-pro
cp .env.example .env   # fill BOT_TOKEN (a DIFFERENT bot), ADMIN_USER_ID, provider keys
uv sync
uv run main.py         # Telegram polling
uv run uvicorn webhooks.server:app --host 0.0.0.0 --port 8000  # webhooks + books webview
```

`DB_PATH` defaults to `../tg-seller-pro/data/reddit_accounts.db` (shared SQLite, WAL mode). Payment tables (`payment_links`, `payments`) are auto-created in the same file.

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_TOKEN` | yes | Separate BotFather token for this bot |
| `ADMIN_USER_ID` | yes | Same admin as seller-pro |
| `DB_PATH` | no | Shared DB path |
| `CASHFREE_ENV` | no | `sandbox` / `prod` |
| `CASHFREE_CLIENT_ID` / `CASHFREE_CLIENT_SECRET` | for UPI | From Cashfree dashboard |
| `CASHFREE_NOTIFY_URL` | for UPI | `https://you/webhook/cashfree` |
| `RN_CLIENT_ID` | for crypto | Request Network client ID (bound payee destination) |
| `RN_DESTINATION_ID` | no | Override `<interopAddr>:<tokenAddress>` |
| `RN_NOTIFY_URL` | for crypto | `https://you/webhook/request` |
| `INR_PER_USD` | no | Rate override; empty = fetch + 10-min cache |
| `WEBAPP_BASE_URL` | no | Base URL used by `/books` to build personal links |

Cashfree links are UPI-only (`payment_methods=upi`, `upi_intent=true`). Crypto links invoice in USD (USDC recommended); INR totals are converted at link time and locked.

## Webhooks (source of truth)

- `POST /webhook/cashfree` — verifies (HMAC if `CASHFREE_WEBHOOK_SECRET`, else live `GET /pg/links/{id}`), on `PAID` records payment, marks all linked sales `paid`, notifies seller + admin with received amount + TX.
- `POST /webhook/request` — verifies HMAC if `RN_WEBHOOK_SECRET`, on `payment.confirmed` same settle path (matched by `reference=link_id`, fallback to `requestId` in `provider_ref`).
- Duplicate deliveries are idempotent (`payments.link_id` unique).
- `GET /health` — liveness.

## Books webview

`/books` sends signed per-user URLs for `/books/sales` and `/books/plink` (Tailwind, mobile-first, search). Seller token shows own links only.

## Testing

```bash
uv run --with pytest pytest tests/ -q
```

## Structure

```
main.py               # polling entry
config.py             # env config (import-safe, validated in main)
database/             # shared-DB reads (sales/sellers) + payment_links/payments ledger
core/                 # permissions (same roles as seller-pro), format, state (5-min TTL)
providers/            # cashfree.py, requestnet.py, fx.py (cached INR/USD)
handlers/             # pay, plink, books, utils_cmds, callbacks, messages
webhooks/server.py    # FastAPI: webhooks + health (+ books routes)
webview/              # books_html.py (Tailwind) + routes.py
tests/                # pytest
```

Private use only.
