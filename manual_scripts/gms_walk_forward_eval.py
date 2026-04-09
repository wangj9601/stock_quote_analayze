#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GMS 交易回测 Walk-forward 对比脚本

对比三组策略：
1) fixed_baseline: 固定止盈/止损（尽量关闭移动止损特性）
2) trailing_only: 仅移动止损（不分批止盈）
3) trailing_partial: 移动止损 + 分批止盈

输出：
- 控制台汇总（按验证段）
- CSV 明细：logs/gms_walk_forward_eval_*.csv
"""

import csv
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Tuple
import argparse

from dateutil.relativedelta import relativedelta

current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

from backend_api.database import SessionLocal
from backend_core.strategies.gms.backtest_runner import run_gms_backtest


def _month_start(d: datetime) -> datetime:
    return datetime(d.year, d.month, 1)


def _fmt(d: datetime) -> str:
    return d.strftime("%Y-%m-%d")


def _safe(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def _build_variants() -> Dict[str, Dict[str, Any]]:
    return {
        "fixed_baseline": {
            "backtest_type": "trade_simulation",
            "atr_period": 14,
            "init_stop_atr_k": 2.2,
            "trail_stop_mode": "percent",
            "trail_pct": 1.0,
            "trail_atr_k": 99.0,
            "breakeven_trigger_r": 999.0,
            "profit_lock_trigger_r": 999.0,
            "profit_lock_r": 0.0,
            "partial_take_profit_r": 999.0,
            "partial_take_ratio": 0.0,
            "time_stop_bars": 999,
        },
        "trailing_only": {
            "backtest_type": "trade_simulation",
            "atr_period": 14,
            "init_stop_atr_k": 2.2,
            "trail_stop_mode": "atr",
            "trail_atr_k": 3.0,
            "trail_pct": 0.08,
            "breakeven_trigger_r": 1.0,
            "profit_lock_trigger_r": 2.0,
            "profit_lock_r": 0.5,
            "partial_take_profit_r": 999.0,
            "partial_take_ratio": 0.0,
            "time_stop_bars": 15,
        },
        "trailing_partial": {
            "backtest_type": "trade_simulation",
            "atr_period": 14,
            "init_stop_atr_k": 2.2,
            "trail_stop_mode": "atr",
            "trail_atr_k": 3.0,
            "trail_pct": 0.08,
            "breakeven_trigger_r": 1.0,
            "profit_lock_trigger_r": 2.0,
            "profit_lock_r": 0.5,
            "partial_take_profit_r": 2.0,
            "partial_take_ratio": 0.4,
            "time_stop_bars": 15,
        },
    }


def _grid_values(mode: str) -> Dict[str, List[float]]:
    if mode == "quick":
        return {
            "trail_atr_k": [2.5, 3.0, 3.5],
            "profit_lock_r": [0.3, 0.5, 0.8],
            "partial_take_ratio": [0.3, 0.4, 0.5],
        }
    return {
        "trail_atr_k": [2.0, 2.5, 3.0, 3.5, 4.0],
        "profit_lock_r": [0.2, 0.3, 0.5, 0.8, 1.0],
        "partial_take_ratio": [0.2, 0.3, 0.4, 0.5, 0.6],
    }


def _score(summary: Dict[str, Any]) -> float:
    ret = _safe(summary.get("total_return_compound"))
    dd = abs(_safe(summary.get("max_drawdown")))
    return ret / (dd + 1e-9)


def _run_one(
    db,
    start_date: str,
    end_date: str,
    market: str,
    target_pct: float,
    horizon_days: int,
    min_score: float,
    cfg: Dict[str, Any],
) -> Dict[str, Any]:
    return run_gms_backtest(
        db=db,
        start_date=start_date,
        end_date=end_date,
        market=market,
        target_pct=target_pct,
        horizon_days=horizon_days,
        min_score=min_score,
        **cfg,
    )


def _select_best_cfg(
    db,
    base_cfg: Dict[str, Any],
    train_start: str,
    train_end: str,
    market: str,
    target_pct: float,
    horizon_days: int,
    min_score: float,
    grid_mode: str,
) -> Tuple[Dict[str, Any], float, int]:
    grid = _grid_values(grid_mode)
    best_cfg = dict(base_cfg)
    best_score = -1e18
    tested = 0
    for trail_atr_k in grid["trail_atr_k"]:
        for profit_lock_r in grid["profit_lock_r"]:
            cfg = dict(base_cfg)
            cfg["trail_atr_k"] = float(trail_atr_k)
            cfg["profit_lock_r"] = float(profit_lock_r)
            if cfg.get("partial_take_ratio", 0) > 0:
                for partial_take_ratio in grid["partial_take_ratio"]:
                    tested += 1
                    cfg2 = dict(cfg)
                    cfg2["partial_take_ratio"] = float(partial_take_ratio)
                    ret = _run_one(
                        db=db,
                        start_date=train_start,
                        end_date=train_end,
                        market=market,
                        target_pct=target_pct,
                        horizon_days=horizon_days,
                        min_score=min_score,
                        cfg=cfg2,
                    )
                    s = ret.get("summary", {})
                    trade_cnt = int(s.get("total_trades", 0) or 0)
                    if trade_cnt <= 0:
                        continue
                    sc = _score(s)
                    if sc > best_score:
                        best_score = sc
                        best_cfg = dict(cfg2)
            else:
                tested += 1
                ret = _run_one(
                    db=db,
                    start_date=train_start,
                    end_date=train_end,
                    market=market,
                    target_pct=target_pct,
                    horizon_days=horizon_days,
                    min_score=min_score,
                    cfg=cfg,
                )
                s = ret.get("summary", {})
                trade_cnt = int(s.get("total_trades", 0) or 0)
                if trade_cnt <= 0:
                    continue
                sc = _score(s)
                if sc > best_score:
                    best_score = sc
                    best_cfg = dict(cfg)

    if best_score <= -1e17:
        best_score = -999999.0
    return best_cfg, best_score, tested


def _gen_windows(
    start_date: str, end_date: str, train_months: int, valid_months: int, step_months: int
) -> List[Tuple[str, str, str, str]]:
    start_dt = _month_start(datetime.strptime(start_date, "%Y-%m-%d"))
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    windows: List[Tuple[str, str, str, str]] = []
    cur = start_dt
    while True:
        tr_s = cur
        tr_e = cur + relativedelta(months=train_months) - relativedelta(days=1)
        va_s = tr_e + relativedelta(days=1)
        va_e = va_s + relativedelta(months=valid_months) - relativedelta(days=1)
        if va_s > end_dt:
            break
        if va_e > end_dt:
            va_e = end_dt
        windows.append((_fmt(tr_s), _fmt(tr_e), _fmt(va_s), _fmt(va_e)))
        cur = cur + relativedelta(months=step_months)
        if cur > end_dt:
            break
    return windows


def main():
    parser = argparse.ArgumentParser(description="GMS 交易回测 Walk-forward 对比")
    parser.add_argument("--market", default="all", choices=["all", "cn", "hk"], help="市场")
    parser.add_argument("--start-date", required=True, help="起始日期 YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="结束日期 YYYY-MM-DD")
    parser.add_argument("--target-pct", type=float, default=0.05, help="目标涨幅比例，如 0.05")
    parser.add_argument("--horizon-days", type=int, default=20, help="持有窗口")
    parser.add_argument("--min-score", type=float, default=0.0, help="最低总分")
    parser.add_argument("--train-months", type=int, default=12, help="训练窗口（月）")
    parser.add_argument("--valid-months", type=int, default=3, help="验证窗口（月）")
    parser.add_argument("--step-months", type=int, default=3, help="滚动步长（月）")
    parser.add_argument(
        "--grid-mode",
        default="quick",
        choices=["quick", "full"],
        help="训练段网格强度：quick(较快)/full(较全)",
    )
    args = parser.parse_args()

    windows = _gen_windows(
        args.start_date, args.end_date, args.train_months, args.valid_months, args.step_months
    )
    if not windows:
        print("未生成有效窗口，请检查日期范围。")
        return

    variants = _build_variants()
    rows: List[Dict[str, Any]] = []
    db = SessionLocal()
    try:
        for idx, (tr_s, tr_e, va_s, va_e) in enumerate(windows, start=1):
            for name, cfg in variants.items():
                tuned_cfg = dict(cfg)
                train_score = None
                grid_tested = 0
                if name in ("trailing_only", "trailing_partial"):
                    tuned_cfg, train_score, grid_tested = _select_best_cfg(
                        db=db,
                        base_cfg=cfg,
                        train_start=tr_s,
                        train_end=tr_e,
                        market=args.market,
                        target_pct=args.target_pct,
                        horizon_days=args.horizon_days,
                        min_score=args.min_score,
                        grid_mode=args.grid_mode,
                    )

                ret = _run_one(
                    db=db,
                    start_date=va_s,
                    end_date=va_e,
                    market=args.market,
                    target_pct=args.target_pct,
                    horizon_days=args.horizon_days,
                    min_score=args.min_score,
                    cfg=tuned_cfg,
                )
                s = ret.get("summary", {})
                row = {
                    "window_idx": idx,
                    "train_start": tr_s,
                    "train_end": tr_e,
                    "valid_start": va_s,
                    "valid_end": va_e,
                    "variant": name,
                    "total_trades": int(s.get("total_trades", 0) or 0),
                    "win_rate": _safe(s.get("win_rate")),
                    "total_return_compound": _safe(s.get("total_return_compound")),
                    "max_drawdown": _safe(s.get("max_drawdown")),
                    "profit_factor": _safe(s.get("profit_factor")),
                    "avg_holding_bars": _safe(s.get("avg_holding_bars")),
                    "score": _score(s),
                    "train_score": train_score if train_score is not None else "",
                    "grid_tested": grid_tested,
                    "best_trail_atr_k": tuned_cfg.get("trail_atr_k"),
                    "best_profit_lock_r": tuned_cfg.get("profit_lock_r"),
                    "best_partial_take_ratio": tuned_cfg.get("partial_take_ratio"),
                }
                rows.append(row)
                print(
                    f"[W{idx}] {name:16s} train={tr_s}~{tr_e} valid={va_s}~{va_e} "
                    f"trades={row['total_trades']:4d} ret={row['total_return_compound']:.4f} "
                    f"dd={row['max_drawdown']:.4f} score={row['score']:.4f} "
                    f"grid={grid_tested} ta={row['best_trail_atr_k']} pl={row['best_profit_lock_r']} "
                    f"pt={row['best_partial_take_ratio']}"
                )
    finally:
        db.close()

    logs_dir = project_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = logs_dir / f"gms_walk_forward_eval_{ts}.csv"
    fields = [
        "window_idx",
        "train_start",
        "train_end",
        "valid_start",
        "valid_end",
        "variant",
        "total_trades",
        "win_rate",
        "total_return_compound",
        "max_drawdown",
        "profit_factor",
        "avg_holding_bars",
        "score",
        "train_score",
        "grid_tested",
        "best_trail_atr_k",
        "best_profit_lock_r",
        "best_partial_take_ratio",
    ]
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    print(f"\n已输出: {out_path}")


if __name__ == "__main__":
    main()

