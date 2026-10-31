# -*- coding: utf-8 -*-
"""SEPA 参数校准：一次抽取信号特征，多组阈值离线扫描。

为什么这么做
------------
不在每组阈值下重跑整条链路（太慢），而是把每个 (交易日, 个股) 的原始特征
（趋势八条、收缩序列、距枢轴距离、量比、两融状态量）一次性落盘，之后任何参数
组合都只是对这些特征做过滤，扫描成本接近 0。

    800 只 x 97 个评估日（2024-10 ~ 2026-09）抽一次特征约 4 分钟，
    之后每个参数组合的统计是毫秒级。

三阶段用法
----------
    python scripts/calibrate_sepa.py features --codes 800 --step 5
    python scripts/calibrate_sepa.py sweep      # 参数矩阵 + 两融 + 就位 + RS
    python scripts/calibrate_sepa.py periods    # 分期稳健性（防单一行情主导）

最近一次校准的主要结论（已写进 config.py 的默认值）
---------------------------------------------------
1. "就位待突破"（距枢轴 3% 内 + 最近 10 日振幅 <=8%）三期一致优于"放量突破"：
   10 日胜率 60~63% vs 40~49%，中位收益 +1.7~2.4% vs -2.2~-0.3%。
2. 突破必须给距离上限：原来的 dist >= 0.2% 无上界，导致距枢轴 50% 的票也被
   标成"突破"，实际是追高。
3. 末次收缩深度 0.10 最优、0.15 以上转负，且必须真正拦截而不是只打标签。
4. 量能倍数 1.0/1.2/1.5 无显著差异，3.0 倍量在牛市段 10 日均值 -3.64%。
5. 两融层样本不足（明细仅 2026-07 起），仅"拥挤度 >5%"有强负向证据。
"""

from __future__ import annotations

import argparse
import bisect
import pickle
import random
import sys
import time
from pathlib import Path

PROJECT = str(Path(__file__).resolve().parents[1])
if PROJECT not in sys.path:
    sys.path.insert(0, PROJECT)

import numpy as np  # noqa: E402
from sqlalchemy import text  # noqa: E402

from backend_core.database.db import SessionLocal  # noqa: E402
from backend_core.analysis.sepa import compute_trend_template, detect_vcp, assess_margin  # noqa: E402
from backend_core.analysis.sepa.bars import rs_rank  # noqa: E402
from backend_core.analysis.sepa.config import MarginConfig, TrendConfig, VCPConfig  # noqa: E402
from backend_core.analysis.sepa.trend import momentum_of  # noqa: E402

CACHE_DIR = Path(PROJECT) / "sepa_cache"
HORIZONS = (5, 10, 20)

# 宽松配置：让"是否算突破/是否有形态"不在这里判定，只取原始特征
LOOSE_VCP = VCPConfig(
    max_last_depth=0.99,
    breakout_vol_multiple=0.0,
    max_tight_range=0.99,
    chase_distance=99.0,
)
LOOSE_MARGIN = MarginConfig(crowd_max=99.0)


def load_universe(db, n_codes: int, seed: int) -> list[str]:
    rows = db.execute(
        text(
            "SELECT code FROM historical_quotes "
            "WHERE code ~ '^[0-9]{6}$' "
            "GROUP BY code HAVING COUNT(*) >= 450 ORDER BY code"
        )
    ).fetchall()
    codes = [r[0] for r in rows]
    random.Random(seed).shuffle(codes)
    return codes[:n_codes]


def load_bars(db, codes: list[str]) -> dict:
    rows = db.execute(
        text(
            "SELECT code, date, open, high, low, close, volume FROM historical_quotes "
            "WHERE code = ANY(:codes) ORDER BY code, date"
        ),
        {"codes": codes},
    ).mappings().all()
    out: dict = {}
    for r in rows:
        d = out.setdefault(r["code"], {"dates": [], "o": [], "h": [], "l": [], "c": [], "v": []})
        d["dates"].append(str(r["date"])[:10])
        d["o"].append(r["open"])
        d["h"].append(r["high"])
        d["l"].append(r["low"])
        d["c"].append(r["close"])
        d["v"].append(r["volume"])
    for d in out.values():
        for k in ("o", "h", "l", "c", "v"):
            d[k] = np.asarray(d[k], dtype=float)
    return out


