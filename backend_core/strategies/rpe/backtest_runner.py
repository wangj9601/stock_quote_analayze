"""RPE 回测：命中率 + 结构破位交易模拟。"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List

from .backtest_storage import RPEBacktestStorage
from .config import RPEConfigManager
from .filters import structure_break
from .strategy_engine import RPEStrategyEngine

logger = logging.getLogger(__name__)


def run_rpe_backtest(task_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    storage = RPEBacktestStorage()
    storage.update_task(
        task_id, status="running", started_at=datetime.now(), progress=1, message="running"
    )
    try:
        cm = RPEConfigManager()
        strategy_cfg = cm.get_config(config.get("strategy_config_id"))
        engine = RPEStrategyEngine(config=strategy_cfg)
        start = str(config.get("start_date"))
        end = str(config.get("end_date"))
        horizon = int(
            config.get("horizon_days")
            or (strategy_cfg.get("backtest") or {}).get("horizon_days", 40)
        )
        target = float(
            config.get("target_relative_pct")
            or (strategy_cfg.get("backtest") or {}).get("target_relative_pct", 0.08)
        )
        bt_type = str(config.get("backtest_type") or "signal_hit_rate")
        board_code = config.get("board_code")
        max_boards = int(config.get("max_boards") or 15)
        date_step = max(1, int(config.get("date_step") or 5))

        # 采样交易日：取任一成分股日历
        boards = engine.loader.list_industry_boards(limit=max_boards)
        if board_code:
            boards = [b for b in boards if b["board_code"] == board_code] or [
                {"board_code": board_code, "board_name": board_code}
            ]
        if not boards:
            raise ValueError("no boards")

        sample_code = None
        members0 = engine.loader.load_board_members(boards[0]["board_code"])
        if members0:
            sample_code = members0[0]["code"]
        bars0 = engine.loader.load_bars(sample_code or "000001", end_date=end, limit=horizon + 200)
        sample_dates = [b["date"] for b in bars0 if start <= b["date"] <= end]

        samples: List[Dict] = []
        for di, d in enumerate(sample_dates[::date_step]):
            for b in boards[:max_boards]:
                rows = engine.screen_board(
                    b["board_code"],
                    b.get("board_name") or b["board_code"],
                    date=d,
                    config=strategy_cfg,
                    entry_only=True,
                )
                samples.extend(rows)
            if di % 3 == 0:
                storage.update_task(
                    task_id,
                    progress=min(10 + int(50 * di / max(1, len(sample_dates[::date_step]))), 60),
                    message=f"signals={len(samples)}",
                )

        if bt_type == "trade_simulation":
            summary = _simulate(engine, samples, horizon)
        else:
            summary = _hit_rate(engine, samples, horizon, target)

        storage.update_task(
            task_id,
            status="completed",
            progress=100,
            message="done",
            summary=summary,
            completed_at=datetime.now(),
        )
        return summary
    except Exception as e:
        logger.exception("RPE backtest failed: %s", e)
        storage.update_task(
            task_id, status="failed", error=str(e), message="failed", completed_at=datetime.now()
        )
        raise


def _hit_rate(engine, samples, horizon, target) -> Dict[str, Any]:
    hit = 0
    details = []
    for s in samples:
        bars = engine.loader.load_bars(s["code"], limit=horizon + 80)
        dates = [b["date"] for b in bars]
        if s["date"] not in dates:
            continue
        i = dates.index(s["date"])
        future = bars[i + 1 : i + 1 + horizon]
        entry = float(s.get("close") or 0)
        if entry <= 0 or not future:
            continue
        support = s.get("nearest_support")
        target_px = entry * (1 + target)
        hit_target = any(b["high"] >= target_px for b in future)
        breached = any(structure_break(b["close"], support) for b in future)
        ok = hit_target and not breached
        if ok:
            hit += 1
        details.append(
            {
                "code": s["code"],
                "date": s["date"],
                "hit_target": hit_target,
                "structure_break": breached,
                "ok": ok,
            }
        )
    total = len(details)
    return {
        "summary_schema_version": 1,
        "backtest_type": "signal_hit_rate",
        "total_samples": total,
        "hit_count": hit,
        "hit_rate": (hit / total) if total else 0.0,
        "details_preview": details[:50],
    }


def _simulate(engine, samples, horizon) -> Dict[str, Any]:
    trades = []
    equity = [1.0]
    wins = 0
    for s in samples:
        bars = engine.loader.load_bars(s["code"], limit=horizon + 80)
        dates = [b["date"] for b in bars]
        if s["date"] not in dates:
            continue
        i = dates.index(s["date"])
        if i + 1 >= len(bars):
            continue
        entry = float(bars[i + 1]["open"] or bars[i + 1]["close"])
        future = bars[i + 1 : i + 1 + horizon]
        support = s.get("nearest_support")
        resistance = s.get("nearest_resistance")
        exit_price = future[-1]["close"] if future else entry
        exit_reason = "horizon"
        for b in future:
            if structure_break(b["close"], support):
                exit_price = b["close"]
                exit_reason = "structure_break"
                break
            if resistance and b["high"] >= float(resistance):
                exit_price = float(resistance)
                exit_reason = "resistance"
                break
        ret = exit_price / entry - 1.0
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
    return {
        "summary_schema_version": 1,
        "backtest_type": "trade_simulation",
        "total_trades": n,
        "win_rate": (wins / n) if n else 0.0,
        "total_return": equity[-1] - 1.0 if equity else 0.0,
        "max_drawdown": max_dd,
        "equity_curve": equity[:200],
        "details_preview": trades[:50],
    }


def start_backtest_async(task_id: str, config: Dict[str, Any]) -> None:
    t = threading.Thread(target=run_rpe_backtest, args=(task_id, config), daemon=True)
    t.start()
