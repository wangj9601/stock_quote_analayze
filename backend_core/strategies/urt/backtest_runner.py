# -*- coding: utf-8 -*-
"""
URT 回测执行器（A 股）：
- 优先读 urt_signal_trace；区间内缺失日先按时间范围全市场（或股票池）补算一次
- 按交易日取买点信号；信号次日开盘入场
- 观察期目标判定对齐 GMS 命中率模式：观察期内最高价是否达到目标涨幅；
  不止损/不提前风控离场，持有满观察期；同标的观察期结束后才可再开仓
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import cast, String
from sqlalchemy.orm import Session

from .config import URTConfigManager
from .data_loader import URTDataLoader
from .strategy_engine import URTStrategyEngine
from .trace_store import (
    dates_ready_for_universe_backtest,
    mark_date_scanned,
    query_buy_signals_for_date,
    upsert_trace_rows,
)

logger = logging.getLogger(__name__)


def _ensure_trace_for_backtest_range(
    db: Session,
    *,
    dates: List[str],
    config_id: int,
    cfg: Dict[str, Any],
    loader: URTDataLoader,
    engine: URTStrategyEngine,
    stock_pool: Optional[List[str]],
    progress_cb: Optional[Callable[[int, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    progress_start: int = 0,
    progress_end: int = 50,
) -> Dict[str, Any]:
    """
    按回测时间范围补齐 urt_signal_trace：
    对尚未达到「全市场/股票池级」覆盖的交易日做扫描并落库。
    注意：仅有零星个股 trace（如强制重算）不算覆盖，必须重新全量扫描。
    扫描完成后始终写入 ``__URT_SCANNED__`` 占位，避免重复全量计算。
    """
    covered = dates_ready_for_universe_backtest(
        db, config_id=config_id, dates=dates, stock_pool=stock_pool
    )
    missing = [d for d in dates if d not in covered]
    meta: Dict[str, Any] = {
        "range_days": len(dates),
        "already_covered": len(covered),
        "precomputed_days": 0,
        "precompute_hits": 0,
        "missing_before": len(missing),
        "coverage_mode": "pool" if stock_pool else "full_market",
    }
    if not missing:
        if progress_cb:
            progress_cb(progress_end, "预计算数据已覆盖回测区间（全市场/股票池级）")
        return meta

    stocks = loader.list_a_share_candidates(stock_codes=stock_pool)
    if stock_pool:
        allow = set(stock_pool)
        stocks = [(c, n) for c, n in stocks if c in allow]
    pool_label = f"股票池 {len(stocks)} 只" if stock_pool else f"全市场 {len(stocks)} 只"
    logger.info(
        "URT 回测区间缺全量预计算 %s/%s 日，开始补算（%s）config_id=%s",
        len(missing),
        len(dates),
        pool_label,
        config_id,
    )

    hit_total = 0
    done = 0
    span = max(1, progress_end - progress_start)
    for j, d in enumerate(missing):
        if cancel_check and cancel_check():
            break
        if progress_cb:
            pct = progress_start + int(span * j / max(1, len(missing)))
            progress_cb(
                min(progress_end - 1, pct),
                f"补齐全市场预计算 {d}（{j + 1}/{len(missing)}，{pool_label}）",
            )
        try:
            day_hits = engine.screen_universe(stocks, as_of_end_date=d)
            day_hits = [h for h in day_hits if str(h.get("signal_date"))[:10] == d]
            if day_hits:
                upsert_trace_rows(db, config_id=config_id, rows=day_hits)
                hit_total += len(day_hits)
            # 无论是否有买点，都打扫描占位（全市场级覆盖标记）
            mark_date_scanned(
                db,
                config_id=config_id,
                trade_date=d,
                extra={
                    "hits": len(day_hits),
                    "candidates": len(stocks),
                    "scope": "pool" if stock_pool else "full_market",
                },
            )
            done += 1
        except Exception as e:
            logger.warning("URT 回测补算预计算失败 date=%s: %s", d, e)
            try:
                db.rollback()
            except Exception:
                pass

    meta["precomputed_days"] = done
    meta["precompute_hits"] = hit_total
    if progress_cb:
        progress_cb(
            progress_end,
            f"预计算补齐完成：新增 {done} 日，买点 {hit_total} 条",
        )
    return meta


def build_urt_trade_meta(
    *,
    target_pct: float = 0.10,
    horizon_days: int = 20,
    min_score: Optional[float] = None,
    use_trace: bool = True,
    risk: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """回测详情用：交易逻辑说明 + 风控参数快照。"""
    risk = dict(risk or {})
    stop_max = float(risk.get("stop_loss_pct_max") or 10)
    stop_min = float(risk.get("stop_loss_pct_min") or 5)
    time_stop_days = int(risk.get("time_stop_down_days") or 3)
    alert_min = float(risk.get("take_profit_alert_pct_min") or 25)
    alert_max = float(risk.get("take_profit_alert_pct_max") or 30)
    trail = float(risk.get("trailing_drawdown_pct") or 5)
    ms = float(min_score) if min_score is not None else 70.0
    tp = float(target_pct) * 100.0
    hz = int(horizon_days)

    risk_params = {
        "stop_loss_pct_min": stop_min,
        "stop_loss_pct_max": stop_max,
        "time_stop_down_days": time_stop_days,
        "take_profit_alert_pct_min": alert_min,
        "take_profit_alert_pct_max": alert_max,
        "trailing_drawdown_pct": trail,
    }

    trade_logic = {
        "summary": (
            f"URT 交易回测（对齐 GMS 命中率）：信号次日开盘入场；观察期 {hz} 个交易日；"
            f"以观察期内最高价判定是否达到目标涨幅 {tp:.1f}%；不止损；最低得分 {ms:.0f}。"
        ),
        "rules": [
            (
                "信号筛选：硬筛（站上均线、连阳规则 A/B、放量倍数等）通过，"
                f"且得分 ≥ {ms:.0f}；"
                + ("优先读取 urt_signal_trace 预计算买点。" if use_trace else "实时引擎扫描买点。")
            ),
            "入场：信号日之后下一交易日开盘价买入；开盘价无效则跳过。",
            f"观察期：自入场日起共 {hz} 根交易日 K 线（默认 20，与 GMS horizon_days 一致）。",
            (
                f"目标命中（不止损）：观察期内最高价 ≥ 入场价 × (1+{tp:.1f}%) 则 hit_target=是；"
                "同时记录观察期最高价与最大涨幅；不因浮亏/连跌/回撤提前离场。"
            ),
            f"到期平仓：持有满观察期，以最后一根 K 线收盘价作为参考出场价（horizon_end）。",
            "同标的去重：上一笔观察期结束日之前不再接受新信号开仓。",
            "参考盈亏 pnl_pct：按观察期末收盘价相对入场价计算；另输出 max_gain_pct（观察期最高价涨幅）。",
            (
                "说明：策略配置中的风控参数（止损/连跌/回撤）仅作文档参考，"
                f"本回测模式不启用（止损区间约 {stop_min:.0f}%–{stop_max:.0f}%，"
                f"连跌 {time_stop_days} 日、回撤止盈警惕 {alert_min:.0f}%–{alert_max:.0f}% / {trail:.0f}%）。"
            ),
        ],
        "exit_priority": [
            {
                "code": "target_hit",
                "label": "触及目标（统计）",
                "desc": f"观察期内最高价触及 +{tp:.1f}%（不止损、不提前平仓）",
            },
            {
                "code": "horizon_end",
                "label": "到期平仓",
                "desc": f"满 {hz} 个交易日以收盘价记作出场参考",
            },
        ],
    }
    return {"risk_params": risk_params, "trade_logic": trade_logic}


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

    # 全市场/大池：无预计算时先按时间范围补齐一次，再读 trace 做交易回测
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
            logger.exception("URT 回测预计算补齐失败: %s", e)
            precompute_meta = {"error": str(e)}

    details: List[Dict[str, Any]] = []
    cooldown: Dict[str, str] = {}  # code -> next allowed signal date
    trade_progress_start = 45 if (use_trace and resolved_id is not None) else 0

    for i, d in enumerate(dates):
        if cancel_check and cancel_check():
            break
        if progress_cb:
            pct = trade_progress_start + int(
                (100 - trade_progress_start) * i / max(1, len(dates))
            )
            progress_cb(min(99, pct), f"扫描交易日 {d}")

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

        need_realtime = False
        if not signals:
            if use_trace and resolved_id is not None:
                # 仅「全市场/池级」未覆盖时回退实时；零星个股 trace 不算覆盖
                covered = dates_ready_for_universe_backtest(
                    db,
                    config_id=int(resolved_id),
                    dates=[d],
                    stock_pool=pool,
                )
                need_realtime = d not in covered
            else:
                need_realtime = True

        if need_realtime:
            stocks = loader.list_a_share_candidates(stock_codes=pool)
            if pool:
                stocks = [(c, n) for c, n in stocks if c in set(pool)]
            day_hits = engine.screen_universe(stocks, as_of_end_date=d)
            signals = [h for h in day_hits if str(h.get("signal_date"))[:10] == d]
            if use_trace and resolved_id is not None:
                try:
                    if signals:
                        upsert_trace_rows(db, config_id=int(resolved_id), rows=signals)
                    mark_date_scanned(
                        db,
                        config_id=int(resolved_id),
                        trade_date=d,
                        extra={
                            "hits": len(signals),
                            "candidates": len(stocks),
                            "scope": "pool" if pool else "full_market",
                        },
                    )
                except Exception as e:
                    logger.debug("URT 回测当日落库失败 %s: %s", d, e)

        if pool:
            allow = set(pool)
            signals = [s for s in signals if str(s.get("code")) in allow]

        for sig in signals:
            code = str(sig.get("code") or "")
            if not code:
                continue
            if code in cooldown and d < cooldown[code]:
                continue
            # 与 GMS 一致：信号日之后 horizon_days 根 K 线为观察窗（首根为入场日）
            future = _future_bars(db, code, d, horizon_days)
            if not future or future[0].get("open") is None or float(future[0]["open"]) <= 0:
                continue
            entry_date = future[0]["date"]
            entry_price = float(future[0]["open"])
            target = entry_price * (1.0 + float(target_pct))

            max_high = entry_price
            hit = False
            hit_date = None
            for bar in future:
                hi = bar.get("high")
                if hi is None:
                    cl = bar.get("close")
                    hi = cl if cl is not None else entry_price
                hi_f = float(hi)
                if hi_f > max_high:
                    max_high = hi_f
                if (not hit) and hi_f >= target:
                    hit = True
                    hit_date = bar.get("date")

            max_gain = (max_high / entry_price - 1.0) if entry_price else 0.0
            # 不止损：持有满观察期，参考出场=末日收盘
            last = future[-1]
            exit_date = last.get("date") or entry_date
            exit_close = last.get("close")
            exit_price = float(exit_close) if exit_close is not None else entry_price
            exit_reason = "horizon_end"
            pnl_pct = (exit_price - entry_price) / entry_price * 100.0
            bars_held = len(future)
            # 去重窗口=完整观察期结束日（对齐 GMS block_until_obs_end）
            cooldown[code] = exit_date
            details.append(
                {
                    "code": code,
                    "name": sig.get("name") or "",
                    "signal_date": d,
                    "score": sig.get("score"),
                    "entry_date": entry_date,
                    "entry_price": round(entry_price, 4),
                    "exit_date": exit_date,
                    "exit_price": round(float(exit_price), 4),
                    "exit_reason": exit_reason,
                    "hit_target": hit,
                    "hit_date": hit_date,
                    "max_high": round(max_high, 4),
                    "max_gain_pct": round(max_gain * 100.0, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "bars_held": bars_held,
                }
            )

    total = len(details)
    hits = sum(1 for r in details if r.get("hit_target"))
    wins = sum(1 for r in details if float(r.get("pnl_pct") or 0) > 0)
    avg_pnl = sum(float(r.get("pnl_pct") or 0) for r in details) / total if total else 0.0
    avg_max_gain = (
        sum(float(r.get("max_gain_pct") or 0) for r in details) / total if total else 0.0
    )

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

    trade_meta = build_urt_trade_meta(
        target_pct=float(target_pct),
        horizon_days=int(horizon_days),
        min_score=cfg.get("min_score"),
        use_trace=bool(use_trace),
        risk=cfg.get("risk") if isinstance(cfg.get("risk"), dict) else {},
    )
    summary = {
        "total_signals": total,
        "total_samples": total,
        "target_hits": hits,
        "hit_count": hits,
        "hit_rate": round(hits / total, 4) if total else 0.0,
        "win_count": wins,
        "win_rate": round(wins / total, 4) if total else 0.0,
        "avg_pnl_pct": round(avg_pnl, 2),
        "avg_max_gain_pct": round(avg_max_gain, 2),
        "target_pct": target_pct,
        "horizon_days": horizon_days,
        "backtest_mode": "signal_hit_rate",
        "apply_stop_loss": False,
        "start_date": start_date,
        "end_date": end_date,
        "strategy_config_id": resolved_id,
        "min_score": cfg.get("min_score"),
        "by_score_bucket": by_score_bucket,
        "holding_days_histogram": holding_hist,
        "exit_reason_dist": exit_reason_dist,
        "monthly_returns": monthly_returns,
        "stock_pool_size": len(pool) if pool else None,
        "risk_params": trade_meta["risk_params"],
        "trade_logic": trade_meta["trade_logic"],
        "precompute": precompute_meta or None,
    }
    if progress_cb:
        progress_cb(100, "回测完成")
    return {"summary": summary, "details": details}
