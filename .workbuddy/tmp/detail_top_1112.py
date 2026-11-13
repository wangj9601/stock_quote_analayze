# -*- coding: utf-8 -*-
from pathlib import Path
from openpyxl import load_workbook

C = lambda s: str(s).replace("\u2060", "").strip() if s is not None else ""
KEYS = ("三花智控", "云煤能源", "光线传媒")
for p in ["reports/csv/urt_7_20261111_130714.xlsx", "reports/csv/urt_6_20261111_130759.xlsx"]:
    wb = load_workbook(p, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    h = [C(c) for c in rows[0]]
    for r in rows[1:]:
        d = dict(zip(h, r))
        if C(d.get("股票名称")) in KEYS:
            print(Path(p).name, "|", C(d.get("股票名称")),
                  "| 收盘", C(d.get("收盘")), "| MA20", C(d.get("MA20")),
                  "| 阳线4/5/10/15/20", C(d.get("4日阳")), C(d.get("5日阳")), C(d.get("10日阳")),
                  C(d.get("15日阳")), C(d.get("20日阳")),
                  "| 多头", C(d.get("多头")), "| 量能", C(d.get("量能倍数")),
                  "| RR", C(d.get("结构盈亏比")), "| 得分", C(d.get("得分")),
                  "| 风险", C(d.get("风险")), "| 建议", C(d.get("买点建议")))
    print("-" * 50)