def load_margin(db, codes: list[str]) -> dict:
    rows = db.execute(
        text(
            "SELECT code, trade_date, rzye, rzmre, rzche FROM stock_margin_daily "
            "WHERE code = ANY(:codes) AND rzye IS NOT NULL ORDER BY code, trade_date"
        ),
        {"codes": codes},
    ).mappings().all()
    out: dict = {}
    for r in rows:
        out.setdefault(r["code"], []).append(
            {
                "trade_date": str(r["trade_date"])[:10],
                "rzye": r["rzye"],
                "rzmre": r["rzmre"],
                "rzche": r["rzche"],
            }
        )
    return out


def load_float_mv(db, codes: list[str], end_date: str) -> dict:
    rows = db.execute(
        text(
            "SELECT b.code, b.free_float_shares, "
            "  (SELECT q.close FROM historical_quotes q WHERE q.code=b.code AND q.date<=:d "
            "   ORDER BY q.date DESC LIMIT 1) AS close "
            "FROM stock_basic_info b WHERE b.code = ANY(:codes)"
        ),
        {"codes": codes, "d": end_date},
    ).mappings().all()
    out = {}
    for r in rows:
        shares, close = r["free_float_shares"], r["close"]
        if not shares or not close:
            continue
        shares = float(shares)
        if shares < 1e6:
            shares *= 1e4
        out[r["code"]] = shares * float(close)
    return out


def slice_bars(d, i: int, n: int = 340) -> list[dict]:
    s = max(0, i - n + 1)
    dates, o, h, l, c, v = d["dates"], d["o"], d["h"], d["l"], d["c"], d["v"]
    return [
        {"date": dates[j], "open": o[j], "high": h[j], "low": l[j], "close": c[j], "volume": v[j]}
        for j in range(s, i + 1)
    ]


