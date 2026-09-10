# -*- coding: utf-8 -*-
"""
CSB 回测执行器（A 股）：
- 优先读 csb_signal_trace；缺失日补算
- 信号次日开盘入场
- exit_mode：hit_rate / risk_exit / structure_exit
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Sequence

from sqlalchemy import cast, String
from sqlalchemy.orm import Session

from .backtest_factor_report import (
    assign_score_buckets,
    build_factor_buckets,
    build_hit_rate_compare,
    enrich_detail_with_factors,
)
from .config import CSBConfigManager
from .data_loader import CSBDataLoader
from .defense_exit import evaluate_risk_exit_rules, evaluate_structure_exit_rules
from .strategy_engine import CSBStrategyEngine
from .trace_store import (
    dates_ready_for_universe_backtest,
    mark_date_scanned,
    query_buy_signals_for_date,
    upsert_trace_rows,
)

logger = logging.getLogger(__name__)


def resolve_target_pct_range(target_pct: Any = 0.10, target_pct_max: Any = None) -> tuple[float, float]:
    def _one(v: Any, default: float) -> float:
        try:
            x = float(v)
        except (TypeError, ValueError):
            return default
        return min(1.0, max(0.001, x))

    lo = _one(target_pct, 0.10)
    hi = _one(target_pct_max, lo) if target_pct_max is not None else lo
    if hi < lo:
        lo, hi = hi, lo
    return lo, hi


def classify_target_hits(*, entry_price: float, max_high: float, target_lo: float, target_hi: float) -> Dict[str, bool]:
    if entry_price <= 0:
        return {"hit_target": False, "hit_target_lower": False, "hit_target_upper": False, "hit_in_band": False}
    gain = max_high / entry_price - 1.0
    hit_lo = max_high >= entry_price * (1.0 + target_lo)
    hit_hi = max_high >= entry_price * (1.0 + target_hi)
    in_band = hit_lo if abs(target_hi - target_lo) < 1e-12 else (gain >= target_lo and gain <= target_hi)
    return {
        "hit_target": bool(hit_lo),
        "hit_target_lower": bool(hit_lo),
        "hit_target_upper": bool(hit_hi),
        "hit_in_band": bool(in_band),
    }


def _trading_dates(db: Session, start: str, end: str) -> List[str]:
    from backend_api.models import HistoricalQuotes

    rows = (
        db.query(HistoricalQuotes.date)
        .filter(
            cast(HistoricalQuotes.date, String) >= str(start)[:10],
            cast(HistoricalQuotes.date, String) <= str(end)[:10],
        )
        .distinct()
        .order_by(HistoricalQuotes.date)
        .all()
    )
    return [str(r[0])[:10] for r in rows if r[0]]


def _future_bars(db: Session, code: str, after_date: str, limit: int) -> List[Dict[str, Any]]:
    from backend_api.models import HistoricalQuotes

    rows = (
        db.query(
            HistoricalQuotes.date,
            HistoricalQuotes.open,
            HistoricalQuotes.high,
            HistoricalQuotes.low,
            HistoricalQuotes.close,
        )
        .filter(HistoricalQuotes.code == code, cast(HistoricalQuotes.date, String) > str(after_date)[:10])
        .order_by(HistoricalQuotes.date)
        .limit(int(limit))
        .all()
    )
    return [
        {
            "date": str(r[0])[:10],
            "open": float(r[1]) if r[1] is not None else None,
            "high": float(r[2]) if r[2] is not None else None,
            "low": float(r[3]) if r[3] is not None else None,
            "close": float(r[4]) if r[4] is not None else None,
        }
        for r in rows
    ]


def _ensure_trace_for_backtest_range(
    db: Session,
    *,
    dates: List[str],
    config_id: int,
    cfg: Dict[str, Any],
    loader: CSBDataLoader,
    engine: CSBStrategyEngine,
    stock_pool: Optional[List[str]],
    progress_cb: Optional[Callable[[int, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    progress_start: int = 0,
    progress_end: int = 50,
) -> Dict[str, Any]:
    covered = dates_ready_for_universe_backtest(
        db, config_id=config_id, dates=dates, stock_pool=stock_pool
    )
    missing = [d for d in dates if d not in covered]
    meta: Dict[str, Any] = {
        "range_days": len(dates),
        "already_covered": len(covered),
        "missing_before": len(missing),
    }
    if not missing:
        if progress_cb:
            progress_cb(progress_end, "预计算已覆盖回测区间")
        return meta

    stocks = loader.list_a_share_candidates(stock_codes=stock_pool)
    if stock_pool:
        allow = {str(c).strip().zfill(6) if str(c).strip().isdigit() else str(c).strip() for c in stock_pool}
        stocks = [(c, n) for c, n in stocks if c in allow]

    span = max(1, progress_end - progress_start)

    def _range_progress(done: int, total: int, msg: str) -> None:
        if progress_cb:
            pct = progress_start + int(span * done / max(1, total))
            progress_cb(min(progress_end - 1, pct), msg)

    hits_by_date, completed = engine.screen_universe_for_dates(
        stocks, missing, require_pass=True, progress_cb=_range_progress, cancel_check=cancel_check
    )
    hit_total = 0
    done = 0
    if completed:
        all_hits = [h for rows in hits_by_date.values() for h in rows]
        if all_hits:
            upsert_trace_rows(db, config_id=config_id, rows=all_hits)
            hit_total = len(all_hits)
        for d in missing:
            mark_date_scanned(
                db,
                config_id=config_id,
                trade_date=d,
                extra={"hits": len(hits_by_date.get(d) or []), "candidates": len(stocks), "scope": "pool" if stock_pool else "full_market"},
            )
            done += 1
    meta.update({"precomputed_days": done, "precompute_hits": hit_total, "range_scan_completed": completed})
    if progress_cb:
        progress_cb(progress_end, f"预计算补齐 {done} 日，买点 {hit_total} 条")
    return meta


def build_csb_trade_meta(
    *,
    target_pct: float,
    horizon_days: int,
    min_score: Optional[float],
    use_trace: bool,
    exit_mode: str,
    cfg: Dict[str, Any],
) -> Dict[str, Any]:
    mode = (exit_mode or "hit_rate").strip().lower()
    ms = float(min_score) if min_score is not None else float(cfg.get("min_score") or 60)
    tp = float(target_pct) * 100.0
    hz = int(horizon_days)
    dcfg = cfg.get("defense") or {}

    if mode == "structure_exit":
        summary = (
            f"CSB 结构出场：次日开盘入场；观察 {hz} 日；"
            f"假突破 {dcfg.get('false_break_days', 3)} 日 + 基准止损 + MA{dcfg.get('trail_ma', 20)} 跟踪；"
            f"同时统计 +{tp:.1f}% 命中；最低得分 {ms:.0f}。"
        )
    elif mode == "risk_exit":
        summary = f"CSB 纪律出场：次日开盘；观察 {hz} 日；基准/百分比止损；统计 +{tp:.1f}% 命中。"
    else:
        summary = f"CSB 命中率：次日开盘；观察 {hz} 日；+{tp:.1f}% 命中；不止损；最低得分 {ms:.0f}。"

    return {
        "risk_params": {"exit_mode": mode, "horizon_days": hz, "target_pct": target_pct},
        "trade_logic": {
            "summary": summary,
            "rules": [
                "信号：CSB BREAKOUT/PROBE 且得分 ≥ 门槛" + ("；读 csb_signal_trace。" if use_trace else "；实时扫描。"),
                "入场：信号次日开盘价。",
                f"观察期：{hz} 个交易日。",
            ],
        },
    }


def run_csb_backtest(
    db: Session,
    *,
    start_date: str,
    end_date: str,
    strategy_config_id: Optional[int] = None,
    target_pct: Optional[float] = None,
    target_pct_max: Optional[float] = None,
    horizon_days: Optional[int] = None,
    min_score: Optional[float] = None,
    use_trace: bool = True,
    stock_pool: Optional[List[str]] = None,
    exit_mode: str = "hit_rate",
    progress_cb: Optional[Callable[[int, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> Dict[str, Any]:
    mode = (exit_mode or "hit_rate").strip().lower()
    if mode not in ("hit_rate", "risk_exit", "structure_exit"):
        mode = "hit_rate"

    cm = CSBConfigManager()
    cm.ensure_default_row(db)
    cfg = cm.get_config(strategy_config_id, db=db)
    bt = cfg.get("backtest") or {}
    target_lo, target_hi = resolve_target_pct_range(
        target_pct if target_pct is not None else bt.get("target_pct", 0.10),
        target_pct_max,
    )
    hz = int(horizon_days if horizon_days is not None else bt.get("horizon_days", 10))
    if min_score is not None:
        cfg = cm.merge_overrides(cfg, min_score=min_score)

    resolved_id = strategy_config_id
    if resolved_id is None:
        from backend_api.models import CSBStrategyConfig

        row = (
            db.query(CSBStrategyConfig)
            .filter(CSBStrategyConfig.is_default.is_(True))
            .order_by(CSBStrategyConfig.id.asc())
            .first()
        )
        resolved_id = int(row.id) if row else None

    dates = _trading_dates(db, start_date, end_date)
    if not dates:
        return {"summary": {"total_signals": 0, "message": "区间内无交易日"}, "details": []}

    loader = CSBDataLoader(db)
    engine = CSBStrategyEngine(loader, cfg)
    pool = None
    if stock_pool:
        pool = [str(c).strip().zfill(6) if str(c).strip().isdigit() else str(c).strip() for c in stock_pool]

    precompute_meta: Dict[str, Any] = {}
    if use_trace and resolved_id is not None:
        try:
            precompute_meta = _ensure_trace_for_backtest_range(
                db,
                dates=dates,
                config_id=int(resolved_id),
                cfg=cfg,
                loader=loader,
                engine=engine,
                stock_pool=pool,
                progress_cb=progress_cb,
                cancel_check=cancel_check,
                progress_start=0,
                progress_end=45,
            )
        except Exception as e:
            logger.exception("CSB 回测预计算补齐失败: %s", e)
            precompute_meta = {"error": str(e)}

    details: List[Dict[str, Any]] = []
    cooldown: Dict[str, str] = {}
    use_trace_ok = bool(use_trace and resolved_id is not None)
    trade_start = 45 if use_trace_ok else 0

    for i, d in enumerate(dates):
        if cancel_check and cancel_check():
            break
        if progress_cb:
            pct = trade_start + int((100 - trade_start) * i / max(1, len(dates)))
            progress_cb(min(99, pct), f"扫描 {d}")

        signals: List[Dict[str, Any]] = []
        if use_trace_ok:
            try:
                signals = query_buy_signals_for_date(
                    db, trade_date=d, config_id=int(resolved_id), min_score=float(cfg.get("min_score") or 0)
                )
            except Exception:
                signals = []

        if not signals and use_trace_ok:
            covered = dates_ready_for_universe_backtest(db, config_id=int(resolved_id), dates=[d], stock_pool=pool)
            if d not in covered:
                stocks = loader.list_a_share_candidates(stock_codes=pool)
                day_hits = engine.screen(stocks, as_of_end_date=d, require_entry=True)
                signals = [h for h in day_hits if str(h.get("signal_date"))[:10] == d]
                try:
                    if signals:
                        upsert_trace_rows(db, config_id=int(resolved_id), rows=signals)
                    mark_date_scanned(db, config_id=int(resolved_id), trade_date=d, extra={"hits": len(signals)})
                except Exception as e:
                    logger.debug("CSB 当日落库失败 %s: %s", d, e)
        elif not use_trace_ok:
            stocks = loader.list_a_share_candidates(stock_codes=pool)
            signals = engine.screen(stocks, as_of_end_date=d, require_entry=True)

        if pool:
            allow = set(pool)
            signals = [s for s in signals if str(s.get("code")) in allow]

        for sig in signals:
            code = str(sig.get("code") or "")
            if not code:
                continue
            if code in cooldown:
                cd = str(cooldown[code])[:10]
                if cd and (d <= cd if mode == "hit_rate" else d < cd):
                    continue

            future = _future_bars(db, code, d, hz)
            if not future or not future[0].get("open") or float(future[0]["open"]) <= 0:
                continue
            entry_date = future[0]["date"]
            entry_price = float(future[0]["open"])
            target_lo_px = entry_price * (1.0 + target_lo)
            target_hi_px = entry_price * (1.0 + target_hi)

            max_high = entry_price
            hit_date = None
            for bar in future:
                hi = float(bar.get("high") or bar.get("close") or entry_price)
                max_high = max(max_high, hi)
                if hit_date is None and hi >= target_lo_px:
                    hit_date = bar.get("date")

            max_gain = max_high / entry_price - 1.0
            band = classify_target_hits(
                entry_price=entry_price, max_high=max_high, target_lo=target_lo, target_hi=target_hi
            )

            if mode == "hit_rate":
                last = future[-1]
                exit_price = float(last.get("close") or entry_price)
                exit_date = last.get("date") or entry_date
                pnl_pct = (exit_price - entry_price) / entry_price * 100.0
                row_out = {
                    "code": code,
                    "name": sig.get("name") or "",
                    "signal_date": d,
                    "signal_type": sig.get("signal_type"),
                    "score": sig.get("score"),
                    "entry_date": entry_date,
                    "entry_price": round(entry_price, 4),
                    "max_high": round(max_high, 4),
                    "max_gain_pct": round(max_gain * 100.0, 2),
                    **band,
                    "hit_date": hit_date,
                    "exit_date": exit_date,
                    "exit_price": round(exit_price, 4),
                    "exit_reason": "horizon_end",
                    "pnl_pct": round(pnl_pct, 2),
                    "bars_held": len(future),
                    "horizon_days": len(future),
                }
                enrich_detail_with_factors(row_out, sig, future, entry_price)
                details.append(row_out)
                cooldown[code] = str(future[-1].get("date") or entry_date)
                continue

            entry_low = sig.get("entry_low")
            channel_upper = sig.get("channel_upper")
            if mode == "structure_exit":
                exit_info = evaluate_structure_exit_rules(
                    entry_price=entry_price,
                    entry_low=entry_low,
                    channel_upper=channel_upper,
                    bars_after_entry=future,
                    signal_date=d,
                    config=cfg,
                )
            else:
                exit_info = evaluate_risk_exit_rules(
                    entry_price=entry_price,
                    entry_low=entry_low,
                    bars_after_entry=future,
                    config=cfg,
                )

            exit_price = float(exit_info.get("exit_price") or entry_price)
            exit_date = exit_info.get("exit_date") or entry_date
            pnl_pct = (exit_price - entry_price) / entry_price * 100.0
            cooldown[code] = str(exit_date)

            row_out = {
                "code": code,
                "name": sig.get("name") or "",
                "signal_date": d,
                "signal_type": sig.get("signal_type"),
                "score": sig.get("score"),
                "entry_date": entry_date,
                "entry_price": round(entry_price, 4),
                "exit_date": exit_date,
                "exit_price": round(exit_price, 4),
                "exit_reason": exit_info.get("exit_reason"),
                "max_high": round(max_high, 4),
                "max_gain_pct": round(max_gain * 100.0, 2),
                **band,
                "hit_date": hit_date,
                "pnl_pct": round(pnl_pct, 2),
                "bars_held": len([b for b in future if str(b.get("date") or "") <= str(exit_date)[:10]]),
                "entry_low": entry_low,
                "channel_upper": channel_upper,
            }
            enrich_detail_with_factors(row_out, sig, future, entry_price)
            details.append(row_out)

    total = len(details)
    hits = sum(1 for r in details if r.get("hit_target"))
    wins = sum(1 for r in details if float(r.get("pnl_pct") or 0) > 0)
    avg_pnl = sum(float(r.get("pnl_pct") or 0) for r in details) / total if total else 0.0
    avg_gain = sum(float(r.get("max_gain_pct") or 0) for r in details) / total if total else 0.0
    avg_bars = (
        float(hz) if mode == "hit_rate" else (sum(int(r.get("bars_held") or 0) for r in details) / total if total else 0.0)
    )

    trade_meta = build_csb_trade_meta(
        target_pct=target_lo,
        horizon_days=hz,
        min_score=cfg.get("min_score"),
        use_trace=use_trace_ok,
        exit_mode=mode,
        cfg=cfg,
    )

    summary_base = {
        "total_signals": total,
        "total_samples": total,
        "hit_count": hits,
        "hit_rate": round(hits / total, 4) if total else 0.0,
        "target_pct": target_lo,
        "target_pct_max": target_hi,
        "horizon_days": hz,
        "backtest_mode": "signal_hit_rate" if mode == "hit_rate" else mode,
        "exit_mode": mode,
        "start_date": start_date,
        "end_date": end_date,
        "strategy_config_id": resolved_id,
        "min_score": cfg.get("min_score"),
        "by_score_bucket": assign_score_buckets(details),
        "by_factor_bucket": build_factor_buckets(details),
        "risk_params": trade_meta["risk_params"],
        "trade_logic": trade_meta["trade_logic"],
        "precompute": precompute_meta or None,
        "avg_max_gain_pct": round(avg_gain, 2),
    }

    if mode == "hit_rate":
        summary = {**summary_base, "avg_bars_held": round(avg_bars, 2)}
    else:
        exit_dist: Dict[str, int] = {}
        for r in details:
            reason = str(r.get("exit_reason") or "unknown")
            exit_dist[reason] = exit_dist.get(reason, 0) + 1
        summary = {
            **summary_base,
            "win_count": wins,
            "win_rate": round(wins / total, 4) if total else 0.0,
            "avg_pnl_pct": round(avg_pnl, 2),
            "avg_bars_held": round(avg_bars, 2),
            "hit_rate_compare": build_hit_rate_compare(details, mode),
            "exit_reason_dist": exit_dist,
        }

    if progress_cb:
        progress_cb(100, "回测完成")
    return {"summary": summary, "details": details}
