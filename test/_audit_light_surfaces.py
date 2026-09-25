# -*- coding: utf-8 -*-
"""Audit frontend CSS for light/white container backgrounds."""
from pathlib import Path
import re

css_dir = Path(__file__).resolve().parents[1] / "frontend" / "css"
# Skip already-dark ops layers
skip = {
    "ops-surfaces.css", "ops-shell.css", "ops-data.css", "ops-responsive.css",
    "design-tokens.css", "home-ops.css", "stock-ops.css", "analysis-ops.css",
    "watchlist-ops.css", "markets-ops.css", "news-ops.css", "screening-ops.css",
    "profile-ops.css", "board-ops.css", "workbench-ops.css", "tools-calculator.css",
}

light_bg = re.compile(
    r"background(?:-color)?\s*:\s*(?:#fff(?:fff)?|white|#f[0-9a-f]{5}|#e[89a-f][0-9a-f]{4}|rgba\(\s*255)",
    re.I,
)
# crude rule splitter
rule_re = re.compile(r"([^{}]+)\{([^{}]*)\}", re.S)

found = {}
for path in sorted(css_dir.glob("*.css")):
    if path.name in skip:
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    for m in rule_re.finditer(text):
        sel, body = m.group(1).strip(), m.group(2)
        if not light_bg.search(body):
            continue
        # keep simple class selectors
        for part in re.split(r",\s*", sel):
            part = part.strip()
            if part.startswith("@") or "keyframes" in part.lower():
                continue
            # extract last class in selector
            classes = re.findall(r"\.([a-zA-Z0-9_-]+)", part)
            if not classes:
                continue
            key = classes[-1]
            found.setdefault(key, set()).add(path.name)

# print high-value container-ish names
containerish = re.compile(
    r"(card|panel|section|box|wrap|container|block|item|row|table|workbench|modal|toolbar|header|grid|list|filter|tab|metric|summary|placeholder|content|board|chart|news|finance|fund|ssa|uto|ba-|lm-|ma-|dr-|rsa|recommend|tool|hot|stats|sector|stock|rank|history|trace|result)",
    re.I,
)
keys = sorted(k for k in found if containerish.search(k))
print(f"light-bg classes: {len(found)} total, {len(keys)} containerish")
for k in keys:
    print(f".{k}  <- {', '.join(sorted(found[k])[:3])}")
