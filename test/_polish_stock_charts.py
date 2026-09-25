# -*- coding: utf-8 -*-
"""Polish stock.js chart theme to ops-map dark + A-share ink."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / "frontend" / "js" / "stock.js"
t = path.read_text(encoding="utf-8")
orig = t

# Chart canvas / tooltip light → dark (ops-map)
replacements = [
    ("backgroundColor: '#ffffff'", "backgroundColor: '#161c24'"),
    ("backgroundColor: 'rgba(245, 245, 245, 0.9)'", "backgroundColor: 'rgba(22, 28, 36, 0.96)'"),
    ("backgroundColor: 'rgba(255, 255, 255, 0.9)'", "backgroundColor: 'rgba(22, 28, 36, 0.96)'"),
    ("borderColor: '#ccc'", "borderColor: 'rgba(217, 226, 236, 0.22)'"),
    ("textStyle: { color: '#000' }", "textStyle: { color: '#d9e2ec' }"),
    ("textStyle: {\n                    color: '#333'\n                }", "textStyle: {\n                    color: '#d9e2ec'\n                }"),
    # A-share ink on candles / volume
    ("color: '#dc2626'", "color: '#c23b3b'"),
    ("color0: '#16a34a'", "color0: '#2f9e6b'"),
    ("borderColor: '#dc2626'", "borderColor: '#c23b3b'"),
    ("borderColor0: '#16a34a'", "borderColor0: '#2f9e6b'"),
    ("return params.value >= 0 ? '#dc2626' : '#16a34a'", "return params.value >= 0 ? '#c23b3b' : '#2f9e6b'"),
    ("color: close >= open ? '#dc2626' : '#16a34a'", "color: close >= open ? '#c23b3b' : '#2f9e6b'"),
    ("itemStyle: { color: '#dc2626' }", "itemStyle: { color: '#c23b3b' }"),
    ("itemStyle: { color: '#16a34a' }", "itemStyle: { color: '#2f9e6b' }"),
    # Axis muted ink
    ("color: '#999'", "color: '#8b9aab'"),
]

for old, new in replacements:
    n = t.count(old)
    if n:
        t = t.replace(old, new)
        print(f"OK x{n}: {old[:48]}")
    else:
        print(f"skip: {old[:48]}")

# splitArea light bands → dark
old_split = "{ scale: true, splitArea: { show: true } }"
new_split = (
    "{ scale: true, splitArea: { show: true, areaStyle: "
    "{ color: ['rgba(217,226,236,0.02)', 'rgba(217,226,236,0.045)'] } }, "
    "axisLabel: { color: '#8b9aab' }, "
    "axisLine: { lineStyle: { color: 'rgba(217,226,236,0.18)' } }, "
    "splitLine: { lineStyle: { color: 'rgba(217,226,236,0.08)' } } }"
)
if old_split in t:
    t = t.replace(old_split, new_split)
    print("OK splitArea dark")
else:
    print("skip splitArea")

# minute yAxis splitArea
old_my = "splitArea: { show: true }\n            }"
new_my = (
    "splitArea: { show: true, areaStyle: { color: ['rgba(217,226,236,0.02)', 'rgba(217,226,236,0.045)'] } },\n"
    "                axisLabel: { color: '#8b9aab' },\n"
    "                axisLine: { lineStyle: { color: 'rgba(217,226,236,0.18)' } },\n"
    "                splitLine: { lineStyle: { color: 'rgba(217,226,236,0.08)' } }\n"
    "            }"
)
if old_my in t:
    # only first occurrence in minute chart ideally - replace carefully
    t = t.replace(old_my, new_my, 1)
    print("OK minute splitArea")
else:
    print("skip minute splitArea")

# minute line accent → route blue already #2563eb → #2f6fed
t2 = t.replace("color: '#2563eb'", "color: '#2f6fed'")
t2 = t2.replace("rgba(37, 99, 235,", "rgba(47, 111, 237,")
if t2 != t:
    print("OK route blue accents")
    t = t2

if t == orig:
    print("NO CHANGES")
else:
    path.write_text(t, encoding="utf-8")
    print("wrote", path, "delta", len(t) - len(orig))

# Mirror critical bg in stock_hk.js
hk = root / "frontend" / "js" / "stock_hk.js"
if hk.exists():
    ht = hk.read_text(encoding="utf-8")
    ho = ht
    for old, new in [
        ("backgroundColor: '#ffffff'", "backgroundColor: '#161c24'"),
        ("backgroundColor: 'rgba(245, 245, 245, 0.9)'", "backgroundColor: 'rgba(22, 28, 36, 0.96)'"),
        ("backgroundColor: 'rgba(255, 255, 255, 0.9)'", "backgroundColor: 'rgba(22, 28, 36, 0.96)'"),
        ("textStyle: { color: '#000' }", "textStyle: { color: '#d9e2ec' }"),
        ("borderColor: '#ccc'", "borderColor: 'rgba(217, 226, 236, 0.22)'"),
        ("color: '#dc2626'", "color: '#c23b3b'"),
        ("color0: '#16a34a'", "color0: '#2f9e6b'"),
        ("borderColor: '#dc2626'", "borderColor: '#c23b3b'"),
        ("borderColor0: '#16a34a'", "borderColor0: '#2f9e6b'"),
    ]:
        if old in ht:
            ht = ht.replace(old, new)
    if ht != ho:
        hk.write_text(ht, encoding="utf-8")
        print("wrote stock_hk.js")
    else:
        print("stock_hk unchanged")
