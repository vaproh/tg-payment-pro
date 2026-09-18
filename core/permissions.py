import logging
import config
from database.connection import get_seller_id_by_user_id

logger = logging.getLogger(__name__)


def get_user_role(user_id):
    if user_id == config.ADMIN_USER_ID:
        return "admin"
    if get_seller_id_by_user_id(user_id) is not None:
        return "seller"
    return None


async def require_seller(update):
    user_id = update.effective_user.id
    if get_user_role(user_id) in ("admin", "seller"):
        return True
    if update.message:
        await update.message.reply_text("You are not authorized to use this bot.")
    elif update.callback_query:
        await update.callback_query.answer("Not authorized.", show_alert=True)
    return False


async def require_admin(update):
    user_id = update.effective_user.id
    if get_user_role(user_id) == "admin":
        return True
    if update.message:
        await update.message.reply_text("Admin access required.")
    elif update.callback_query:
        await update.callback_query.answer("Admin access required.", show_alert=True)
    return False
