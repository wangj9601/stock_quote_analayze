from openpyxl import load_workbook
CLEAN = lambda s: str(s).replace("\u2060","").strip() if s is not None else ""
for path, names in (("reports/csv/urt_6_20261110_131148.xlsx", ["领益智造","云煤能源","京投发展"]),
                    ("reports/csv/urt_7_20261110_131039.xlsx", ["光线传媒","五洲新春","三花智控"])):
    wb = load_workbook(path, data_only=True); ws = wb.active
    rows = list(ws.iter_rows(values_only=True)); header=[CLEAN(c) for c in rows[0]]
    for r in rows[1:]:
        d = dict(zip(header, r))
        if CLEAN(d.get("股票名称")) in names:
            print(path.split("\\")[-1], "|", {k: CLEAN(v) for k,v in d.items()})
    print("-"*60)
