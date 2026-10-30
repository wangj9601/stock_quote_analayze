# -*- coding: utf-8 -*-
import json
from pathlib import Path
from collections import Counter
import openpyxl
root=Path(r"E:/wangxw/股票分析软件/编码/stock_quote_analayze")
res=json.loads((root/".workbuddy/tmp/push_urt_daily_result.json").read_text(encoding="utf-8"))
clean=lambda s: str(s).replace("\u2060","").strip()
for t in res["targets"]:
    p=root/t["report_file_path"]
    wb=openpyxl.load_workbook(p); ws=wb.active
    rows=list(ws.iter_rows(values_only=True)); hdr=rows[0]
    idx={h:i for i,h in enumerate(hdr)}
    data=[r for r in rows[1:] if r and r[0]]
    print("="*60); print(f"config={t['config_id']} user={t['user_id']} 行数={len(data)}")
    cnt=Counter()
    for r in data:
        for part in str(r[idx['风险']]).replace("；",";").split(";"):
            part=part.strip()
            if part: cnt[part]+=1
    for k,v in cnt.most_common(8): print(f"   {k}: {v}")
    # 多头/量能统计
    duotou=sum(1 for r in data if str(r[idx['多头']]) in ('是','True','1'))
    print("   多头成立:", duotou, "/", len(data))
    vols=[r[idx['量能倍数']] for r in data if isinstance(r[idx['量能倍数']],(int,float))]
    if vols: print(f"   量能倍数 avg={sum(vols)/len(vols):.2f}")
