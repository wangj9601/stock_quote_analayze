# -*- coding: utf-8 -*-
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1] / "frontend"
ver = "20260925q"
pairs = [
    ("design-tokens.css", ver),
    ("analysis-ops.css", ver),
    ("ops-data.css", ver),
    ("ops-surfaces.css", ver),
    ("screening-ops.css", ver),
]
n = 0
for html in sorted(root.glob("*.html")):
    t = html.read_text(encoding="utf-8")
    orig = t
    for name, v in pairs:
        t = re.sub(
            rf'(href="css/{re.escape(name)})(\?v=[^"]*)?(")',
            rf"\1?v={v}\3",
            t,
        )
    if t != orig:
        html.write_text(t, encoding="utf-8", newline="\n")
        n += 1
print("bumped", n, "->", ver)
