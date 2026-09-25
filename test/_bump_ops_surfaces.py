# -*- coding: utf-8 -*-
"""Bump ops-surfaces + stock-ops cache versions on ops-map pages."""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1] / "frontend"
SURF_VER = "20260925h"
STOCK_OPS_VER = "20260925b"

skip = {"login.html", "animation-test.html", "clear_cache_instructions.html",
        "index_new.html", "test_news.html", "recommend.html", "triple_volume_observe.html"}

surf_link = f'<link rel="stylesheet" href="css/ops-surfaces.css?v={SURF_VER}">'
surf_re = re.compile(r'<link rel="stylesheet" href="css/ops-surfaces\.css[^"]*">')
stock_ops_re = re.compile(r'(href="css/stock-ops\.css)(\?v=[^"]*)?(")')

updated = []
for html in sorted(root.glob("*.html")):
    if html.name in skip:
        continue
    t = html.read_text(encoding="utf-8")
    orig = t
    if "ops-map" not in t and "ops-shell.css" not in t:
        continue
    if surf_re.search(t):
        t = surf_re.sub(surf_link, t)
    elif "</head>" in t:
        t = t.replace("</head>", f"    {surf_link}\n</head>", 1)
    if "stock-ops.css" in t:
        t = stock_ops_re.sub(rf'\1?v={STOCK_OPS_VER}\3', t)
    if t != orig:
        html.write_text(t, encoding="utf-8")
        updated.append(html.name)

print("updated:", len(updated))
for n in updated:
    print(" ", n)
