# -*- coding: utf-8 -*-
"""分析 CSB 回测 b0505621（预期 v6），对照 cdaac3ce / e7b3cbe0。"""
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
    "回踩次数": "touch_count",
    "通道上轨": "channel_upper",
    "通道下轨": "channel_lower",
    "入场价": "entry_price",
    "观察期最大涨幅(%)": "max_gain_pct",
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
            "touch_count": 19,
            "channel_upper": 22,
            "channel_lower": 23,
        }
        for k, i in pos.items():
            df[k] = df.iloc[:, i]
    for c in (
        "score",
        "pnl_pct",
        "bars_held",
        "touch_count",
        "channel_upper",
        "channel_lower",
        "entry_price",
        "max_gain_pct",
    ):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "hit_target_lower" in df.columns:
        df["hit"] = df["hit_target_lower"].astype(bool)
    else:
        df["hit"] = False
    width = df["channel_upper"] - df["channel_lower"]
    df["channel_width_pct"] = (width / df["entry_price"].replace(0, np.nan)) * 100.0
    df["entry_pos"] = (df["entry_price"] - df["channel_lower"]) / width.replace(0, np.nan)
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
        f"entry_pos min/mean={df['entry_pos'].min():.3f}/{df['entry_pos'].mean():.3f} "
        f"pos<0 n={int((df['entry_pos']<0).sum())}"
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
    lines.append(
        "monthly: "
        + str({str(k): int(v) for k, v in sd.dt.to_period("M").value_counts().sort_index().items()})
    )
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


def cmp(a: pd.DataFrame, b: pd.DataFrame, label: str) -> list[str]:
    return [
        f"=== vs {label} ===",
        f"n {len(a)}->{len(b)}",
        f"hit {100*a['hit'].mean():.2f}%->{100*b['hit'].mean():.2f}%",
        f"win {100*(a['pnl_pct']>0).mean():.2f}%->{100*(b['pnl_pct']>0).mean():.2f}%",
        f"avg_pnl {a['pnl_pct'].mean():.2f}%->{b['pnl_pct'].mean():.2f}%",
        f"BAD% {100*a['BAD'].mean():.1f}%->{100*b['BAD'].mean():.1f}%",
        f"entry_pos mean {a['entry_pos'].mean():.3f}->{b['entry_pos'].mean():.3f}",
    ]


lines: list[str] = []
new = load("b0505621")
v5 = load("cdaac3ce")
v3 = load("e7b3cbe0")
lines.extend(summarize("b0505621", new))
lines.append("\n=== PDF ===")
lines.append(pdf_lines("b0505621"))
lines.extend(cmp(v5, new, "cdaac3ce (v5)"))
lines.extend(cmp(v3, new, "e7b3cbe0 (v3)"))
lines.append("\n=== v6 compliance (entry CSV uses next-day entry_price) ===")
lines.append(
    f"touch 4-5: {100*new['touch_count'].between(4,5).mean():.0f}% "
    f"width>=2%: {100*(new['channel_width_pct']>=2).mean():.0f}% "
    f"entry_pos>=0: {100*(new['entry_pos']>=0).mean():.0f}% (lt0={int((new['entry_pos']<0).sum())}) "
    f"score>=80: {100*(new['score']>=80).mean():.0f}%"
)
lines.append(
    "note: filter uses signal-day close; CSV entry_pos is next-day open — may differ slightly"
)

out = Path("exported_docs") / "CSB_b0505621_analysis.txt"
out.write_text("\n".join(lines), encoding="utf-8")
print(out.read_text(encoding="utf-8"))