def cmd_features(args) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    db = SessionLocal()
    t0 = time.time()
    codes = load_universe(db, args.codes, args.seed)
    print(f"universe: {len(codes)} 只（随机种子 {args.seed}）")

    bars = load_bars(db, codes)
    codes = [c for c in codes if c in bars and len(bars[c]["dates"]) >= 300]
    margin = load_margin(db, codes)
    float_mv = load_float_mv(db, codes, "2026-10-30")

    cal = db.execute(
        text("SELECT DISTINCT date FROM historical_quotes WHERE date >= :d ORDER BY date"),
        {"d": args.start},
    ).fetchall()
    calendar = [str(r[0])[:10] for r in cal]
    calendar = [d for d in calendar if d <= args.end][:: args.step]
    print(f"评估日: {len(calendar)} 个（{calendar[0]} ~ {calendar[-1]}，间隔 {args.step} 个交易日）")

    tc = TrendConfig()
    rows: list[dict] = []
    for n, d in enumerate(calendar, 1):
        # 1) 该日可交易的标的与其 K 线切片
        slices: dict = {}
        for code in codes:
            dates = bars[code]["dates"]
            i = bisect.bisect_right(dates, d) - 1
            if i < tc.min_bars:
                continue
            slices[code] = (i, slice_bars(bars[code], i))

        # 2) 横截面相对强度
        mom = {c: momentum_of(s[1]) for c, s in slices.items()}
        ranks = dict(zip(slices.keys(), rs_rank(list(mom.values()))))

        # 3) 逐票：趋势 -> VCP -> 两融
        for code, (i, bslice) in slices.items():
            tr = compute_trend_template(bslice, rs_rank=ranks.get(code), cfg=tc)
            base = {
                "date": d,
                "code": code,
                "trend_ok": tr["ok"],
                "ok_count": tr["ok_count"],
                "trend_quality": (tr.get("metrics") or {}).get("trend_quality"),
                "rs_rank": ranks.get(code),
                "ret5": np.nan,
                "ret10": np.nan,
                "ret20": np.nan,
            }
            c_arr = bars[code]["c"]
            for h in HORIZONS:
                if i + h < len(c_arr):
                    base[f"ret{h}"] = float(c_arr[i + h] / c_arr[i] - 1.0)
            if not tr["ok"]:
                base["has_vcp"] = False
                rows.append(base)
                continue

            vcp = detect_vcp(bslice, cfg=LOOSE_VCP)
            base.update(
                {
                    "has_vcp": vcp["count"] > 0,
                    "count": vcp["count"],
                    "last_depth": (vcp["contractions"][-1]["depth_pct"] / 100.0)
                    if vcp["contractions"] else np.nan,
                    "dist_pct": (vcp["dist_to_pivot_pct"] / 100.0)
                    if vcp["dist_to_pivot_pct"] is not None else np.nan,
                    "vol_ratio": vcp["vol_ratio"],
                    "tight_range": (vcp["tight_range_pct"] / 100.0)
                    if vcp["tight_range_pct"] is not None else np.nan,
                }
            )
            mg = margin.get(code) or []
            hist = [x for x in mg if x["trade_date"] <= d][-60:]
            ma = assess_margin(hist, circ_mv=float_mv.get(code), cfg=LOOSE_MARGIN)
            base.update(
                {
                    "mg_status": ma.get("status"),
                    "mg_score": ma.get("score"),
                    "crowd_pct": ma.get("crowd_pct"),
                    "mg_drawdown": ma.get("drawdown_pct"),
                    "mg_reflow": ma.get("reflow_pct"),
                    "mg_streak": ma.get("streak_days", 0),
                    "mg_net_sum": ma.get("net_buy_sum"),
                }
            )
            rows.append(base)

        if n % 10 == 0 or n == len(calendar):
            el = time.time() - t0
            print(f"  [{n}/{len(calendar)}] {d}  累计 {len(rows)} 行  已用 {el:.0f}s "
                  f"预计剩余 {el / n * (len(calendar) - n):.0f}s")

    db.close()
    out = CACHE_DIR / f"features_{args.codes}_{args.step}_{args.seed}.pkl"
    with open(out, "wb") as f:
        pickle.dump(
            {"rows": rows, "codes": codes, "calendar": calendar,
             "args": {k: v for k, v in vars(args).items() if k != "func"}},
            f,
        )
    print(f"\n已写入 {out}  共 {len(rows)} 行  趋势通过 {sum(r['trend_ok'] for r in rows)} 行")


def _stats(rets: dict, bench: dict, mask: list[bool]) -> dict:
    n = sum(mask)
    if n == 0:
        return {"n": 0}
    out = {"n": n}
    for h in HORIZONS:
        vals = [r[f"ret{h}"] for r, m in zip(rets, mask) if m and np.isfinite(r[f"ret{h}"])]
        if not vals:
            out[f"mean{h}"] = np.nan
            out[f"win{h}"] = np.nan
            out[f"exc{h}"] = np.nan
            continue
        out[f"mean{h}"] = float(np.mean(vals)) * 100
        out[f"win{h}"] = float(np.mean([v > 0 for v in vals])) * 100
        b = [bench[h][idx] for idx, m in enumerate(mask) if m and np.isfinite(rets[idx][f"ret{h}"])]
        out[f"exc{h}"] = out[f"mean{h}"] - (float(np.mean(b)) * 100 if b else 0.0)
    return out


