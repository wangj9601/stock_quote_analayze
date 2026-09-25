# -*- coding: utf-8 -*-
"""Append ops-surfaces.css as last stylesheet on all ops-map pages."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1] / "frontend"
LINK = '<link rel="stylesheet" href="css/ops-surfaces.css?v=20260925g">'
SKIP = {
    "test_news.html",
    "animation-test.html",
    "clear_cache_instructions.html",
    "recommend.html",
    "triple_volume_observe.html",
    "index_new.html",
}

for path in sorted(ROOT.glob("*.html")):
    if path.name in SKIP:
        continue
    text = path.read_text(encoding="utf-8")
    if "ops-map" not in text and "design-tokens.css" not in text:
        continue
    if "ops-surfaces.css" in text:
        # bump version
        text2 = re.sub(
            r'href="css/ops-surfaces\.css[^"]*"',
            'href="css/ops-surfaces.css?v=20260925g"',
            text,
        )
        if text2 != text:
            path.write_text(text2, encoding="utf-8")
            print("bump", path.name)
        else:
            print("skip", path.name)
        continue
    if "</head>" not in text.lower():
        print("no head", path.name)
        continue
    # insert immediately before </head>
    text2 = re.sub(
        r"</head>",
        f"    {LINK}\n</head>",
        text,
        count=1,
        flags=re.I,
    )
    path.write_text(text2, encoding="utf-8")
    print("ok", path.name)
