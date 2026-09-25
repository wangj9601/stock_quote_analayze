# -*- coding: utf-8 -*-
from pathlib import Path

root = Path(__file__).resolve().parents[1]
js = root / "frontend" / "js" / "markets.js"
t = js.read_text(encoding="utf-8")

old1 = (
    'tbody.innerHTML = `<tr><td colspan="11" style="text-align:center;color:#888;">'
    "暂无同花顺${ui.label}数据</td></tr>`;"
)
new1 = (
    'tbody.innerHTML = `<tr><td colspan="11" class="ops-empty-cell">'
    "暂无同花顺${ui.label}数据</td></tr>`;"
)
old2 = (
    'grid.innerHTML = `<div class="empty-tip" style="text-align:center;padding:2em;color:#888;">'
    "暂无同花顺${ui.label}数据</div>`;"
)
new2 = (
    'grid.innerHTML = `<div class="empty-tip ops-empty-tip">'
    "暂无同花顺${ui.label}数据</div>`;"
)

for old, new, name in ((old1, new1, "list"), (old2, new2, "grid")):
    if old not in t:
        print("MISS", name)
    else:
        t = t.replace(old, new)
        print("OK", name)

js.write_text(t, encoding="utf-8")

html = root / "frontend" / "markets.html"
ht = html.read_text(encoding="utf-8")
for old in (
    "markets-ops.css?v=20260925polish2",
    "markets-ops.css?v=20260925polish",
    'href="css/markets-ops.css"',
):
    if old in ht:
        if old.startswith("href"):
            ht = ht.replace(old, 'href="css/markets-ops.css?v=20260925sectors"')
        else:
            ht = ht.replace(old, "markets-ops.css?v=20260925sectors")
        print("bumped", old)
        break
html.write_text(ht, encoding="utf-8")
print("done", "sectors" in html.read_text(encoding="utf-8"))
