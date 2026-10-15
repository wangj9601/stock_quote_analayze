# -*- coding: utf-8 -*-
"""分析 CSB 回测 e7b3cbe0，并与 2bd159df 对照。"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pymupdf

COL = {
    "signal_date": 2,
    "signal_type": 3,
    "score": 4,
    "hit_target": 9,
    "exit_reason": 13,
    "pnl_pct": 14,
    "bars_held": 15,
    "touch_count": 19,
    "max_gain_pct": 8,
}

DL = Path(r"C:\Users\Administrator\Downloads")


def load_csv(tid: str) -> pd.DataFrame:
    path = list(DL.glob(f"*{tid}*.csv"))[0]
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        df = pd.read_csv(path, encoding=enc)
        st = df.iloc[:, COL["signal_type"]].astype(str)
        if st.str.contains("CSB_").any():
            return df
    raise RuntimeError(tid)


def summarize(tid: str, df: pd.DataFrame) -> dict:
    sig = df.iloc[:, COL["signal_type"]].astype(str)
    exit_r = df.iloc[:, COL["exit_reason"]].astype(str)
    pnl = pd.to_numeric(df.iloc[:, COL["pnl_pct"]], errors="coerce")
    score = pd.to_numeric(df.iloc[:, COL["score"]], errors="coerce")
    mg = pd.to_numeric(df.iloc[:, COL["max_gain_pct"]], errors="coerce")
    touch = pd.to_numeric(df.iloc[:, COL["touch_count"]], errors="coerce")
    held = pd.to_numeric(df.iloc[:, COL["bars_held"]], errors="coerce")
    if "hit_target_lower" in df.columns:
        hit = df["hit_target_lower"].astype(bool)
    else:
        hit = df.iloc[:, COL["hit_target"]].astype(str).isin(["是", "True", "true", "1"])

    exit_counts = exit_r.value_counts().to_dict()
    exit_stats = []
    for name, idx in exit_r.groupby(exit_r).groups.items():
        part_pnl = pnl.loc[idx]
        part_hit = hit.loc[idx]
        exit_stats.append(
            {
                "reason": str(name),
                "n": len(idx),
                "pct": round(100 * len(idx) / len(df), 1),
                "avg_pnl": round(float(part_pnl.mean()), 2),
                "win": round(100 * float((part_pnl > 0).mean()), 1),
                "hit": round(100 * float(part_hit.mean()), 1),
            }
        )
    exit_stats.sort(key=lambda x: -x["n"])

    sd = pd.to_datetime(df.iloc[:, COL["signal_date"]], errors="coerce")
    monthly = sd.dt.to_period("M").value_counts().sort_index().to_dict()
    monthly = {str(k): int(v) for k, v in monthly.items()}

    return {
        "tid": tid,
        "n": len(df),
        "sig": sig.value_counts().to_dict(),
        "hit_rate": round(100 * float(hit.mean()), 2),
        "win_rate": round(100 * float((pnl > 0).mean()), 2),
        "avg_pnl": round(float(pnl.mean()), 2),
        "median_pnl": round(float(pnl.median()), 2),
        "avg_max_gain": round(float(mg.mean()), 2),
        "avg_score": round(float(score.mean()), 2),
        "min_score": round(float(score.min()), 2),
        "avg_touch": round(float(touch.mean()), 2),
        "avg_held": round(float(held.mean()), 2),
        "exit_counts": {str(k): int(v) for k, v in exit_counts.items()},
        "exit_stats": exit_stats,
        "monthly": monthly,
    }


def pdf_compact(tid: str) -> str:
    path = list(DL.glob(f"*{tid}*.pdf"))[0]
    doc = pymupdf.open(path)
    text = "\n".join(p.get_text("text") for p in doc)
    lines = [
        ln.strip()
        for ln in text.splitlines()
        if ln.strip() and re.search(r"[A-Za-z0-9%~+\-×x./]", ln)
    ]
    return "\n".join(lines[:40])


lines: list[str] = []


def log(s: str = "") -> None:
    print(s)
    lines.append(s)


new = summarize("e7b3cbe0", load_csv("e7b3cbe0"))
old = summarize("2bd159df", load_csv("2bd159df"))

log("=== e7b3cbe0 (new) ===")
for k in (
    "n",
    "hit_rate",
    "win_rate",
    "avg_pnl",
    "median_pnl",
    "avg_max_gain",
    "avg_score",
    "min_score",
    "avg_touch",
    "avg_held",
    "sig",
):
    log(f"{k}: {new[k]}")
log("exit_stats:")
for e in new["exit_stats"]:
    log(f"  {e}")
log(f"monthly: {new['monthly']}")

log("\n=== PDF e7b3cbe0 ===")
log(pdf_compact("e7b3cbe0"))

log("\n=== vs 2bd159df ===")
log(
    f"n {old['n']} -> {new['n']}\n"
    f"hit {old['hit_rate']}% -> {new['hit_rate']}%\n"
    f"win {old['win_rate']}% -> {new['win_rate']}%\n"
    f"avg_pnl {old['avg_pnl']}% -> {new['avg_pnl']}%\n"
    f"avg_max_gain {old['avg_max_gain']}% -> {new['avg_max_gain']}%\n"
    f"avg_held {old['avg_held']} -> {new['avg_held']}"
)
log("exit pct compare (by n-rank labels from each run):")
# map by Chinese reason string as-is
old_map = {e["reason"]: e for e in old["exit_stats"]}
new_map = {e["reason"]: e for e in new["exit_stats"]}
all_reasons = sorted(set(old_map) | set(new_map), key=lambda r: -(new_map.get(r) or old_map.get(r) or {}).get("n", 0))
for r in all_reasons:
    o = old_map.get(r)
    n = new_map.get(r)
    log(
        f"  {r}: "
        f"n {o['n'] if o else 0}->{n['n'] if n else 0} "
        f"({o['pct'] if o else 0}%->{n['pct'] if n else 0}%) "
        f"avg_pnl {o['avg_pnl'] if o else '-'}->{n['avg_pnl'] if n else '-'}"
    )

out = Path("exported_docs") / "CSB_e7b3cbe0_analysis.txt"
out.write_text("\n".join(lines), encoding="utf-8")
print("WROTE", out)
