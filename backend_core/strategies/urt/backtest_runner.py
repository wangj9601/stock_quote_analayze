# -*- coding: utf-8 -*-
"""
URT 回测执行器（A 股）：
- 按交易日扫描信号（实时引擎或 urt_signal_trace）
- 次日开盘入场
- 观察期内：触达 target_pct 记命中；或按 evaluate_exit_rules 离场算盈亏
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import cast, String
from sqlalchemy.orm import Session

from .config import URTConfigManager
from .data_loader import URTDataLoader
from .signal_detector import evaluate_exit_rules
from .strategy_engine import URTStrategyEngine
from .trace_store import query_buy_signals_for_date

logger = logging.getLogger(__name__)


def _trading_dates(db: Session, start: str, end: str) -> List[str]:
    from backend_api.models import HistoricalQuotes

    start_s, end_s = str(start)[:10], str(end)[:10]
    rows = (
        db.query(HistoricalQuotes.date)
        .filter(
            cast(HistoricalQuotes.date, String) >= start_s,
            cast(HistoricalQuotes.date, String) <= end_s,
        )
        .distinct()
        .order_by(HistoricalQuotes.date)
        .all()
    )
    return [str(r[0])[:10] for r in rows if r[0]]


def _next_open(db: Session, code: str, signal_date: str) -> Optional[Dict[str, Any]]:
    from backend_api.models import HistoricalQuotes

    after = str(signal_date)[:10]
    row = (
        db.query(HistoricalQuotes.date, HistoricalQuotes.open, HistoricalQuotes.close, HistoricalQuotes.high)
        .filter(HistoricalQuotes.code == code, cast(HistoricalQuotes.date, String) > after)
        .order_by(HistoricalQuotes.date)
        .first()
    )
    if not row or row[1] is None:
        return None
    return {
        "date": str(row[0])[:10],
        "open": float(row[1]),
        "close": float(row[2]) if row[2] is not None else float(row[1]),
        "high": float(row[3]) if row[3] is not None else float(row[1]),
    }


def _future_bars(db: Session, code: str, after_date: str, limit: int) -> List[Dict[str, Any]]:
    from backend_api.models import HistoricalQuotes

    after = str(after_date)[:10]
    rows = (
        db.query(
            HistoricalQuotes.date,
            HistoricalQuotes.open,
            HistoricalQuotes.high,
            HistoricalQuotes.low,
            HistoricalQuotes.close,
        )
        .filter(HistoricalQuotes.code == code, cast(HistoricalQuotes.date, String) > after)
        .order_by(HistoricalQuotes.date)
        .limit(int(limit))
        .all()
    )
    out = []
    for r in rows:
        out.append(
            {
                "date": str(r[0])[:10],
                "open": float(r[1]) if r[1] is not None else None,
                "high": float(r[2]) if r[2] is not None else None,
                "low": float(r[3]) if r[3] is not None else None,
                "close": float(r[4]) if r[4] is not None else None,
            }
        )
    return out


def run_urt_backtest(
    db: Session,
    *,
    start_date: str,
    end_date: str,
    strategy_config_id: Optional[int] = None,
    target_pct: float = 0.10,
    horizon_days: int = 20,
    min_score: Optional[float] = None,
    use_trace: bool = True,
    stock_pool: Optional[List[str]] = None,
    progress_cb: Optional[Callable[[int, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> Dict[str, Any]:
    cm = URTConfigManager()
    cm.ensure_default_row(db)
    cfg = cm.get_config(strategy_config_id, db=db)
    if min_score is not None:
        cfg = cm.merge_overrides(cfg, min_score=min_score)

    resolved_id = strategy_config_id
    if resolved_id is None:
        from backend_api.models import URTStrategyConfig

        row = (
            db.query(URTStrategyConfig)
            .filter(URTStrategyConfig.is_default.is_(True))
            .order_by(URTStrategyConfig.id.asc())
            .first()
        )
        resolved_id = int(row.id) if row else None

    dates = _trading_dates(db, start_date, end_date)
    if not dates:
        return {
            "summary": {"total_signals": 0, "message": "区间内无交易日"},
            "details": [],
        }

    loader = URTDataLoader(db)
    engine = URTStrategyEngine(loader, cfg)
    pool = None
    if stock_pool:
        pool = [str(c).strip().zfill(6) if str(c).strip().isdigit() else str(c).strip() for c in stock_pool]

    details: List[Dict[str, Any]] = []
    cooldown: Dict[str, str] = {}  # code -> next allowed signal date

    for i, d in enumerate(dates):
        if cancel_check and cancel_check():
            break
        if progress_cb:
            progress_cb(int(100 * i / max(1, len(dates))), f"扫描交易日 {d}")

        signals: List[Dict[str, Any]] = []
        if use_trace and resolved_id is not None:
            try:
                signals = query_buy_signals_for_date(
                    db,
                    trade_date=d,
                    config_id=resolved_id,
                    min_score=float(cfg.get("min_score") or 70),
                )
            except Exception:
                signals = []
        if not signals:
            stocks = loader.list_a_share_candidates(stock_codes=pool)
            if pool:
                stocks = [(c, n) for c, n in stocks if c in set(pool)]
            # 仅限当天附近扫描：用引擎对候选筛（可能较慢，回测建议先预计算）
            if len(stocks) > 800 and not pool:
                # 无 trace 且全市场过慢时跳过实时
                continue
            day_hits = engine.screen_universe(stocks, as_of_end_date=d)
            signals = [h for h in day_hits if str(h.get("signal_date"))[:10] == d]

        if pool:
            allow = set(pool)
            signals = [s for s in signals if str(s.get("code")) in allow]

        for sig in signals:
            code = str(sig.get("code") or "")
            if not code:
                continue
            if code in cooldown and d < cooldown[code]:
                continue
            entry = _next_open(db, code, d)
            if not entry or entry["open"] <= 0:
                continue
            entry_price = float(entry["open"])
            future = _future_bars(db, code, entry["date"], horizon_days)
            # 含入场日：把入场日后的 bars 作为观察
            target = entry_price * (1.0 + float(target_pct))
            hit = False
            hit_date = None
            exit_reason = "horizon_end"
            exit_price = entry_price
            exit_date = entry["date"]
            peak = entry_price
            closes: List[float] = [entry_price]

            for bar in future:
                if bar.get("close") is None:
                    continue
                cl = float(bar["close"])
                hi = float(bar["high"] or cl)
                peak = max(peak, hi)
                closes.append(cl)
                if hi >= target:
                    hit = True
                    hit_date = bar["date"]
                    exit_reason = "target_hit"
                    exit_price = target
                    exit_date = bar["date"]
                    break
                exit_ev = evaluate_exit_rules(
                    entry_price=entry_price,
                    closes=closes,
                    peak_price=peak,
                    cfg=cfg,
                )
                if exit_ev:
                    exit_reason = exit_ev.get("exit_reason") or "rule_exit"
                    exit_price = cl
                    exit_date = bar["date"]
                    break
            else:
                if future and future[-1].get("close") is not None:
                    exit_price = float(future[-1]["close"])
                    exit_date = future[-1]["date"]

            pnl_pct = (exit_price - entry_price) / entry_price * 100.0
            bars_held = 0
            for bar in future:
                bars_held += 1
                if bar.get("date") == exit_date:
                    break
            if bars_held <= 0:
                bars_held = 1
            cooldown[code] = exit_date
            details.append(
                {
                    "code": code,
                    "name": sig.get("name") or "",
                    "signal_date": d,
                    "score": sig.get("score"),
                    "entry_date": entry["date"],
                    "entry_price": round(entry_price, 4),
                    "exit_date": exit_date,
                    "exit_price": round(float(exit_price), 4),
                    "exit_reason": exit_reason,
                    "hit_target": hit,
                    "hit_date": hit_date,
                    "pnl_pct": round(pnl_pct, 2),
                    "bars_held": bars_held,
                }
            )

    total = len(details)
    hits = sum(1 for r in details if r.get("hit_target"))
    wins = sum(1 for r in details if float(r.get("pnl_pct") or 0) > 0)
    avg_pnl = sum(float(r.get("pnl_pct") or 0) for r in details) / total if total else 0.0

    by_score_bucket: Dict[str, Dict[str, Any]] = {}
    for r in details:
        s = r.get("score")
        try:
            sv = float(s) if s is not None else None
        except (TypeError, ValueError):
            sv = None
        if sv is None:
            bucket = "未知"
        elif sv < 60:
            bucket = "[0,60)"
        elif sv < 70:
            bucket = "[60,70)"
        elif sv < 80:
            bucket = "[70,80)"
        elif sv < 90:
            bucket = "[80,90)"
        else:
            bucket = "[90,100]"
        if bucket not in by_score_bucket:
            by_score_bucket[bucket] = {"total": 0, "hit": 0}
        by_score_bucket[bucket]["total"] += 1
        if r.get("hit_target"):
            by_score_bucket[bucket]["hit"] += 1
    for v in by_score_bucket.values():
        v["hit_rate"] = round(v["hit"] / v["total"], 4) if v["total"] else 0.0

    holding_hist = {"1-3": 0, "4-10": 0, "11-20": 0, "21+": 0}
    for r in details:
        bars = int(r.get("bars_held") or 0)
        if bars <= 3:
            holding_hist["1-3"] += 1
        elif bars <= 10:
            holding_hist["4-10"] += 1
        elif bars <= 20:
            holding_hist["11-20"] += 1
        else:
            holding_hist["21+"] += 1

    exit_reason_dist: Dict[str, int] = {}
    for r in details:
        reason = str(r.get("exit_reason") or "unknown")
        exit_reason_dist[reason] = exit_reason_dist.get(reason, 0) + 1

    # 分月收益：按出场月汇总 pnl_pct 均值（简化）
    monthly_map: Dict[str, List[float]] = {}
    for r in details:
        ed = str(r.get("exit_date") or "")[:7]
        if not ed:
            continue
        monthly_map.setdefault(ed, []).append(float(r.get("pnl_pct") or 0))
    monthly_returns = [
        {"month": m, "return_pct": round(sum(vs) / len(vs), 2), "count": len(vs)}
        for m, vs in sorted(monthly_map.items())
    ]

    summary = {
        "total_signals": total,
        "total_samples": total,
        "target_hits": hits,
        "hit_count": hits,
        "hit_rate": round(hits / total, 4) if total else 0.0,
        "win_count": wins,
        "win_rate": round(wins / total, 4) if total else 0.0,
        "avg_pnl_pct": round(avg_pnl, 2),
        "target_pct": target_pct,
        "horizon_days": horizon_days,
        "start_date": start_date,
        "end_date": end_date,
        "strategy_config_id": resolved_id,
        "min_score": cfg.get("min_score"),
        "by_score_bucket": by_score_bucket,
        "holding_days_histogram": holding_hist,
        "exit_reason_dist": exit_reason_dist,
        "monthly_returns": monthly_returns,
        "stock_pool_size": len(pool) if pool else None,
    }
    if progress_cb:
        progress_cb(100, "回测完成")
    return {"summary": summary, "details": details}
