# -*- coding: utf-8 -*-
"""分析 CSB 回测 2bd159df CSV + PDF（按列位置，避开控制台编码）。"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pymupdf

# 与 backtest_storage CSV 中文表头顺序对齐（导出后可能含额外因子列）
COL = {
    "code": 0,
    "name": 1,
    "signal_date": 2,
    "signal_type": 3,
    "score": 4,
    "entry_date": 5,
    "entry_price": 6,
    "max_high": 7,
    "max_gain_pct": 8,
    "hit_target": 9,
    "hit_date": 10,
    "exit_date": 11,
    "exit_price": 12,
    "exit_reason": 13,
    "pnl_pct": 14,
    "bars_held": 15,
    "touch_count": 19,
}

DL = Path(r"C:\Users\Administrator\Downloads")
csv_path = list(DL.glob("*2bd159df*.csv"))[0]
pdf_path = list(DL.glob("*2bd159df*.pdf"))[0]

# 尝试多种编码
df = None
for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
    try:
        df = pd.read_csv(csv_path, encoding=enc)
        # 校验：信号类型列应含 CSB_
        st = df.iloc[:, COL["signal_type"]].astype(str)
        if st.str.contains("CSB_").any():
            print("encoding", enc, "rows", len(df))
            break
    except Exception as e:
        print("fail", enc, e)
        df = None
assert df is not None

out_lines = []


def log(msg: str) -> None:
    print(msg)
    out_lines.append(msg)


log(f"rows={len(df)} file={csv_path.name}")

sig = df.iloc[:, COL["signal_type"]].astype(str)
exit_r = df.iloc[:, COL["exit_reason"]].astype(str)
pnl = pd.to_numeric(df.iloc[:, COL["pnl_pct"]], errors="coerce")
score = pd.to_numeric(df.iloc[:, COL["score"]], errors="coerce")
mg = pd.to_numeric(df.iloc[:, COL["max_gain_pct"]], errors="coerce")
touch = pd.to_numeric(df.iloc[:, COL["touch_count"]], errors="coerce")
held = pd.to_numeric(df.iloc[:, COL["bars_held"]], errors="coerce")
hit_raw = df.iloc[:, COL["hit_target"]].astype(str)
# 是/否 or True/False
hit = hit_raw.isin(["是", "True", "true", "1", "Y", "y"])
# also use hit_target_lower if present
if "hit_target_lower" in df.columns:
    hit = df["hit_target_lower"].astype(bool)

log("\n== signal_type ==")
log(sig.value_counts().to_string())

log("\n== exit_reason ==")
log(exit_r.value_counts().to_string())

log(
    "\n== overall =="
    f"\nn={len(df)}"
    f"\nhit_rate={100*float(hit.mean()):.2f}%"
    f"\nwin_rate={100*float((pnl>0).mean()):.2f}%"
    f"\navg_pnl={float(pnl.mean()):.2f}%"
    f"\nmedian_pnl={float(pnl.median()):.2f}%"
    f"\navg_max_gain={float(mg.mean()):.2f}%"
    f"\navg_score={float(score.mean()):.2f}"
    f"\nmin_score={float(score.min()):.2f}"
    f"\navg_touch={float(touch.mean()):.2f}"
    f"\navg_bars_held={float(held.mean()):.2f}"
)

log("\n== exit_reason detail ==")
for name, idx in exit_r.groupby(exit_r).groups.items():
    part_pnl = pnl.loc[idx]
    part_hit = hit.loc[idx]
    log(
        f"{name}\tn={len(idx)}\tpct={100*len(idx)/len(df):.1f}%"
        f"\tavg_pnl={float(part_pnl.mean()):.2f}%"
        f"\twin={100*float((part_pnl>0).mean()):.1f}%"
        f"\thit={100*float(part_hit.mean()):.1f}%"
    )

# monthly
sd = pd.to_datetime(df.iloc[:, COL["signal_date"]], errors="coerce")
log("\n== monthly signals ==")
log(sd.dt.to_period("M").value_counts().sort_index().to_string())

# channel_fail share vs d8595daa expectation
cf_mask = exit_r.str.contains("通道|channel", case=False, na=False)
bl_mask = exit_r.str.contains("基准|baseline|止损", case=False, na=False)
log(
    f"\n== exit focus =="
    f"\nchannel_fail_like={int(cf_mask.sum())} ({100*cf_mask.mean():.1f}%)"
    f"\nbaseline_like={int(bl_mask.sum())} ({100*bl_mask.mean():.1f}%)"
)

# PDF
doc = pymupdf.open(pdf_path)
text = "\n".join(p.get_text("text") for p in doc)
compact = [
    ln.strip()
    for ln in text.splitlines()
    if ln.strip() and re.search(r"[A-Za-z0-9%~+\-×x./]", ln)
]
log("\n== PDF ==")
log("\n".join(compact[:40]))

# vs previous reports
log(
    "\n== vs prior =="
    "\nd8595daa: n=127 hit~26.8% (PROBE优化旧通道失效0.5%x2)"
    "\n066d24af/4b71bb67: n=0 (仅BREAKOUT/LPS)"
    f"\n2bd159df: n={len(df)} hit={100*float(hit.mean()):.2f}% (PROBE优化+通道失效默认已放宽到1.5%x3)"
)

Path("exported_docs").mkdir(exist_ok=True)
Path("exported_docs/CSB_2bd159df_analysis.txt").write_text("\n".join(out_lines), encoding="utf-8")
print("WROTE exported_docs/CSB_2bd159df_analysis.txt")
