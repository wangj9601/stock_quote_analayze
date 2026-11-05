import openpyxl
for f in ["reports/csv/urt_7_20261102_130001.xlsx","reports/csv/urt_6_20261102_130051.xlsx"]:
    ws=openpyxl.load_workbook(f).active
    rows=list(ws.values); hdr=[str(c).strip() for c in rows[0]]
    print("="*40, f)
    for r in rows[1:6]:
        d={hdr[i]:r[i] for i in range(len(hdr))}
        print(d.get("股票名称"), "|得分",d.get("得分"),"|建议:",d.get("买点建议"),"|支撑",d.get("支撑"),"|阻力",d.get("阻力"),"|盈亏比",d.get("结构盈亏比"))
