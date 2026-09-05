"""SBBR 回测：命中率 + 交易模拟。"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .backtest_storage import SBBRBacktestStorage
from .config import SBBRConfigManager
from .data_loader import SBBRDataLoader
from .defense_exit import calc_defense_band, evaluate_exit_factors
from .strategy_engine import SBBRStrategyEngine

logger = logging.getLogger(__name__)


def _parse_date(s: str):
    return datetime.strptime(s[:10], "%Y-%m-%d").date()


def run_sbbr_backtest(task_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    storage = SBBRBacktestStorage()
    storage.update_task(
        task_id,
        status="running",
        started_at=datetime.now(),
        progress=1,
        message="running",
    )
    try:
        cm = SBBRConfigManager()
        strategy_cfg = cm.get_config(config.get("strategy_config_id"))
        engine = SBBRStrategyEngine(config=strategy_cfg)
        loader = engine.loader

        start = str(config.get("start_date"))
        end = str(config.get("end_date"))
        horizon = int(config.get("horizon_days") or (strategy_cfg.get("backtest") or {}).get("horizon_days", 60))
        target_pct = float(config.get("target_pct") or (strategy_cfg.get("backtest") or {}).get("target_pct", 0.5))
        bt_type = str(config.get("backtest_type") or "signal_hit_rate")
        pool = config.get("stock_pool") or []

        if pool:
            codes = [str(c) for c in pool]
        else:
            uni = loader.build_size_universe(strategy_cfg, trade_date=end)
            codes = [u["code"] for u in uni[: int(config.get("universe_limit") or 80)]]

        # 采样交易日：按 end 往前取 bars 的日期集合近似
        sample_dates: List[str] = []
        if codes:
            bars0 = loader.load_bars(codes[0], end_date=end, limit=horizon + 120)
            sample_dates = [
                b["date"]
                for b in bars0
                if start <= b["date"] <= end
            ]

        storage.update_task(task_id, progress=10, message=f"codes={len(codes)} dates={len(sample_dates)}")

        samples = []
        # 为控制耗时，每隔若干日采样
        step = max(1, int(config.get("date_step") or 5))
        for di, d in enumerate(sample_dates[::step]):
            for code in codes:
                row = engine.evaluate_code(code, date=d, config=strategy_cfg)
                if not row or not row.get("entry_signal"):
                    continue
                samples.append(row)
            if di % 5 == 0:
                pct = 10 + int(50 * di / max(1, len(sample_dates[::step])))
                storage.update_task(
                    task_id,
                    progress=min(pct, 60),
                    message=f"entry_count={len(samples)}",
                )

        entry_count = len(samples)
        scope_meta = config.get("scope_meta") or {
            "stock_pool_mode": config.get("stock_pool_mode") or ("stocks" if pool else "market"),
            "stock_count": len(codes),
            "universe_limit": config.get("universe_limit"),
        }

        if bt_type == "trade_simulation":
            summary = _simulate_trades(loader, samples, horizon, target_pct, strategy_cfg)
        else:
            summary = _hit_rate(loader, samples, horizon, target_pct, strategy_cfg)

        summary["entry_count"] = entry_count
        summary["scope_meta"] = scope_meta
        summary["stock_pool_mode"] = scope_meta.get("stock_pool_mode")
        summary["universe_size"] = len(codes)

        storage.update_task(
            task_id,
            status="completed",
            progress=100,
            message=f"done entry={entry_count}",
            summary=summary,
            completed_at=datetime.now(),
        )
        return summary
    except Exception as e:
        logger.exception("SBBR backtest failed: %s", e)
        storage.update_task(
            task_id,
            status="failed",
            error=str(e),
            message="failed",
            completed_at=datetime.now(),
        )
        raise


def _hit_rate(loader, samples, horizon, target_pct, cfg) -> Dict[str, Any]:
    hit = 0
    details = []
    for s in samples:
        bars = loader.load_bars(s["code"], end_date=None, limit=horizon + 80)
        # find index of signal date
        dates = [b["date"] for b in bars]
        if s["date"] not in dates:
            continue
        i = dates.index(s["date"])
        future = bars[i + 1 : i + 1 + horizon]
        entry = float(s.get("close") or 0)
        if entry <= 0 or not future:
            continue
        target = entry * (1 + target_pct)
        defense_low = s.get("defense_low") or (entry * 0.97)
        hit_target = any(b["high"] >= target for b in future)
        breached = any(b["close"] < defense_low for b in future)
        ok = hit_target and not breached
        if ok:
            hit += 1
        details.append(
            {
                "code": s["code"],
                "date": s["date"],
                "hit_target": hit_target,
                "defense_breached": breached,
                "ok": ok,
            }
        )
    total = len(details)
    entry_count = len(samples)
    return {
        "summary_schema_version": 1,
        "backtest_type": "signal_hit_rate",
        "entry_count": entry_count,
        "total_samples": total,
        "hit_count": hit,
        "hit_rate": (hit / total) if total else 0.0,
        "target_pct": target_pct,
        "horizon_days": horizon,
        "details_preview": details[:50],
    }


def _simulate_trades(loader, samples, horizon, target_pct, cfg) -> Dict[str, Any]:
    trades = []
    equity = [1.0]
    wins = 0
    for s in samples:
        bars = loader.load_bars(s["code"], end_date=None, limit=horizon + 80)
        dates = [b["date"] for b in bars]
        if s["date"] not in dates:
            continue
        i = dates.index(s["date"])
        if i + 1 >= len(bars):
            continue
        # T+1 open
        entry = float(bars[i + 1]["open"] or bars[i + 1]["close"])
        future = bars[i + 1 : i + 1 + horizon]
        defense_low = s.get("defense_low") or entry * 0.97
        exit_price = future[-1]["close"] if future else entry
        exit_reason = "horizon"
        for b in future:
            if b["close"] < defense_low:
                exit_price = b["close"]
                exit_reason = "defense"
                break
            if b["high"] >= entry * (1 + target_pct):
                exit_price = entry * (1 + target_pct)
                exit_reason = "target"
                break
            exit_info = evaluate_exit_factors(
                bars[: dates.index(b["date"]) + 1],
                entry_price=entry,
                config=cfg,
            )
            if exit_info.get("all_ok"):
                exit_price = b["close"]
                exit_reason = "three_factors"
                break

        # 五·三·二简化：80% 仓位参与
        alloc = 0.8
        ret = (exit_price / entry - 1.0) * alloc
        equity.append(equity[-1] * (1 + ret))
        if ret > 0:
            wins += 1
        trades.append(
            {
                "code": s["code"],
                "signal_date": s["date"],
                "entry": entry,
                "exit": exit_price,
                "return": ret,
                "exit_reason": exit_reason,
            }
        )

    peak = equity[0]
    max_dd = 0.0
    for v in equity:
        peak = max(peak, v)
        if peak > 0:
            max_dd = max(max_dd, (peak - v) / peak)

    n = len(trades)
    entry_count = len(samples)
    return {
        "summary_schema_version": 1,
        "backtest_type": "trade_simulation",
        "entry_count": entry_count,
        "total_trades": n,
        "win_rate": (wins / n) if n else 0.0,
        "total_return": equity[-1] - 1.0 if equity else 0.0,
        "max_drawdown": max_dd,
        "equity_curve": equity[:200],
        "by_exit_reason": _count_by(trades, "exit_reason"),
        "details_preview": trades[:50],
    }


def _count_by(rows: List[Dict], key: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for r in rows:
        k = str(r.get(key) or "")
        out[k] = out.get(k, 0) + 1
    return out


def start_backtest_async(task_id: str, config: Dict[str, Any]) -> None:
    t = threading.Thread(target=run_sbbr_backtest, args=(task_id, config), daemon=True)
    t.start()
