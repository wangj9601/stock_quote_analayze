# -*- coding: utf-8 -*-
"""失效(通道/基准) vs 到期/派发 因子对照 —— 主看 e7b3cbe0，辅看 8810a56d。"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DL = Path(r"C:\Users\Administrator\Downloads")
OUT = Path("exported_docs")
OUT.mkdir(exist_ok=True)

# 英文逻辑列 ← 中文表头
RENAME = {
    "股票代码": "code",
    "股票名称": "name",
    "信号日期": "signal_date",
    "信号类型": "signal_type",
    "得分": "score",
    "入场日期": "entry_date",
    "入场价": "entry_price",
    "观察期最高价": "max_high",
    "观察期最大涨幅(%)": "max_gain_pct",
    "是否命中目标": "hit_target",
    "命中日期": "hit_date",
    "出场日期": "exit_date",
    "出场价": "exit_price",
    "出场原因": "exit_reason",
    "盈亏比例(%)": "pnl_pct",
    "持有天数": "bars_held",
    "观察期天数": "horizon_days",
    "粘合天数": "squeeze_days",
    "粘合带宽": "squeeze_pct",
    "回踩次数": "touch_count",
    "放量倍数": "vol_expand_mult",
    "5/20量比": "vol_ratio_5_20",
    "通道上轨": "channel_upper",
    "通道下轨": "channel_lower",
    "基准低点": "entry_low",
}


def load(tid: str) -> pd.DataFrame:
    path = list(DL.glob(f"*{tid}*.csv"))[0]
    df = pd.read_csv(path, encoding="utf-8-sig")
    df = df.rename(columns={k: v for k, v in RENAME.items() if k in df.columns})
    # 若中文列被破坏，按固定位置
    if "exit_reason" not in df.columns:
        cols = list(df.columns)
        pos = {
            "code": 0,
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
        "entry_price",
        "max_gain_pct",
        "pnl_pct",
        "bars_held",
        "squeeze_days",
        "squeeze_pct",
        "touch_count",
        "vol_expand_mult",
        "vol_ratio_5_20",
        "channel_upper",
        "channel_lower",
        "entry_low",
    ):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "hit_target_lower" in df.columns:
        df["hit"] = df["hit_target_lower"].astype(bool)
    else:
        df["hit"] = df.get("hit_target", pd.Series(dtype=str)).astype(str).isin(["是", "True", "true", "1"])

    # 通道几何
    cu, cl, ep, el = df["channel_upper"], df["channel_lower"], df["entry_price"], df["entry_low"]
    width = (cu - cl).where((cu > 0) & (cl > 0))
    df["channel_width_pct"] = (width / ep.replace(0, np.nan)) * 100.0
    df["entry_pos_in_channel"] = (ep - cl) / width.replace(0, np.nan)  # 0=下轨 1=上轨
    df["entry_above_lower_pct"] = ((ep - cl) / cl.replace(0, np.nan)) * 100.0
    df["stop_cushion_pct"] = ((ep - el) / ep.replace(0, np.nan)) * 100.0  # 入场相对基准低点缓冲
    df["vol_ratio"] = df["vol_ratio_5_20"].fillna(df["vol_expand_mult"])

    reason = df["exit_reason"].astype(str)
    def grp(r: str) -> str:
        if "通道" in r or r == "channel_fail":
            return "bad_channel"
        if "基准" in r or r == "baseline_stop":
            return "bad_baseline"
        if "到期" in r or r == "horizon_end":
            return "good_horizon"
        if "派发" in r or r == "distribution":
            return "good_dist"
        if "阶梯" in r or "跟踪" in r or r == "ma_trail":
            return "mid_trail"
        return "other"

    df["cohort"] = reason.map(grp)
    df["cohort2"] = df["cohort"].map(
        {
            "bad_channel": "BAD",
            "bad_baseline": "BAD",
            "good_horizon": "GOOD",
            "good_dist": "GOOD",
            "mid_trail": "MID",
            "other": "OTHER",
        }
    )
    df["task"] = tid
    return df


FACTORS = [
    "score",
    "touch_count",
    "squeeze_days",
    "squeeze_pct",
    "vol_ratio",
    "channel_width_pct",
    "entry_pos_in_channel",
    "entry_above_lower_pct",
    "stop_cushion_pct",
    "bars_held",
    "max_gain_pct",
    "pnl_pct",
]


def cohort_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, part in df.groupby("cohort2"):
        row = {"cohort": name, "n": len(part), "pct": round(100 * len(part) / len(df), 1)}
        row["hit_rate"] = round(100 * float(part["hit"].mean()), 1)
        row["win_rate"] = round(100 * float((part["pnl_pct"] > 0).mean()), 1)
        for f in FACTORS:
            if f in part.columns:
                row[f"mean_{f}"] = round(float(part[f].mean()), 3)
                row[f"med_{f}"] = round(float(part[f].median()), 3)
        rows.append(row)
    return pd.DataFrame(rows).sort_values("n", ascending=False)


def detail_by_exit(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, part in df.groupby("cohort"):
        row = {"cohort": name, "n": len(part)}
        for f in FACTORS:
            row[f"mean_{f}"] = round(float(part[f].mean()), 3)
        rows.append(row)
    return pd.DataFrame(rows).sort_values("n", ascending=False)


def bucket_lift(df: pd.DataFrame, col: str, edges: list[float], labels: list[str]) -> pd.DataFrame:
    sub = df[df["cohort2"].isin(["BAD", "GOOD"])].copy()
    sub["bucket"] = pd.cut(sub[col], bins=edges, labels=labels, include_lowest=True)
    rows = []
    for b, part in sub.groupby("bucket", observed=False):
        if len(part) == 0:
            continue
        bad = (part["cohort2"] == "BAD").sum()
        good = (part["cohort2"] == "GOOD").sum()
        rows.append(
            {
                "factor": col,
                "bucket": str(b),
                "n": len(part),
                "bad": int(bad),
                "good": int(good),
                "bad_rate": round(100 * bad / len(part), 1),
                "good_rate": round(100 * good / len(part), 1),
                "avg_pnl": round(float(part["pnl_pct"].mean()), 2),
                "hit_rate": round(100 * float(part["hit"].mean()), 1),
            }
        )
    return pd.DataFrame(rows)


lines: list[str] = []


def log(s: str = "") -> None:
    print(s)
    lines.append(s)


# 主样本 v3（量大）
df3 = load("e7b3cbe0")
df4 = load("8810a56d")

log("=== e7b3cbe0 cohort2 ===")
t3 = cohort_table(df3)
log(t3.to_string(index=False))
log("\n=== e7b3cbe0 cohort detail ===")
log(detail_by_exit(df3).to_string(index=False))

log("\n=== 8810a56d cohort2 (reference) ===")
log(cohort_table(df4).to_string(index=False))

# 分桶：在 BAD+GOOD 上找 lift
log("\n=== bucket lifts on e7b3cbe0 (BAD vs GOOD only) ===")
buckets = [
    ("score", [0, 82, 86, 90, 100], ["<=82", "82-86", "86-90", ">90"]),
    ("touch_count", [0, 3, 4, 5, 20], ["<=3", "4", "5", ">=6"]),
    ("squeeze_days", [0, 15, 25, 40, 200], ["<=15", "16-25", "26-40", ">40"]),
    ("squeeze_pct", [0, 0.015, 0.025, 0.04, 1], ["<=1.5%", "1.5-2.5%", "2.5-4%", ">4%"]),
    ("vol_ratio", [0, 0.5, 0.65, 0.8, 5], ["<=0.5", "0.5-0.65", "0.65-0.8", ">0.8"]),
    ("channel_width_pct", [0, 2, 4, 6, 50], ["<=2%", "2-4%", "4-6%", ">6%"]),
    ("entry_pos_in_channel", [0, 0.25, 0.5, 0.75, 1.5], ["near_low", "low-mid", "mid-high", "near_high"]),
    ("stop_cushion_pct", [-5, 0.5, 1.5, 3, 20], ["<=0.5%", "0.5-1.5%", "1.5-3%", ">3%"]),
]
all_b = []
for col, edges, labels in buckets:
    bt = bucket_lift(df3, col, edges, labels)
    all_b.append(bt)
    log(f"\n-- {col} --")
    log(bt.to_string(index=False))

# BAD vs GOOD 均值差排序
bad = df3[df3["cohort2"] == "BAD"]
good = df3[df3["cohort2"] == "GOOD"]
log("\n=== BAD vs GOOD mean delta (e7b3cbe0) ===")
deltas = []
for f in FACTORS:
    if f in ("pnl_pct", "max_gain_pct", "bars_held"):
        continue
    bm, gm = float(bad[f].mean()), float(good[f].mean())
    deltas.append({"factor": f, "bad_mean": round(bm, 3), "good_mean": round(gm, 3), "good_minus_bad": round(gm - bm, 3)})
dlt = pd.DataFrame(deltas).sort_values("good_minus_bad", key=lambda s: s.abs(), ascending=False)
log(dlt.to_string(index=False))

# 建议阈值：挑 bad_rate 最低且 n 足够的桶
log("\n=== candidate filters (bad_rate low, n>=12) ===")
cand = pd.concat(all_b, ignore_index=True)
cand = cand[(cand["n"] >= 12) & (cand["factor"] != "score")]  # score already tried
# also include score
cand = pd.concat(all_b, ignore_index=True)
cand = cand[cand["n"] >= 12].copy()
base_bad = 100 * (df3["cohort2"] == "BAD").sum() / len(df3)
# among BAD+GOOD only baseline
bg = df3[df3["cohort2"].isin(["BAD", "GOOD"])]
base_bad_bg = 100 * (bg["cohort2"] == "BAD").sum() / len(bg)
cand["lift_vs_bg"] = (base_bad_bg - cand["bad_rate"]).round(1)
cand = cand.sort_values(["lift_vs_bg", "avg_pnl"], ascending=[False, False])
log(f"BAD rate among BAD+GOOD baseline: {base_bad_bg:.1f}%")
log(cand.head(15).to_string(index=False))

# 组合试探：不改代码，仅统计
log("\n=== combo what-if on e7b3cbe0 ===")
combos = [
    ("vol_ratio<=0.65", df3["vol_ratio"] <= 0.65),
    ("squeeze_pct<=0.025", df3["squeeze_pct"] <= 0.025),
    ("channel_width_pct<=4", df3["channel_width_pct"] <= 4),
    ("entry_pos<=0.5", df3["entry_pos_in_channel"] <= 0.5),
    ("stop_cushion>=1.5", df3["stop_cushion_pct"] >= 1.5),
    ("vol<=0.65 & width<=4", (df3["vol_ratio"] <= 0.65) & (df3["channel_width_pct"] <= 4)),
    ("vol<=0.65 & pos<=0.5", (df3["vol_ratio"] <= 0.65) & (df3["entry_pos_in_channel"] <= 0.5)),
    ("width<=4 & pos<=0.5", (df3["channel_width_pct"] <= 4) & (df3["entry_pos_in_channel"] <= 0.5)),
    ("vol<=0.65 & width<=4 & pos<=0.5", (df3["vol_ratio"] <= 0.65) & (df3["channel_width_pct"] <= 4) & (df3["entry_pos_in_channel"] <= 0.5)),
]
for name, mask in combos:
    part = df3[mask]
    if len(part) == 0:
        continue
    bad_n = (part["cohort2"] == "BAD").sum()
    log(
        f"{name}: n={len(part)} hit={100*part['hit'].mean():.1f}% "
        f"win={100*(part['pnl_pct']>0).mean():.1f}% avg_pnl={part['pnl_pct'].mean():.2f}% "
        f"BAD%={100*bad_n/len(part):.1f}%"
    )

report = "\n".join(lines)
(OUT / "CSB_factor_contrast_e7b3cbe0.txt").write_text(report, encoding="utf-8")
t3.to_csv(OUT / "CSB_factor_cohort_e7b3cbe0.csv", index=False, encoding="utf-8-sig")
pd.concat(all_b, ignore_index=True).to_csv(OUT / "CSB_factor_buckets_e7b3cbe0.csv", index=False, encoding="utf-8-sig")
print("WROTE", OUT / "CSB_factor_contrast_e7b3cbe0.txt")
