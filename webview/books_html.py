"""Mobile-friendly books webview (Tailwind CDN, token auth)."""
import html

PAGE = """<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<script src="https://cdn.tailwindcss.com"></script>
</head><body class="bg-slate-950 text-slate-100 min-h-screen">
<div class="max-w-xl mx-auto p-4">
<h1 class="text-xl font-bold mb-1">{title}</h1>
<p class="text-xs text-slate-400 mb-4">{subtitle}</p>
<form method="get" class="flex gap-2 mb-4">
<input type="hidden" name="token" value="{token}">
<input name="q" value="{q}" placeholder="Search link / sale / label"
 class="flex-1 rounded-xl px-3 py-2 bg-slate-900 border border-slate-700 text-sm">
<button class="rounded-xl px-4 py-2 bg-emerald-500 text-slate-950 font-semibold text-sm">Go</button>
</form>
<div class="space-y-3">{cards}</div>
</div></body></html>"""

CARD = """<div class="rounded-2xl border border-slate-800 bg-slate-900 p-3">
<div class="flex justify-between items-center">
<span class="font-mono text-sm font-bold">{link_id}</span>
<span class="text-[11px] px-2 py-1 rounded-full {pill}">{status}</span>
</div>
<div class="text-sm mt-1">{detail}</div>
<div class="text-xs text-slate-400 mt-1">{meta}</div>
<a href="{url}" class="text-emerald-400 text-xs break-all">{url}</a>
</div>"""


def render(kind, rows, token, q=""):
    title = "Sales book" if kind == "sale" else "Plink book"
    subtitle = "Latest 100. Sale links mark seller-pro sales paid on settle." if kind == "sale" else "Latest 100 custom payments."
    cards = []
    for r in rows[:100]:
        if q:
            hay = f"{r['link_id']} {' '.join(r.get('sale_codes') or [])} {r.get('purpose') or ''}".lower()
            if q.lower() not in hay:
                continue
        if kind == "sale":
            detail = f"{r['method'].upper()} - {r['amount_expected']:.0f} {r['currency']} - {(r.get('sale_codes') or [])}"
        else:
            detail = f"{r['method'].upper()} - {r['amount_expected']:.0f} {r['currency']} - {html.escape(r.get('purpose') or '-')}"
        pill = "bg-emerald-500/20 text-emerald-300" if r["status"] == "PAID" else "bg-amber-500/20 text-amber-300"
        cards.append(CARD.format(
            link_id=html.escape(r["link_id"]), status=html.escape(r["status"]), pill=pill,
            detail=html.escape(detail),
            meta=f"tx {html.escape(str(r.get('tx_id') or '-'))} - {html.escape(str(r.get('created_at') or ''))}",
            url=html.escape(r.get("url") or "#"),
        ))
    return PAGE.format(title=title, subtitle=subtitle, token=html.escape(token),
                       q=html.escape(q or ""), cards="".join(cards) or "<p>No matches.</p>")
