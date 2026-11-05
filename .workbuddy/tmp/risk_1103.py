# -*- coding: utf-8 -*-
import openpyxl, collections
files = {"user7":"reports/csv/urt_7_20261102_130001.xlsx","user6":"reports/csv/urt_6_20261102_130051.xlsx"}
for k,f in files.items():
    ws = openpyxl.load_workbook(f).active
    rows=list(ws.values); hdr=[str(c).strip() for c in rows[0]]
    data=[{hdr[i]:r[i] for i in range(len(hdr))} for r in rows[1:]]
    print("="*60); print(k, "行数", len(data))
    cnt=collections.Counter()
    for d in data:
        v=d.get("风险")
        if v:
            for s in str(v).replace("；",";").replace("、",";").split(";"):
                s=s.strip()
                if s: cnt[s]+=1
    print("风险主因:", cnt.most_common(10))
    bull=sum(1 for d in data if str(d.get("多头")).strip() in ("1","True","是","Y","多头"))
    print("多头成立:", bull, "/", len(data))
    rr=[d.get("结构盈亏比") for d in data if isinstance(d.get("结构盈亏比"),(int,float))]
    if rr: print("结构盈亏比 min/avg/max: %.2f / %.2f / %.2f" % (min(rr), sum(rr)/len(rr), max(rr)))
    print("得分明细:")
    for d in sorted(data,key=lambda x: float(x.get("得分") or -1),reverse=True):
        print("   %s %s 得分%.1f 收盘%s MA20%s 多头%s 盈亏比%s 风险:%s" % (
            str(d.get("股票代码")).replace("\u2060","").strip(), d.get("股票名称"), float(d.get("得分") or 0),
            d.get("收盘"), d.get("MA20"), d.get("多头"), d.get("结构盈亏比"), d.get("风险")))
