# -*- coding: utf-8 -*-
"""分析 CSB 回测 8810a56d（v4），对照 e7b3cbe0（v3）。"""
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
        if df.iloc[:, COL["signal_type"]].astype(str).str.contains("CSB_").any():
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
    monthly = {str(k): int(v) for k, v in sd.dt.to_period("M").value_counts().sort_index().items()}
    fail_pct = sum(e["pct"] for e in exit_stats if any(k in e["reason"] for k in ("通道", "基准", "channel", "baseline", "止损")))
    # more reliable: sum pct for top failure-like by known Chinese labels via n of channel+baseline
    # identify by ranking - use string contains after normalizing
    fail_n = 0
    for e in exit_stats:
        r = e["reason"]
        if "通道" in r or "基准" in r or "channel" in r.lower() or "baseline" in r.lower():
            # 阶梯跟踪也含止损 — exclude 阶梯/跟踪
            if "阶梯" in r or "跟踪" in r or "ma_trail" in r.lower():
                continue
            fail_n += e["n"]

    return {
        "tid": tid,
        "n": len(df),
        "sig": {str(k): int(v) for k, v in sig.value_counts().items()},
        "hit_rate": round(100 * float(hit.mean()), 2),
        "win_rate": round(100 * float((pnl > 0).mean()), 2),
        "avg_pnl": round(float(pnl.mean()), 2),
        "median_pnl": round(float(pnl.median()), 2),
        "avg_max_gain": round(float(mg.mean()), 2),
        "avg_score": round(float(score.mean()), 2),
        "min_score": round(float(score.min()), 2),
        "avg_touch": round(float(touch.mean()), 2),
        "min_touch": int(touch.min()) if touch.notna().any() else None,
        "avg_held": round(float(held.mean()), 2),
        "exit_stats": exit_stats,
        "monthly": monthly,
        "fail_struct_n": fail_n,
        "fail_struct_pct": round(100 * fail_n / len(df), 1) if len(df) else 0,
    }


def pdf_compact(tid: str) -> str:
    path = list(DL.glob(f"*{tid}*.pdf"))[0]
    doc = pymupdf.open(path)
    text = "\n".join(p.get_text("text") for p in doc)
    return "\n".join(
        ln.strip()
        for ln in text.splitlines()
        if ln.strip() and re.search(r"[A-Za-z0-9%~+\-×x./]", ln)
    )[:2000]


lines: list[str] = []


def log(s: str = "") -> None:
    print(s)
    lines.append(s)


new = summarize("8810a56d", load_csv("8810a56d"))
old = summarize("e7b3cbe0", load_csv("e7b3cbe0"))

log("=== 8810a56d (v4) ===")
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
    "min_touch",
    "avg_held",
    "sig",
    "fail_struct_pct",
):
    log(f"{k}: {new[k]}")
log("exit_stats:")
for e in new["exit_stats"]:
    log(f"  {e}")
log(f"monthly: {new['monthly']}")

log("\n=== PDF ===")
log(pdf_compact("8810a56d"))

log("\n=== vs e7b3cbe0 (v3) ===")
log(
    f"n {old['n']} -> {new['n']}\n"
    f"hit {old['hit_rate']}% -> {new['hit_rate']}%\n"
    f"win {old['win_rate']}% -> {new['win_rate']}%\n"
    f"avg_pnl {old['avg_pnl']}% -> {new['avg_pnl']}%\n"
    f"median_pnl {old['median_pnl']}% -> {new['median_pnl']}%\n"
    f"avg_max_gain {old['avg_max_gain']}% -> {new['avg_max_gain']}%\n"
    f"avg_score {old['avg_score']} -> {new['avg_score']} (min {old['min_score']}->{new['min_score']})\n"
    f"avg_touch {old['avg_touch']} -> {new['avg_touch']} (min {old.get('min_touch')}->{new['min_touch']})\n"
    f"avg_held {old['avg_held']} -> {new['avg_held']}\n"
    f"struct_fail(channel+baseline) {old['fail_struct_pct']}% -> {new['fail_struct_pct']}%"
)
old_map = {e["reason"]: e for e in old["exit_stats"]}
new_map = {e["reason"]: e for e in new["exit_stats"]}
for r in sorted(set(old_map) | set(new_map), key=lambda x: -(new_map.get(x) or old_map.get(x) or {}).get("n", 0)):
    o, n = old_map.get(r), new_map.get(r)
    log(
        f"  {r}: n {o['n'] if o else 0}->{n['n'] if n else 0} "
        f"({o['pct'] if o else 0}%->{n['pct'] if n else 0}%) "
        f"avg_pnl {o['avg_pnl'] if o else '-'}->{n['avg_pnl'] if n else '-'}"
    )

out = Path("exported_docs") / "CSB_8810a56d_analysis.txt"
out.write_text("\n".join(lines), encoding="utf-8")
print("WROTE", out)