def cmd_sweep(args) -> None:
    files = sorted(CACHE_DIR.glob("features_*.pkl"))
    if not files:
        raise SystemExit("没有缓存，先跑 features")
    path = files[-1] if not args.file else CACHE_DIR / args.file
    with open(path, "rb") as f:
        data = pickle.load(f)
    rows = data["rows"]
    print(f"载入 {path.name}  行数 {len(rows)}  评估日 {len(data['calendar'])} 个\n")

    # 基准：同一评估日、同一批"够 260 根"标的的等权前瞻收益
    bench = {h: [np.nan] * len(rows) for h in HORIZONS}
    by_date: dict = {}
    for idx, r in enumerate(rows):
        by_date.setdefault(r["date"], []).append(idx)
    for d, idxs in by_date.items():
        for h in HORIZONS:
            vals = [rows[i][f"ret{h}"] for i in idxs if np.isfinite(rows[i][f"ret{h}"])]
            if vals:
                mean = float(np.mean(vals))
                for i in idxs:
                    bench[h][i] = mean

    trend_ok = [r["trend_ok"] for r in rows]
    print("基准（同期同池等权）:")
    s = _stats(rows, bench, trend_ok)
    print(f"  趋势通过池 n={s['n']}  5日 {s['mean5']:.2f}%  10日 {s['mean10']:.2f}%  "
          f"20日 {s['mean20']:.2f}%\n")

    # ---- 参数矩阵 ----
    print("=" * 108)
    print("① 突破量能阈值 × 末次收缩深度上限（信号 = 趋势过 + 放量突破）")
    print("=" * 108)
    print(f"{'vol_mult':>9} {'last_depth':>11} {'n':>5} {'胜率5':>7} {'胜率10':>7} {'胜率20':>7} "
          f"{'均值10':>8} {'超额10':>8} {'均值20':>8} {'超额20':>8}")
    best = []
    for vm in (1.0, 1.2, 1.5, 2.0, 2.5, 3.0):
        for ldm in (0.08, 0.10, 0.12, 0.15, 0.20, 0.99):
            mask = [
                r["trend_ok"]
                and r.get("has_vcp")
                and np.isfinite(r.get("dist_pct", np.nan)) and r["dist_pct"] >= 0.002
                and np.isfinite(r.get("vol_ratio", np.nan)) and r["vol_ratio"] >= vm
                and (not np.isfinite(r.get("last_depth", np.nan)) or r["last_depth"] <= ldm)
                for r in rows
            ]
            st = _stats(rows, bench, mask)
            if st["n"] < 25:
                continue
            print(f"{vm:>9.1f} {ldm:>11.2f} {st['n']:>5} {st['win5']:>6.1f}% {st['win10']:>6.1f}% "
                  f"{st['win20']:>6.1f}% {st['mean10']:>7.2f}% {st['exc10']:>7.2f}% "
                  f"{st['mean20']:>7.2f}% {st['exc20']:>7.2f}%")
            best.append((st["exc20"], st["exc10"], vm, ldm, st))

    print()
    print("=" * 108)
    print("② 两融旁证是否加分（仅在有两融明细的区间有效，2026-07 起）")
    print("=" * 108)
    print(f"{'条件':<34} {'n':>5} {'胜率10':>7} {'均值10':>8} {'超额10':>8} {'均值20':>8} {'超额20':>8}")
    mg_cases = [
        ("无条件（全部突破）", lambda r: True),
        ("两融分 >= 55", lambda r: (r.get("mg_score") or 0) >= 55),
        ("两融分 < 55（对照）", lambda r: (r.get("mg_score") or 100) < 55),
        ("状态=回流确认", lambda r: r.get("mg_status") == "reflow"),
        ("状态=出清中/高位拥挤（对照）", lambda r: r.get("mg_status") in ("clearing", "crowded")),
        ("拥挤度 <= 5%", lambda r: np.isfinite(r.get("crowd_pct") or np.nan) and (r["crowd_pct"] or 0) <= 5),
        ("拥挤度 > 5%（对照）", lambda r: np.isfinite(r.get("crowd_pct") or np.nan) and (r["crowd_pct"] or 0) > 5),
    ]
    base_mask = [
        r["trend_ok"] and r.get("has_vcp")
        and np.isfinite(r.get("dist_pct", np.nan)) and r["dist_pct"] >= 0.002
        and np.isfinite(r.get("vol_ratio", np.nan)) and r["vol_ratio"] >= 1.5
        for r in rows
    ]
    for label, fn in mg_cases:
        mask = [b and fn(r) for b, r in zip(base_mask, rows)]
        st = _stats(rows, bench, mask)
        if st["n"] == 0:
            print(f"{label:<34} {'0':>5}   （样本为空）")
            continue
        print(f"{label:<34} {st['n']:>5} {st['win10']:>6.1f}% {st['mean10']:>7.2f}% "
              f"{st['exc10']:>7.2f}% {st['mean20']:>7.2f}% {st['exc20']:>7.2f}%")

    print()
    print("=" * 108)
    print("③ 就位待突破（未放量、距枢轴 3% 内、末端紧凑）——买在突破前是否更好")
    print("=" * 108)
    for label, dist_lo, dist_hi, need_tight in (
        ("距枢轴 -3%~0% + 紧凑", -0.03, 0.002, True),
        ("距枢轴 -6%~-3% + 紧凑", -0.06, -0.03, True),
        ("放量突破（对照）", 0.002, 9.9, False),
    ):
        mask = []
        for r in rows:
            d = r.get("dist_pct", np.nan)
            ok = (
                r["trend_ok"] and r.get("has_vcp") and np.isfinite(d)
                and dist_lo <= d < dist_hi
                and (not need_tight or (np.isfinite(r.get("tight_range", np.nan))
                                        and r["tight_range"] <= 0.08))
            )
            if not need_tight:
                ok = ok and np.isfinite(r.get("vol_ratio", np.nan)) and r["vol_ratio"] >= 1.5
            mask.append(ok)
        st = _stats(rows, bench, mask)
        if st["n"] == 0:
            print(f"{label:<34} 样本为空")
            continue
        print(f"{label:<34} {st['n']:>5} {st['win10']:>6.1f}% {st['mean10']:>7.2f}% "
              f"{st['exc10']:>7.2f}% {st['mean20']:>7.2f}% {st['exc20']:>7.2f}%")

    print()
    print("=" * 108)
    print("④ 相对强度门槛（趋势条件 8）的影响")
    print("=" * 108)
    for thr in (60, 70, 80, 90):
        mask = [
            r["trend_ok"] and (r.get("rs_rank") or 0) >= thr and r.get("has_vcp")
            and np.isfinite(r.get("dist_pct", np.nan)) and r["dist_pct"] >= 0.002
            and np.isfinite(r.get("vol_ratio", np.nan)) and r["vol_ratio"] >= 1.5
            for r in rows
        ]
        st = _stats(rows, bench, mask)
        if st["n"] == 0:
            continue
        print(f"RS >= {thr:<3}                        {st['n']:>5} {st['win10']:>6.1f}% "
              f"{st['mean10']:>7.2f}% {st['exc10']:>7.2f}% {st['mean20']:>7.2f}% {st['exc20']:>7.2f}%")


