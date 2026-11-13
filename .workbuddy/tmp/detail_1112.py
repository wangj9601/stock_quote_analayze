# -*- coding: utf-8 -*-
"""解析 2026-11-11 URT 报告：汇总统计 + Top 明细 + 风险主因"""
import json
from collections import Counter
from openpyxl import load_workbook

CLEAN = lambda s: str(s).replace("\u2060", "").strip() if s is not None else ""

FILES = [
    ("user7", "reports/csv/urt_7_20261111_130714.xlsx"),
    ("user6", "reports/csv/urt_6_20261111_130759.xlsx"),
]

summary = {}
for tag, path in FILES:
    wb = load_workbook(path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    header = [CLEAN(c) for c in rows[0]]
    recs = [dict(zip(header, r)) for r in rows[1:] if any(v is not None for v in r)]
    print("=" * 70)
    print(tag, path, "列名:", header)
    print("总行数:", len(recs))

    def num(v):
        try:
            return float(v)
        except Exception:
            return None

    scores = [num(r.get("得分")) for r in recs]
    scores = [s for s in scores if s is not None]
    buys = [r for r in recs if CLEAN(r.get("是否买点")).upper() in ("是", "TRUE", "1", "Y")]
    bull = [r for r in recs if CLEAN(r.get("多头")).upper() in ("TRUE", "是", "1", "Y")]
    vols = [num(r.get("量能倍数")) for r in recs]
    vols = [v for v in vols if v is not None]

    print("买点数:", len(buys), "| 多头:", len(bull))
    if scores:
        print("得分 min/max/avg: %.1f / %.1f / %.1f" % (min(scores), max(scores), sum(scores) / len(scores)))
    if vols:
        print("量能倍数 avg: %.2f" % (sum(vols) / len(vols)))

    # Top 10
    ranked = sorted([r for r in recs if num(r.get("得分")) is not None], key=lambda r: -num(r.get("得分")))[:10]
    print("--- Top10 ---")
    for r in ranked:
        print("  ", CLEAN(r.get("股票代码")), CLEAN(r.get("股票名称")), "得分", CLEAN(r.get("得分")),
              "| 多头", CLEAN(r.get("多头")), "| 买点", CLEAN(r.get("是否买点")),
              "| RR", CLEAN(r.get("结构盈亏比")), "| 风险", CLEAN(r.get("风险"))[:60])

    # 风险主因统计
    reasons = Counter()
    for r in recs:
        txt = CLEAN(r.get("风险"))
        if txt:
            for part in txt.replace("；", ";").replace("，", ";").split(";"):
                p = part.strip()
                if p:
                    reasons[p] += 1
    print("--- 风险主因 Top8 ---")
    for k, v in reasons.most_common(8):
        print("  %-28s %d" % (k, v))

    summary[tag] = {
        "rows": len(recs),
        "buy_count": len(buys),
        "bull_count": len(bull),
        "score_min": min(scores) if scores else None,
        "score_max": max(scores) if scores else None,
        "score_avg": round(sum(scores) / len(scores), 1) if scores else None,
        "top10": [
            {"code": CLEAN(r.get("股票代码")), "name": CLEAN(r.get("股票名称")),
             "score": CLEAN(r.get("得分")), "bull": CLEAN(r.get("多头")), "buy": CLEAN(r.get("是否买点"))}
            for r in ranked
        ],
        "reasons": dict(reasons.most_common(8)),
    }

print("===SUMMARY_JSON===")
print(json.dumps(summary, ensure_ascii=False, indent=2))
