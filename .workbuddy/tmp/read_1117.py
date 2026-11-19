# -*- coding: utf-8 -*-
"""读取 2026-11-17 两份 URT 报告明细：得分/买点/多头/量能/换手/风险主因"""
import re
from openpyxl import load_workbook

files = [
    r"E:\wangxw\股票分析软件\编码\stock_quote_analayze\reports\csv\urt_7_20261117_130905.xlsx",
    r"E:\wangxw\股票分析软件\编码\stock_quote_analayze\reports\csv\urt_6_20261117_131003.xlsx",
]
WJ = "\u2060"
for fp in files:
    wb = load_workbook(fp, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    header = [str(c).strip() if c else "" for c in rows[0]]
    idx = {h: i for i, h in enumerate(header)}
    data = rows[1:]
    print(f"\n=== {fp.split(chr(92))[-1]}  行数={len(data)} ===")
    print("列名:", header)
    scores, risks, bulls, vols, rrs, turns, codes_names = [], [], 0, [], [], [], []
    for r in data:
        def g(col):
            i = idx.get(col)
            return r[i] if i is not None and i < len(r) else None
        code = str(g("股票代码") or "").replace(WJ, "").strip()
        name = str(g("股票名称") or "").strip()
        s = g("得分")
        if s is not None:
            try: scores.append(float(s))
            except Exception: pass
        if str(g("是否买点") or "").strip() in ("是", "True", "true"): pass
        if str(g("多头") or "").strip() in ("是", "True", "true", "✓", "成立"): bulls += 1
        for vcol in ("量能倍数", "量能"):
            v = g(vcol)
            if v is not None:
                try: vols.append(float(v))
                except Exception: pass
                break
        rr = g("结构盈亏比")
        if rr is not None:
            try: rrs.append(float(rr))
            except Exception: pass
        tv = g("换手率")
        if tv is not None:
            try: turns.append(float(tv))
            except Exception: pass
        rk = str(g("风险") or "").strip()
        if rk: risks.append((code, name, rk))
        codes_names.append((code, name, s))
    if scores:
        print(f"得分 min={min(scores):.1f} max={max(scores):.1f} avg={sum(scores)/len(scores):.1f}")
    print(f"多头成立: {bulls}/{len(data)}")
    if vols: print(f"量能倍数 avg={sum(vols)/len(vols):.2f} max={max(vols):.2f}")
    if rrs: print(f"结构盈亏比 avg={sum(rrs)/len(rrs):.2f} max={max(rrs):.2f}")
    if turns: print(f"换手率 avg={sum(turns)/len(turns):.2f}")
    print("Top5 by 得分:")
    for c, n, s in sorted(codes_names, key=lambda x: -(float(x[2]) if x[2] is not None else -1))[:5]:
        print(f"  {c} {n} {s}")
    # 风险主因统计
    from collections import Counter
    cnt = Counter()
    for _, _, rk in risks:
        for item in re.split(r"[;；]", rk):
            item = item.strip()
            if item: cnt[item] += 1
    print("风险主因 Top:", cnt.most_common(8))
