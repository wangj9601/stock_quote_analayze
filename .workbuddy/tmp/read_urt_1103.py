# -*- coding: utf-8 -*-
import openpyxl, collections, json
files = {
 "user7":"reports/csv/urt_7_20261102_130001.xlsx",
 "user6":"reports/csv/urt_6_20261102_130051.xlsx",
}
for k,f in files.items():
    wb = openpyxl.load_workbook(f)
    ws = wb.active
    rows = list(ws.values)
    hdr = [str(c).strip() for c in rows[0]]
    print("="*70)
    print(k, f, "行数(含表头)", len(rows)-1, "列:", hdr)
    data = []
    for r in rows[1:]:
        d = {hdr[i]: r[i] for i in range(len(hdr))}
        data.append(d)
    # 编码清洗
    def clean(v):
        return str(v).replace("\u2060","").strip() if v is not None else ""
    for d in data:
        d["code"] = clean(d.get("股票代码"))
        d["name"] = clean(d.get("股票名称"))
        d["score"] = d.get("得分")
        d["buy"] = d.get("是否买点")
    scores = [float(d["score"]) for d in data if d["score"] not in (None,"")]
    print("得分范围: %.1f - %.1f  均值 %.1f" % (min(scores), max(scores), sum(scores)/len(scores)))
    buys = [d for d in data if str(d["buy"]) in ("1","True","是","Y")]
    print("买点数:", len(buys))
    print("Top5:")
    for d in sorted(data, key=lambda x: float(x["score"] or -1), reverse=True)[:5]:
        print("   ", d["code"], d["name"], d["score"], "买点:", d["buy"])
    # 风险原因
    cnt = collections.Counter()
    for d in data:
        for key in ("不买原因","风险提示","原因","否决原因"):
            if key in d and d[key]:
                for s in str(d[key]).replace("；",";").split(";"):
                    s=s.strip()
                    if s: cnt[s]+=1
                break
    print("风险主因 Top8:", cnt.most_common(8))
