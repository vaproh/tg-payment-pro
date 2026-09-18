from fastapi.responses import HTMLResponse
from webhooks.server import app
from handlers.books import verify_token, _scope
from database import payments as paydb
from webview.books_html import render


@app.get("/books/sales", response_class=HTMLResponse)
async def books_sales(token: str = "", q: str = ""):
    uid = verify_token(token)
    if not uid:
        return HTMLResponse("Invalid or expired link. Run /books again.", status_code=401)
    rows = paydb.list_links(kind="sale", creator_user_id=_scope(uid), limit=100)
    return render("sale", rows, token, q)


@app.get("/books/plink", response_class=HTMLResponse)
async def books_plink(token: str = "", q: str = ""):
    uid = verify_token(token)
    if not uid:
        return HTMLResponse("Invalid or expired link. Run /books again.", status_code=401)
    rows = paydb.list_links(kind="plink", creator_user_id=_scope(uid), limit=100)
    return render("plink", rows, token, q)
