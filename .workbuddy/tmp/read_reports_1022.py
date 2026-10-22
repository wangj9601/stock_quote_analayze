# -*- coding: utf-8 -*-
import openpyxl, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

for f in [r"reports/csv/urt_7_20261021_125949.xlsx", r"reports/csv/urt_6_20261021_130110.xlsx"]:
    wb = openpyxl.load_workbook(f, read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    header = rows[0]
    data = rows[1:]
    print("=" * 10, f, "rows:", len(data))
    # find column indexes
    idx = {h: i for i, h in enumerate(header)}
    score_col = None
    for cand in ("综合得分", "得分", "score", "总分"):
        if cand in idx:
            score_col = idx[cand]
            break
    code_col = idx.get("代码") or idx.get("股票代码") or idx.get("code")
    name_col = idx.get("名称") or idx.get("股票名称") or idx.get("name")
    buy_col = idx.get("买点") or idx.get("买入信号") or idx.get("buy_signal")
    print("header:", header)
    def sc(r):
        try: return float(r[score_col])
        except Exception: return -1
    data_sorted = sorted(data, key=sc, reverse=True)
    scores = [sc(r) for r in data_sorted if sc(r) >= 0]
    if scores:
        print("score min/max/avg: %.1f / %.1f / %.1f" % (min(scores), max(scores), sum(scores)/len(scores)))
    buy_cnt = 0
    if buy_col is not None:
        buys = [r for r in data if str(r[buy_col]).strip() in ("是", "True", "true", "1", "买入", "Y", "✓")]
        buy_cnt = len(buys)
    print("buy_points:", buy_cnt)
    print("Top 5:")
    for r in data_sorted[:5]:
        line = [str(r[c]) for c in (code_col, name_col, score_col) if c is not None]
        print("  ", " | ".join(line))
    wb.close()
