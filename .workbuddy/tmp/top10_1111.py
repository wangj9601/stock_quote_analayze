from openpyxl import load_workbook
CLEAN=lambda s: str(s).replace("\u2060","").strip() if s is not None else ""
for path in ("reports/csv/urt_7_20261110_131039.xlsx","reports/csv/urt_6_20261110_131148.xlsx"):
    wb=load_workbook(path,data_only=True); ws=wb.active
    rows=list(ws.iter_rows(values_only=True)); header=[CLEAN(c) for c in rows[0]]
    recs=[dict(zip(header,r)) for r in rows[1:] if r and r[0] is not None]
    recs.sort(key=lambda r: float(r.get("得分") or 0), reverse=True)
    print("###", path.split("\\")[-1])
    for r in recs[:10]:
        print("|", CLEAN(r["股票代码"]), "|", CLEAN(r["股票名称"]), "|", CLEAN(r["收盘"]), "|", CLEAN(r["得分"]),
              "|", CLEAN(r["量能倍数"]), "|", CLEAN(r["结构盈亏比"]), "|", CLEAN(r["多头"]), "|", CLEAN(r["风险"]), "|")
