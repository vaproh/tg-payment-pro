"""Main menu + menu callbacks. Every feature reachable by tap."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import config
from core.permissions import require_seller
from core.format import code
from core.state import state
from handlers.books import sign_token


def menu_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💰 Sale Link", callback_data="menu:pay"),
            InlineKeyboardButton("🔗 Custom Link", callback_data="menu:plink"),
        ],
        [
            InlineKeyboardButton("📒 Sales", callback_data="menu:sales"),
            InlineKeyboardButton("📕 Plinks", callback_data="menu:plinks"),
            InlineKeyboardButton("📱 Webview", callback_data="menu:books"),
        ],
        [
            InlineKeyboardButton("💱 Convert", callback_data="menu:convert"),
            InlineKeyboardButton("📈 Rate", callback_data="menu:rate"),
            InlineKeyboardButton("🏓 Ping", callback_data="menu:ping"),
        ],
    ])


async def menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str):
    query = update.callback_query
    user_id = update.effective_user.id
    if action == "pay":
        state.set(user_id, "pay_stage", "await_codes")
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu", callback_data="menu:home")]])
        await query.edit_message_text(
            "💰 <b>Sale Link</b>\n\n📦 Send sale codes, comma separated:\n<code>SALE-A, SALE-B</code>",
            parse_mode="HTML", reply_markup=kb,
        )
    elif action == "plink":
        state.set(user_id, "plink_stage", "await_amount")
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu", callback_data="menu:home")]])
        await query.edit_message_text(
            "🔗 <b>Custom Link</b>\n\n💵 Send amount in <b>INR</b> (label optional):\n<code>500 VPS setup</code>",
            parse_mode="HTML", reply_markup=kb,
        )
    elif action == "sales":
        from handlers.books import render_book_text
        text, kb = render_book_text("sale", user_id)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
    elif action == "plinks":
        from handlers.books import render_book_text
        text, kb = render_book_text("plink", user_id)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
    elif action == "books":
        if not config.WEBAPP_BASE_URL:
            await query.edit_message_text("⚠️ Webview not configured. Use 📒/📕 books.")
            return
        token = sign_token(user_id)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📒 Open Sales Book", url=f"{config.WEBAPP_BASE_URL}/sales?token={token}")],
            [InlineKeyboardButton("📕 Open Plink Book", url=f"{config.WEBAPP_BASE_URL}/plink?token={token}")],
            [InlineKeyboardButton("⬅️ Menu", callback_data="menu:home")],
        ])
        await query.edit_message_text("📱 <b>Books Webview</b> - tap to open:", parse_mode="HTML", reply_markup=kb)
    elif action == "convert":
        state.set(user_id, "misc_stage", "await_convert")
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu", callback_data="menu:home")]])
        await query.edit_message_text(
            "💱 Send like <code>1200 INR</code> or <code>15 USD</code>:",
            parse_mode="HTML", reply_markup=kb,
        )
    elif action == "rate":
        from handlers.utils_cmds import rate_text
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="menu:rate")],
            [InlineKeyboardButton("⬅️ Menu", callback_data="menu:home")],
        ])
        await query.edit_message_text(await rate_text(), reply_markup=kb)
    elif action == "ping":
        from handlers.utils_cmds import ping_text
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu", callback_data="menu:home")]])
        await query.edit_message_text(await ping_text(), reply_markup=kb)
    elif action == "home":
        for k in ("pay_stage", "plink_stage", "misc_stage"):
            state.pop(user_id, k, None)
        await query.edit_message_text("💰 <b>Payment Bot</b> - what do you need?", parse_mode="HTML", reply_markup=menu_kb())
