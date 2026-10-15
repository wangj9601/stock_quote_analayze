# -*- coding: utf-8 -*-
"""分析 CSB 回测 4ca39a24（预期 v5），对照 e7b3cbe0。"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pymupdf

DL = Path(r"C:\Users\Administrator\Downloads")
RENAME = {
    "信号日期": "signal_date",
    "信号类型": "signal_type",
    "得分": "score",
    "出场原因": "exit_reason",
    "盈亏比例(%)": "pnl_pct",
    "持有天数": "bars_held",
    "粘合天数": "squeeze_days",
    "粘合带宽": "squeeze_pct",
    "回踩次数": "touch_count",
    "5/20量比": "vol_ratio_5_20",
    "放量倍数": "vol_expand_mult",
    "通道上轨": "channel_upper",
    "通道下轨": "channel_lower",
    "入场价": "entry_price",
    "观察期最大涨幅(%)": "max_gain_pct",
    "基准低点": "entry_low",
}


def load(tid: str) -> pd.DataFrame:
    path = list(DL.glob(f"*{tid}*.csv"))[0]
    df = pd.read_csv(path, encoding="utf-8-sig")
    df = df.rename(columns={k: v for k, v in RENAME.items() if k in df.columns})
    if "exit_reason" not in df.columns:
        pos = {
            "signal_date": 2,
            "signal_type": 3,
            "score": 4,
            "entry_price": 6,
            "max_gain_pct": 8,
            "exit_reason": 13,
            "pnl_pct": 14,
            "bars_held": 15,
            "squeeze_days": 17,
            "squeeze_pct": 18,
            "touch_count": 19,
            "vol_expand_mult": 20,
            "vol_ratio_5_20": 21,
            "channel_upper": 22,
            "channel_lower": 23,
            "entry_low": 24,
        }
        for k, i in pos.items():
            df[k] = df.iloc[:, i]
    for c in (
        "score",
        "pnl_pct",
        "bars_held",
        "touch_count",
        "squeeze_days",
        "squeeze_pct",
        "channel_upper",
        "channel_lower",
        "entry_price",
        "max_gain_pct",
        "entry_low",
        "vol_ratio_5_20",
        "vol_expand_mult",
    ):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "hit_target_lower" in df.columns:
        df["hit"] = df["hit_target_lower"].astype(bool)
    else:
        df["hit"] = False
    width = df["channel_upper"] - df["channel_lower"]
    df["channel_width_pct"] = (width / df["entry_price"].replace(0, np.nan)) * 100.0
    reason = df["exit_reason"].astype(str)

    def cohort(r: str) -> str:
        if "通道" in r:
            return "channel_fail"
        if "基准" in r:
            return "baseline_stop"
        if "到期" in r:
            return "horizon_end"
        if "派发" in r:
            return "distribution"
        if "阶梯" in r or "跟踪" in r:
            return "ma_trail"
        return r

    df["exit"] = reason.map(cohort)
    df["BAD"] = df["exit"].isin(["channel_fail", "baseline_stop"])
    return df


def summarize(tid: str, df: pd.DataFrame) -> list[str]:
    lines = [f"=== {tid} n={len(df)} ==="]
    lines.append(f"sig: {df['signal_type'].astype(str).value_counts().to_dict()}")
    lines.append(
        f"hit={100*df['hit'].mean():.2f}% win={100*(df['pnl_pct']>0).mean():.2f}% "
        f"avg_pnl={df['pnl_pct'].mean():.2f}% med={df['pnl_pct'].median():.2f}% "
        f"avg_max_gain={df['max_gain_pct'].mean():.2f}%"
    )
    lines.append(
        f"score min/mean={df['score'].min():.2f}/{df['score'].mean():.2f} "
        f"touch min/max/mean={df['touch_count'].min():.0f}/{df['touch_count'].max():.0f}/{df['touch_count'].mean():.2f} "
        f"width% min/mean={df['channel_width_pct'].min():.2f}/{df['channel_width_pct'].mean():.2f} "
        f"width<2% n={(df['channel_width_pct']<2).sum()}"
    )
    lines.append(f"BAD%={100*df['BAD'].mean():.1f}% held={df['bars_held'].mean():.2f}")
    lines.append("exit:")
    for name, part in df.groupby("exit"):
        lines.append(
            f"  {name}: n={len(part)} ({100*len(part)/len(df):.1f}%) "
            f"avg_pnl={part['pnl_pct'].mean():.2f}% win={100*(part['pnl_pct']>0).mean():.1f}% "
            f"hit={100*part['hit'].mean():.1f}%"
        )
    sd = pd.to_datetime(df["signal_date"], errors="coerce")
    lines.append("monthly: " + str({str(k): int(v) for k, v in sd.dt.to_period("M").value_counts().sort_index().items()}))
    return lines


def pdf_lines(tid: str) -> str:
    path = list(DL.glob(f"*{tid}*.pdf"))[0]
    doc = pymupdf.open(path)
    text = "\n".join(p.get_text("text") for p in doc)
    return "\n".join(
        ln.strip()
        for ln in text.splitlines()
        if ln.strip() and re.search(r"[A-Za-z0-9%~+\-×x./]", ln)
    )


lines: list[str] = []
new = load("4ca39a24")
old = load("e7b3cbe0")
lines.extend(summarize("4ca39a24", new))
lines.append("\n=== PDF ===")
lines.append(pdf_lines("4ca39a24"))
lines.append("\n=== vs e7b3cbe0 ===")
lines.append(
    f"n {len(old)}->{len(new)}\n"
    f"hit {100*old['hit'].mean():.2f}%->{100*new['hit'].mean():.2f}%\n"
    f"win {100*(old['pnl_pct']>0).mean():.2f}%->{100*(new['pnl_pct']>0).mean():.2f}%\n"
    f"avg_pnl {old['pnl_pct'].mean():.2f}%->{new['pnl_pct'].mean():.2f}%\n"
    f"BAD% {100*old['BAD'].mean():.1f}%->{100*new['BAD'].mean():.1f}%\n"
    f"touch mean {old['touch_count'].mean():.2f}->{new['touch_count'].mean():.2f}\n"
    f"width% mean {old['channel_width_pct'].mean():.2f}->{new['channel_width_pct'].mean():.2f}"
)
# v5 compliance
lines.append("\n=== v5 compliance ===")
lines.append(
    f"touch in 4-5: {int(new['touch_count'].between(4,5).mean()*100)}% "
    f"(out={int((~new['touch_count'].between(4,5)).sum())}) "
    f"width>=2%: {int((new['channel_width_pct']>=2).mean()*100)}% "
    f"(lt2={int((new['channel_width_pct']<2).sum())}) "
    f"score>=80: {int((new['score']>=80).mean()*100)}%"
)
# vs what-if expectation ~ n=32 hit40.6 avg+0.83
lines.append(
    "\nwhat-if target (width>2 & touch4-5 on e7): n~32 hit~40.6% avg_pnl~+0.83% BAD%~31%"
)

out = Path("exported_docs") / "CSB_4ca39a24_analysis.txt"
out.write_text("\n".join(lines), encoding="utf-8")
print(out.read_text(encoding="utf-8"))
