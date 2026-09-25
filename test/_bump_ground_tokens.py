# -*- coding: utf-8 -*-
"""Bump design-tokens / ops-data / screening-ops / ops-surfaces cache versions (UTF-8)."""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1] / "frontend"
VER = "20260925o"

repls = [
    (re.compile(r'(href="css/design-tokens\.css)(\?v=[^"]*)?(")'), rf'\1?v={VER}\3'),
    (re.compile(r'(href="css/ops-data\.css)(\?v=[^"]*)?(")'), rf'\1?v={VER}\3'),
    (re.compile(r'(href="css/screening-ops\.css)(\?v=[^"]*)?(")'), rf'\1?v={VER}\3'),
    (re.compile(r'(href="css/ops-surfaces\.css)(\?v=[^"]*)?(")'), rf'\1?v={VER}\3'),
]

# Ensure design-tokens link exists with version even if bare
bare_dt = re.compile(r'href="css/design-tokens\.css"')

n = 0
for html in sorted(root.glob("*.html")):
    t = html.read_text(encoding="utf-8")
    if "ops-map" not in t and "design-tokens.css" not in t:
        continue
    orig = t
    if bare_dt.search(t) and f"design-tokens.css?v=" not in t:
        t = bare_dt.sub(f'href="css/design-tokens.css?v={VER}"', t)
    for rx, rep in repls:
        t = rx.sub(rep, t)
    if t != orig:
        html.write_text(t, encoding="utf-8", newline="\n")
        n += 1
        print("updated", html.name)
print("done", n)