def _sig_breakout(r: dict, vol_mult: float = 1.5, ldm: float = 0.12) -> bool:
    return bool(
        r["trend_ok"] and r.get("has_vcp")
        and np.isfinite(r.get("dist_pct", np.nan)) and r["dist_pct"] >= 0.002
        and np.isfinite(r.get("vol_ratio", np.nan)) and r["vol_ratio"] >= vol_mult
        and (not np.isfinite(r.get("last_depth", np.nan)) or r["last_depth"] <= ldm)
    )


def _sig_ready(r: dict) -> bool:
    d = r.get("dist_pct", np.nan)
    return bool(
        r["trend_ok"] and r.get("has_vcp") and np.isfinite(d)
        and -0.03 <= d < 0.002
        and np.isfinite(r.get("tight_range", np.nan)) and r["tight_range"] <= 0.08
        and (not np.isfinite(r.get("last_depth", np.nan)) or r["last_depth"] <= 0.12)
    )


def cmd_periods(args) -> None:
    """分期稳健性：整体结论是否被某一段行情主导。"""
    files = sorted(CACHE_DIR.glob("features_*.pkl"))
    with open(files[-1], "rb") as f:
        data = pickle.load(f)
    rows = data["rows"]

    bench = {h: [np.nan] * len(rows) for h in HORIZONS}
    by_date: dict = {}
    for idx, r in enumerate(rows):
        by_date.setdefault(r["date"], []).append(idx)
    for idxs in by_date.values():
        for h in HORIZONS:
            vals = [rows[i][f"ret{h}"] for i in idxs if np.isfinite(rows[i][f"ret{h}"])]
            if vals:
                mean = float(np.mean(vals))
                for i in idxs:
                    bench[h][i] = mean

    periods = {
        "2024-10~2025-06": ("2024-10-01", "2025-06-30"),
        "2025-07~2025-12": ("2025-07-01", "2025-12-31"),
        "2026-01~2026-09": ("2026-01-01", "2026-12-31"),
    }
    print("=" * 104)
    print("⑤ 分期对照：放量突破 vs 就位待突破（超额 = 相对同期同池等权）")
    print("=" * 104)
    print(f"{'区间':<18}{'信号':<10}{'n':>5}{'胜率10':>8}{'均值10':>9}{'超额10':>9}"
          f"{'中位10':>9}{'均值20':>9}{'超额20':>9}")
    for name, (lo, hi) in periods.items():
        for label, fn in (("放量突破", lambda r: _sig_breakout(r)), ("就位待突破", lambda r: _sig_ready(r))):
            mask = [fn(r) and lo <= r["date"] <= hi for r in rows]
            st = _stats(rows, bench, mask)
            if st["n"] == 0:
                print(f"{name:<18}{label:<10}{0:>5}   （无信号）")
                continue
            meds = [r["ret10"] for r, m in zip(rows, mask) if m and np.isfinite(r["ret10"])]
            print(f"{name:<18}{label:<10}{st['n']:>5}{st['win10']:>7.1f}%{st['mean10']:>8.2f}%"
                  f"{st['exc10']:>8.2f}%{np.median(meds) * 100:>8.2f}%"
                  f"{st['mean20']:>8.2f}%{st['exc20']:>8.2f}%")

    print()
    print("=" * 104)
    print("⑥ 量能倍数在每一期的表现（末次收缩 <= 12%，用于判断 2 倍以上是否该禁用）")
    print("=" * 104)
    print(f"{'区间':<18}{'vol_mult':<10}{'n':>5}{'胜率10':>8}{'均值10':>9}{'超额10':>9}{'超额20':>9}")
    for name, (lo, hi) in periods.items():
        for vm in (1.0, 1.5, 2.0, 3.0):
            mask = [_sig_breakout(r, vol_mult=vm) and lo <= r["date"] <= hi for r in rows]
            st = _stats(rows, bench, mask)
            if st["n"] < 15:
                continue
            print(f"{name:<18}{vm:<10.1f}{st['n']:>5}{st['win10']:>7.1f}%{st['mean10']:>8.2f}%"
                  f"{st['exc10']:>8.2f}%{st['exc20']:>8.2f}%")


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    pf = sub.add_parser("features", help="抽特征并缓存")
    pf.add_argument("--codes", type=int, default=500)
    pf.add_argument("--step", type=int, default=5, help="每隔几个交易日评估一次")
    pf.add_argument("--start", default="2024-10-01")
    pf.add_argument("--end", default="2026-09-25")
    pf.add_argument("--seed", type=int, default=42)
    pf.set_defaults(func=cmd_features)

    ps = sub.add_parser("sweep", help="扫参数")
    ps.add_argument("--file", default=None)
    ps.set_defaults(func=cmd_sweep)

    pp = sub.add_parser("periods", help="分期稳健性检验")
    pp.set_defaults(func=cmd_periods)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
