# -*- coding: utf-8 -*-
import os
import re

root = os.path.join(os.path.dirname(__file__), "..", "frontend")
root = os.path.abspath(root)
skip = {"test_news.html", "clear_cache_instructions.html", "animation-test.html"}
checks = [
    "design-tokens.css",
    "ops-shell.css",
    "ops-data.css",
    "ops-responsive.css",
]

for fn in sorted(os.listdir(root)):
    if not fn.endswith(".html") or fn in skip:
        continue
    path = os.path.join(root, fn)
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    has = [c for c in checks if c in text]
    miss = [c for c in checks if c not in text]
    ops_map = "ops-map" in text
    channel_ops = bool(re.search(r"css/[a-z0-9_-]+-ops\.css", text))
    m = re.search(r"<body[^>]*>", text, re.I)
    body = (m.group(0) if m else "?")[:120]
    print(fn)
    print("  has:", ",".join(has) or "-")
    print("  miss:", ",".join(miss) or "-")
    print("  ops-map:", ops_map, "channel-ops:", channel_ops)
    print(" ", body)
    print()
