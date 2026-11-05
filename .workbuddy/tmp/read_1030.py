# -*- coding: utf-8 -*-
"""读取 2026-10-30 两份 URT 报告，输出行数/买点/得分/Top/风险主因统计。"""
import glob
import os
import re
from collections import Counter
from openpyxl import load_workbook

ROOT = r"E:\wangxw\股票分析软件\编码\stock_quote_analayze"

for path in sorted(glob.glob(os.path.join(ROOT, "reports", "csv", "urt_*_20261030_*.xlsx"))):
    wb = load_workbook(path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    header = [str(h) if h is not None else "" for h in rows[0]]
    data = [dict(zip(header, r)) for r in rows[1:] if any(v is not None for v in r)]

    col_code = next((c for c in header if "代码" in c), header[0])
    col_name = next((c for c in header if "名称" in c), header[1])
    col_score = next((c for c in header if "得分" in c), None)
    col_buy = next((c for c in header if "买点" in c or "是否" in c), None)
    col_risk = next((c for c in header if "风险" in c or "原因" in c or "否决" in c), None)

    def clean(v):
        return str(v).replace("\u2060", "").strip() if v is not None else ""

    scores = [float(d[col_score]) for d in data if d.get(col_score) is not None]
    buys = [d for d in data if col_buy and str(d.get(col_buy)).strip() in ("是", "True", "1", "Y", "是（买点）")]
    risks = Counter()
    if col_risk:
        for d in data:
            r = clean(d.get(col_risk))
            if r and r not in ("无", "-"):
                risks[r] += 1

    print("=" * 60)
    print("文件:", os.path.basename(path))
    print("行数:", len(data), "| 买点:", len(buys),
          "| 得分: %.1f ~ %.1f, 均值 %.1f" % (min(scores), max(scores), sum(scores) / len(scores)) if scores else "无得分")
    ranked = sorted(data, key=lambda d: d.get(col_score) or 0, reverse=True)
    for d in ranked[:5]:
        print("  Top: %s %s 得分 %s 买点 %s" % (
            clean(d.get(col_code)), clean(d.get(col_name)), d.get(col_score), d.get(col_buy)))
    if buys:
        print("  -- 买点明细 --")
        for d in buys:
            print("  BUY: %s %s 得分 %s" % (clean(d.get(col_code)), clean(d.get(col_name)), d.get(col_score)))
    if risks:
        print("  风险主因 Top5:", risks.most_common(5))
