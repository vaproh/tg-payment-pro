# AGENTS.md — tg-payment-pro

## What this is
Telegram payment-link bot extending tg-seller-pro. Cashfree (UPI/INR) + Request Network (crypto/USD). Webhooks auto-mark seller-pro sales `paid`.

## Commands
- `just run` / `uv run main.py` — polling bot
- `just webhook` / `uv run uvicorn webhooks.server:app --host 0.0.0.0 --port 8000` — webhooks + books webview (same app)
- `uv run --with pytest pytest tests/ -q` — tests
- `uv run python -m py_compile <file>` — syntax check

## Conventions
- `uv` for env/deps. `config.py` must stay import-safe (no raise at import; validate in `main()`).
- Shared SQLite via `DB_PATH` (default `../tg-seller-pro/data/reddit_accounts.db`). New tables only: `payment_links`, `payments`. Never alter seller-pro tables; use `mark_sales_paid()` for status changes.
- Amounts from DB, not user input. Custom override is explicit and stored as `amount_expected` without rewriting `sales.price`.
- Roles mirror seller-pro: sellers own their links (`creator_user_id` / `sales.seller_id`), admin bypasses. Check `core/permissions.py`.
- Webhook handlers must be idempotent (`payments.link_id` unique, `has_payment()` guard) and notify in chat, not just logs. Verify-then-fetch pattern for Cashfree; HMAC when secret configured.
- Currency: UPI prompts in INR, crypto in USD. Always show both using `providers/fx.py` (cached, 10-min TTL).
- Never commit `.env`, `data/`, `logs/`, `.venv/`. No secrets in code or tests.
