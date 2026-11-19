# -*- coding: utf-8 -*-
from openpyxl import load_workbook
CLEAN = lambda s: str(s).replace("\u2060","").replace("\ufeff","").strip() if s is not None else ""
for path in ["reports/csv/urt_7_20261116_130529.xlsx","reports/csv/urt_6_20261116_130614.xlsx"]:
    wb=load_workbook(path,data_only=True); ws=wb.active
    rows=list(ws.iter_rows(values_only=True)); h=[CLEAN(c) for c in rows[0]]
    recs=[dict(zip(h,r)) for r in rows[1:] if r and r[0] is not None]
    print("="*60); print(path, "行数", len(recs))
    for r in sorted(recs,key=lambda x: float(x.get("得分") or 0),reverse=True):
        print(" %s %s 得分=%s 多头=%s 量能=%s 换手=%s RR=%s 风险=%s" % (
            CLEAN(r.get("股票代码")), CLEAN(r.get("股票名称")), CLEAN(r.get("得分")),
            CLEAN(r.get("多头")), CLEAN(r.get("量能倍数")), CLEAN(r.get("换手%")),
            CLEAN(r.get("结构盈亏比")), CLEAN(r.get("风险"))))
