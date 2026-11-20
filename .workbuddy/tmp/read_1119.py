# -*- coding: utf-8 -*-
"""读取 2026-11-19 信号日两份 URT 报告明细"""
import glob
from openpyxl import load_workbook

for path in [r"E:\wangxw\股票分析软件\编码\stock_quote_analayze\reports\csv\urt_7_20261119_130823.xlsx",
             r"E:\wangxw\股票分析软件\编码\stock_quote_analayze\reports\csv\urt_6_20261119_130928.xlsx"]:
    wb = load_workbook(path, read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    header = [str(h).strip() if h is not None else "" for h in rows[0]]
    data = rows[1:]
    print("=" * 80)
    print(path.split("\\")[-1], "行数:", len(data))
    print("列名:", header)
    idx = {name: i for i, name in enumerate(header)}
    scores, bulls, vols, buys = [], [], [], 0
    from collections import Counter
    risks = Counter()
    for r in data:
        if r is None:
            continue
        code = str(r[idx["股票代码"]]).replace("\u2060", "").strip()
        name = str(r[idx.get("股票名称", idx["股票代码"])]).replace("\u2060", "").strip()
        score = r[idx["得分"]]
        buy = str(r[idx["是否买点"]]) if "是否买点" in idx else ""
        bull = str(r[idx["多头"]]) if "多头" in idx else ""
        risk = str(r[idx["风险"]]) if "风险" in idx and r[idx["风险"]] else ""
        vol = r[idx["量能倍数"]] if "量能倍数" in idx else None
        rr = r[idx["结构盈亏比"]] if "结构盈亏比" in idx else None
        if isinstance(score, (int, float)):
            scores.append(score)
        if "买" in str(buy) and "否" not in str(buy) and "是" in str(buy):
            buys += 1
        if bull in ("是", "True", "true", "1"):
            bulls.append(name)
        if vol is not None and isinstance(vol, (int, float)):
            vols.append(vol)
        for part in risk.replace("；", ";").split(";"):
            part = part.strip()
            if part:
                risks[part] += 1
    print("买点:", buys, "| 得分区间:", min(scores) if scores else "-", "-", max(scores) if scores else "-",
          "| 均值:", round(sum(scores) / len(scores), 1) if scores else "-")
    print("多头成立:", len(bulls), "/", len(data), ":", bulls[:8])
    print("量能倍数均值:", round(sum(vols) / len(vols), 2) if vols else "-")
    print("Top8:", [f"{str(r[idx['股票名称']]).replace(chr(0x2060),'').strip()}{round(r[idx['得分']],1)}" for r in data[:8] if r])
    print("风险主因:", risks.most_common(8))
