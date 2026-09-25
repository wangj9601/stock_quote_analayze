# -*- coding: utf-8 -*-
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
html = root / "frontend" / "stock.html"
t = html.read_text(encoding="utf-8")

reps = [
    ('<button class="watchlist-toggle">⭐ 自选</button>', '<button class="watchlist-toggle" type="button">自选</button>'),
    ("<h3>📊 交易建议</h3>", "<h3>交易建议</h3>"),
    ("<h3>📈 其他指标</h3>", "<h3>其他指标</h3>"),
    ("css/stock-ops.css?v=20260925c", "css/stock-ops.css?v=20260925polish"),
    ("css/stock-ops.css?v=20260925polish", "css/stock-ops.css?v=20260925polish"),  # noop if already
    ("js/stock.js?v=20260924-no-thirdparty", "js/stock.js?v=20260925polish"),
]
for old, new in reps:
    if old != new and old in t:
        t = t.replace(old, new)
        print("replaced", len(old))

t, n = re.subn(r"js/stock_hk\.js(?:\?v=[^'\"]+)?", "js/stock_hk.js?v=20260925polish", t)
print("hk", n)

html.write_text(t, encoding="utf-8")
t2 = html.read_text(encoding="utf-8")
print("star_gone", "⭐" not in t2)
print("emoji_gone", "📊" not in t2 and "📈" not in t2)
print("cache", "20260925polish" in t2)
print("title_ok", "个股详情" in t2)
