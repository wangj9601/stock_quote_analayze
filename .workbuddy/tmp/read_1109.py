# -*- coding: utf-8 -*-
import re
from openpyxl import load_workbook

for f in [r"E:/wangxw/股票分析软件/编码/stock_quote_analayze/reports/csv/urt_7_20261109_130713.xlsx",
          r"E:/wangxw/股票分析软件/编码/stock_quote_analayze/reports/csv/urt_6_20261109_130802.xlsx"]:
    wb = load_workbook(f)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    header = rows[0]
    print("="*20, f.split("\\")[-1])
    print("列名:", header)
    data = rows[1:]
    print("行数:", len(data))
    idx = {h: i for i, h in enumerate(header)}
    def col(name):
        return idx.get(name)
    scores = []
    buy = 0
    bulls = 0
    items = []
    for r in data:
        code = str(r[col("股票代码")]).replace("\u2060", "").strip()
        name = str(r[col("股票名称")]).strip()
        sc = r[col("得分")]
        try: sc = float(sc)
        except: sc = None
        scores.append(sc)
        bp = r[col("是否买点")]
        if str(bp).strip() in ("是", "True", "true", "1"): buy += 1
        bcol = col("多头")
        if bcol is not None:
            bv = str(r[bcol]).strip()
            if bv in ("是", "True", "true", "1"): bulls += 1
        items.append((sc, code, name))
    items = [i for i in items if i[0] is not None]
    items.sort(reverse=True)
    ok = [s for s in scores if s is not None]
    print("得分区间: %.1f - %.1f, 均值 %.1f" % (min(ok), max(ok), sum(ok)/len(ok)))
    print("买点:", buy, "| 多头成立:", bulls, "/", len(data))
    print("Top5:", "; ".join("%s %s %.1f" % (c, n, s) for s, c, n in items[:5]))
    # 风险原因统计
    rcol = col("风险原因") or col("风险") or col("不买点原因")
    if rcol is not None:
        from collections import Counter
        cnt = Counter()
        for r in data:
            v = str(r[rcol] or "").strip()
            if v and v not in ("无", "None", ""):
                cnt[v] += 1
        print("风险原因 Top8:")
        for k, v in cnt.most_common(8):
            print("  ", k, v)
