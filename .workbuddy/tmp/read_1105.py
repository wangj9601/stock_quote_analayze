# -*- coding: utf-8 -*-
"""读取最新 URT 报告明细 + 风险主因统计（通用版，参数为报告路径）。"""
import sys
import json
from collections import Counter
from openpyxl import load_workbook

CLEAN = lambda s: str(s).replace("\u2060", "").replace("\ufeff", "").strip() if s is not None else ""

for path in sys.argv[1:]:
    wb = load_workbook(path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    header = [CLEAN(c) for c in rows[0]]
    recs = [dict(zip(header, r)) for r in rows[1:] if r and r[0] is not None]

    scores = [float(r.get("得分")) for r in recs if r.get("得分") not in (None, "")]
    buys = [r for r in recs if str(r.get("是否买点", "")).strip() in ("是", "True", "1", "Y")]
    bull = [r for r in recs if str(r.get("多头成立", "")).strip() in ("是", "True", "1", "Y")]

    top = sorted(recs, key=lambda r: float(r.get("得分") or 0), reverse=True)[:8]

    risk = Counter()
    for r in recs:
        v = r.get("风险提示") or r.get("风险") or ""
        for part in str(v).replace("；", ";").replace("、", ";").split(";"):
            p = part.strip()
            if p:
                risk[p] += 1

    print("=" * 70)
    print("报告:", path)
    print("列名:", header)
    print(f"总行数={len(recs)} 买点={len(buys)} 多头成立={len(bull)}")
    if scores:
        print(f"得分 min={min(scores):.1f} max={max(scores):.1f} avg={sum(scores)/len(scores):.1f}")
    print("Top8:")
    for r in top:
        print("  ", {k: CLEAN(r.get(k)) for k in header if k in ("股票代码", "股票名称", "得分", "是否买点", "盈亏比", "风险提示")})
    print("风险主因 Top6:", risk.most_common(6))
