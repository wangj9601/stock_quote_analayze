# -*- coding: utf-8 -*-
"""读取 2026-11-04 URT 报告明细：Top 得分、买点、风险主因、多头成立统计。"""
from openpyxl import load_workbook

FILES = {
    "user7": r"E:\wangxw\股票分析软件\编码\stock_quote_analayze\reports\csv\urt_7_20261104_090711.xlsx",
    "user6": r"E:\wangxw\股票分析软件\编码\stock_quote_analayze\reports\csv\urt_6_20261104_090807.xlsx",
}

import json
for tag, path in FILES.items():
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    header = [str(h).strip() if h else "" for h in rows[0]]
    data = []
    for r in rows[1:]:
        if r[0] is None:
            continue
        d = dict(zip(header, r))
        code = str(d.get("股票代码", "")).replace("\u2060", "").strip()
        d["股票代码"] = code
        data.append(d)
    wb.close()

    score_key = "得分"
    buy_key = next((k for k in header if "买点" in k), "是否买点")
    risk_key = next((k for k in header if "风险" in k or "否决" in k), None)
    bull_key = next((k for k in header if "多头" in k), None)

    scores = [float(d[score_key]) for d in data if d.get(score_key) is not None]
    top = sorted(data, key=lambda d: float(d.get(score_key) or 0), reverse=True)[:8]
    buys = [d for d in data if str(d.get(buy_key, "")).strip() in ("是", "True", "1", "Y", "true")]

    print(f"===== {tag} | 行数={len(data)} | 买点={len(buys)} | 得分 {min(scores):.1f}~{max(scores):.1f} 均值 {sum(scores)/len(scores):.1f}")
    for t in top:
        line = f"  {t['股票代码']} {t.get('股票名称','')} 得分={t.get(score_key)}"
        if risk_key and t.get(risk_key):
            line += f" | {risk_key}={t[risk_key]}"
        if bull_key:
            line += f" | {bull_key}={t.get(bull_key)}"
        print(line)

    # 风险主因统计
    if risk_key:
        from collections import Counter
        c = Counter()
        for d in data:
            v = str(d.get(risk_key) or "").strip()
            if v and v not in ("无", "None", "-"):
                for item in v.replace("；", ";").split(";"):
                    item = item.strip()
                    if item and item not in ("无",):
                        c[item] += 1
        print("  风险主因:", c.most_common(6))
    if bull_key:
        bulls = sum(1 for d in data if str(d.get(bull_key, "")).strip() in ("是", "True", "1", "true", "Y"))
        print(f"  多头成立: {bulls}/{len(data)}")
