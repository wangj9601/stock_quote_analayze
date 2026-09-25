# -*- coding: utf-8 -*-
from pathlib import Path
import re
root = Path(__file__).resolve().parents[1] / "frontend"
ver = "20260925p"
rx = re.compile(r'(href="css/design-tokens\.css)(\?v=[^"]*)?(")')
n = 0
for p in sorted(root.glob("*.html")):
    t = p.read_text(encoding="utf-8")
    if "design-tokens.css" not in t:
        continue
    t2 = rx.sub(rf"\1?v={ver}\3", t)
    if t2 != t:
        p.write_text(t2, encoding="utf-8", newline="\n")
        n += 1
print("bumped", n)
