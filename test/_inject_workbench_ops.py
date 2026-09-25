# -*- coding: utf-8 -*-
"""Inject workbench-ops.css into ops-map secondary pages."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "frontend"
LINK = '    <link rel="stylesheet" href="css/workbench-ops.css">\n'
TARGETS = [
    "stock_gms_trace.html",
    "stock_rpe_trace.html",
    "stock_rs_trace.html",
    "stock_urt_trace.html",
    "stock_urt_score_detail.html",
    "stock_sbbr_trace.html",
    "stock_csb_trace.html",
    "stock_vsb_trace.html",
    "stock_history.html",
    "indicator_data.html",
    "indicator_details.html",
]

for name in TARGETS:
    path = ROOT / name
    text = path.read_text(encoding="utf-8")
    if "workbench-ops.css" in text:
        print("skip", name)
        continue
    needle = 'href="css/ops-responsive.css">'
    if needle not in text:
        print("MISS responsive", name)
        continue
    text = text.replace(
        needle,
        needle + "\n" + LINK.rstrip() + "\n",
        1,
    )
    # normalize messy indentation on design-tokens line
    text = text.replace(
        "        <link rel=\"stylesheet\" href=\"css/design-tokens.css\">",
        "    <link rel=\"stylesheet\" href=\"css/design-tokens.css\">",
    )
    text = text.replace(
        "<link rel=\"stylesheet\" href=\"css/stock.css\">",
        "    <link rel=\"stylesheet\" href=\"css/stock.css\">",
    )
    text = text.replace(
        "<link rel=\"stylesheet\" href=\"css/screening.css\">",
        "    <link rel=\"stylesheet\" href=\"css/screening.css\">",
    )
    path.write_text(text, encoding="utf-8")
    print("ok", name)
