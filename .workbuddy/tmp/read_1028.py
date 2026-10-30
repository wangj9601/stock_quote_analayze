# -*- coding: utf-8 -*-
import json, os
from pathlib import Path
import openpyxl
root=Path(r"E:/wangxw/股票分析软件/编码/stock_quote_analayze")
res=json.loads((root/".workbuddy/tmp/push_urt_daily_result.json").read_text(encoding="utf-8"))
for t in res["targets"]:
    p=root/t.get("report_file_path","")
    print("="*70)
    print(f"config={t['config_id']} user={t['user_id']}/{t['username']} record={t['record_id']} status={t['record_status']} ch={t['channel_status']}")
    print("file:", p, "exists:", p.exists())
    if not p.exists(): continue
    wb=openpyxl.load_workbook(p); ws=wb.active
    rows=list(ws.iter_rows(values_only=True))
    hdr=rows[0]; print("列名:", hdr)
    data=[r for r in rows[1:] if r and r[0]]
    print("行数:", len(data))
    idx={h:i for i,h in enumerate(hdr)}
    def g(r,key):
        for k in idx:
            if k and key in str(k): return r[idx[k]]
        return None
    scores=[g(r,"得分") for r in data]
    scores=[s for s in scores if isinstance(s,(int,float))]
    if scores: print(f"得分 min={min(scores):.1f} max={max(scores):.1f} avg={sum(scores)/len(scores):.1f}")
    buys=[r for r in data if str(g(r,"买点")).strip() in ("是","True","1","Y")]
    print("买点数:", len(buys))
    # top5
    srt=sorted(data, key=lambda r: (g(r,"得分") or 0), reverse=True)[:5]
    print("Top5:")
    for r in srt:
        print("   ", g(r,"代码") or r[0], g(r,"名称"), "得分",g(r,"得分"), "信号日",g(r,"信号日"))
    if buys:
        print("买点明细:")
        for r in buys: print("   ", r)
    print("全部代码:", [ (g(r,'代码') or r[0]) for r in data])
