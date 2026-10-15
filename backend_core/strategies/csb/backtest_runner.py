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

from sqlalchemy.orm import Session

from .backtest_factor_report import (
    assign_score_buckets,
    build_factor_buckets,
    build_hit_rate_compare,
    enrich_detail_with_factors,
)
from .config import BUY_SIGNAL_TYPES, CSB_PROBE, CSBConfigManager
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


def _signal_ref_price(sig: Dict[str, Any], *, upper: float, lower: float) -> Optional[float]:
    for key in ("close", "probe_price", "breakout_price", "lps_price", "entry_price"):
        try:
            v = float(sig.get(key))
        except (TypeError, ValueError):
            continue
        if v > 0:
            return v
    mid = (upper + lower) / 2.0
    return mid if mid > 0 else None


def _signal_channel_width_pct(sig: Dict[str, Any]) -> Optional[float]:
    """通道宽度 / 收盘价；字段不全时返回 None（不过滤）。"""
    try:
        upper = float(sig.get("channel_upper"))
        lower = float(sig.get("channel_lower"))
    except (TypeError, ValueError):
        return None
    if upper <= 0 or lower <= 0 or upper <= lower:
        return None
    px = _signal_ref_price(sig, upper=upper, lower=lower)
    if px is None or px <= 0:
        return None
    return (upper - lower) / px


def _signal_entry_pos_in_channel(sig: Dict[str, Any]) -> Optional[float]:
    """(价-下轨)/(上轨-下轨)；0=下轨，1=上轨；字段不全返回 None。"""
    try:
        upper = float(sig.get("channel_upper"))
        lower = float(sig.get("channel_lower"))
    except (TypeError, ValueError):
        return None
    if upper <= 0 or lower <= 0 or upper <= lower:
        return None
    px = _signal_ref_price(sig, upper=upper, lower=lower)
    if px is None:
        return None
    return (px - lower) / (upper - lower)


def build_zero_signal_diagnostics(
    *,
    total_signals: int,
    loaded_before_filter: int,
    kept_after_filter: int,
    type_counts_before_filter: Optional[Dict[str, int]] = None,
    allowed_signal_types: Optional[Sequence[str]] = None,
    precompute_hits: Optional[int] = None,
    min_score: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """预计算/读库有买点但最终交易信号为 0 时的诊断（写入 summary.zero_signal_hint）。"""
    if int(total_signals or 0) > 0:
        return None

    loaded = int(loaded_before_filter or 0)
    kept = int(kept_after_filter or 0)
    try:
        pc = int(precompute_hits) if precompute_hits is not None else None
    except (TypeError, ValueError):
        pc = None
    if loaded <= 0 and (pc is None or pc <= 0):
        return None

    type_counts = {
        str(k): int(v)
        for k, v in (type_counts_before_filter or {}).items()
        if str(k).strip()
    }
    allow = [str(x).strip() for x in (allowed_signal_types or []) if str(x).strip()]
    allow_set = set(allow)
    parts: List[str] = []

    if pc is not None and pc > 0 and loaded <= 0:
        parts.append(
            f"预计算命中 {pc} 笔，但回测阶段未读到可交易买点"
            f"（可能被股票池、日期覆盖或 min_score={min_score} 挡住）"
        )
    elif loaded > 0 and kept <= 0:
        if allow_set and type_counts:
            excluded = {k: v for k, v in type_counts.items() if k not in allow_set}
            included = {k: v for k, v in type_counts.items() if k in allow_set}
            if excluded and not included:
                excl_s = "、".join(f"{k}×{v}" for k, v in sorted(excluded.items()))
                allow_s = "、".join(allow)
                parts.append(
                    f"读到 {loaded} 笔买点（{excl_s}），但当前允许类型仅含 {allow_s}，"
                    f"过滤后为 0。可改预设/allowed_signal_types 纳入被排除类型，或换含 BREAKOUT/LPS 的区间"
                )
            elif excluded:
                excl_s = "、".join(f"{k}×{v}" for k, v in sorted(excluded.items()))
                parts.append(
                    f"读到 {loaded} 笔买点；其中 {excl_s} 不在允许类型内，"
                    f"其余经得分/回踩/通道等过滤后为 0"
                )
            else:
                parts.append(f"读到 {loaded} 笔买点，经得分/回踩/通道等过滤后为 0")
        else:
            parts.append(f"读到 {loaded} 笔买点，经过滤后为 0")
    elif kept > 0:
        parts.append(
            f"过滤后保留 {kept} 笔，但因冷却期/无次日开盘等原因未形成交易，最终信号为 0"
        )
    elif pc is not None and pc > 0:
        parts.append(f"预计算命中 {pc} 笔，最终交易信号为 0，请检查类型过滤与股票池")

    if not parts:
        return None

    return {
        "message": "；".join(parts),
        "loaded_before_filter": loaded,
        "kept_after_filter": kept,
        "type_counts_before_filter": type_counts,
        "allowed_signal_types": allow or None,
        "precompute_hits": pc,
        "min_score": min_score,
    }


def filter_backtest_signals(
    signals: Sequence[Dict[str, Any]],
    cfg: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """按 backtest 段过滤：类型/得分/回踩/通道宽/入场位置/单日上限。"""
    rows = [s for s in (signals or []) if isinstance(s, dict)]
    bt = (cfg or {}).get("backtest") if isinstance((cfg or {}).get("backtest"), dict) else {}
    bt = bt or {}

    allowed = bt.get("allowed_signal_types")
    allow_set = None
    if isinstance(allowed, (list, tuple, set)) and allowed:
        allow_set = {str(x).strip() for x in allowed if str(x).strip()}

    try:
        min_touch = int(bt.get("min_touch_count") or 0)
    except (TypeError, ValueError):
        min_touch = 0
    try:
        max_touch_raw = bt.get("max_touch_count")
        max_touch = int(max_touch_raw) if max_touch_raw not in (None, "") else 0
    except (TypeError, ValueError):
        max_touch = 0
    probe_min = bt.get("probe_min_score")
    try:
        probe_min_f = float(probe_min) if probe_min is not None and probe_min != "" else None
    except (TypeError, ValueError):
        probe_min_f = None
    try:
        min_width_raw = bt.get("min_channel_width_pct")
        min_width = float(min_width_raw) if min_width_raw not in (None, "") else 0.0
    except (TypeError, ValueError):
        min_width = 0.0
    min_pos_raw = bt.get("min_entry_pos_in_channel")
    min_pos: Optional[float]
    try:
        min_pos = float(min_pos_raw) if min_pos_raw not in (None, "") else None
    except (TypeError, ValueError):
        min_pos = None
    try:
        max_per_day = int(bt.get("max_signals_per_day") or 0)
    except (TypeError, ValueError):
        max_per_day = 0

    out: List[Dict[str, Any]] = []
    for s in rows:
        st = str(s.get("signal_type") or "").strip()
        if allow_set is not None and st not in allow_set:
            continue
        if st and st not in BUY_SIGNAL_TYPES and allow_set is None:
            continue
        try:
            touches = float(s.get("touch_count") or 0)
        except (TypeError, ValueError):
            touches = 0.0
        # 回踩门槛主要针对 PROBE；BREAKOUT/LPS 不因回踩数被挡
        if st == CSB_PROBE and min_touch > 0 and touches < float(min_touch):
            continue
        if st == CSB_PROBE and max_touch > 0 and touches > float(max_touch):
            continue
        if st == CSB_PROBE and probe_min_f is not None:
            try:
                sc = float(s.get("score") or 0)
            except (TypeError, ValueError):
                sc = 0.0
            if sc < probe_min_f:
                continue
        if min_width > 0:
            width = _signal_channel_width_pct(s)
            if width is not None and width < min_width:
                continue
        if min_pos is not None:
            pos = _signal_entry_pos_in_channel(s)
            if pos is not None and pos < float(min_pos):
                continue
        out.append(s)

    out.sort(key=lambda r: float(r.get("score") or 0), reverse=True)
    if max_per_day > 0:
        out = out[:max_per_day]
    return out


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


def _date_str(value: Any) -> str:
    """库内 date 多为 text(YYYY-MM-DD)，比较须用字符串，避免 text >= date。"""
    return str(value)[:10]


def _trading_dates(db: Session, start: str, end: str) -> List[str]:
    from backend_api.models import HistoricalQuotes

    rows = (
        db.query(HistoricalQuotes.date)
        .filter(
            HistoricalQuotes.date >= _date_str(start),
            HistoricalQuotes.date <= _date_str(end),
        )
        .distinct()
        .order_by(HistoricalQuotes.date)
        .all()
    )
    return [str(r[0])[:10] for r in rows if r[0]]


def _bars_from_rows(rows) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "date": str(r[0])[:10],
                "open": float(r[1]) if r[1] is not None else None,
                "high": float(r[2]) if r[2] is not None else None,
                "low": float(r[3]) if r[3] is not None else None,
                "close": float(r[4]) if r[4] is not None else None,
                "volume": float(r[5]) if r[5] is not None else None,
                "turnover_rate": float(r[6]) if r[6] is not None else None,
            }
        )
    return out


def _future_bars(db: Session, code: str, after_date: str, limit: int) -> List[Dict[str, Any]]:
    from backend_api.models import HistoricalQuotes

    rows = (
        db.query(
            HistoricalQuotes.date,
            HistoricalQuotes.open,
            HistoricalQuotes.high,
            HistoricalQuotes.low,
            HistoricalQuotes.close,
            HistoricalQuotes.volume,
            HistoricalQuotes.turnover_rate,
        )
        .filter(HistoricalQuotes.code == code, HistoricalQuotes.date > _date_str(after_date))
        .order_by(HistoricalQuotes.date)
        .limit(int(limit))
        .all()
    )
    return _bars_from_rows(rows)


def _prior_bars(db: Session, code: str, end_date: str, limit: int = 40) -> List[Dict[str, Any]]:
    """信号日及之前的 K 线，供 MA10/MA20 与派发量能比较。"""
    from backend_api.models import HistoricalQuotes

    rows = (
        db.query(
            HistoricalQuotes.date,
            HistoricalQuotes.open,
            HistoricalQuotes.high,
            HistoricalQuotes.low,
            HistoricalQuotes.close,
            HistoricalQuotes.volume,
            HistoricalQuotes.turnover_rate,
        )
        .filter(HistoricalQuotes.code == code, HistoricalQuotes.date <= _date_str(end_date))
        .order_by(HistoricalQuotes.date.desc())
        .limit(int(limit))
        .all()
    )
    return list(reversed(_bars_from_rows(rows)))


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
    stock_offset: int = 0,
    checkpoint_cb: Optional[Callable[[Dict[str, Any]], None]] = None,
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
    hit_total = 0

    def _range_progress(done: int, total: int, msg: str) -> None:
        if progress_cb:
            pct = progress_start + int(span * done / max(1, total))
            progress_cb(min(progress_end - 1, pct), msg)

    def _on_chunk(flat_hits: List[Dict[str, Any]], done_stocks: int, total: int) -> None:
        nonlocal hit_total
        if flat_hits:
            upsert_trace_rows(db, config_id=config_id, rows=flat_hits)
            hit_total += len(flat_hits)
        if checkpoint_cb:
            checkpoint_cb(
                {
                    "phase": "precompute",
                    "precompute_stock_offset": int(done_stocks),
                    "backtest_date_index": 0,
                    "cooldown": {},
                    "precompute_meta": {
                        **meta,
                        "precompute_hits": hit_total,
                        "range_scan_completed": False,
                        "stocks_total": total,
                    },
                }
            )

    hits_by_date, completed = engine.screen_universe_for_dates(
        stocks,
        missing,
        require_entry=True,
        progress_cb=_range_progress,
        cancel_check=cancel_check,
        stock_offset=stock_offset,
        chunk_hits_cb=_on_chunk,
    )
    done = 0
    if completed:
        for d in missing:
            mark_date_scanned(
                db,
                config_id=config_id,
                trade_date=d,
                extra={
                    "hits": len(hits_by_date.get(d) or []),
                    "candidates": len(stocks),
                    "scope": "pool" if stock_pool else "full_market",
                },
            )
            done += 1
    meta.update(
        {
            "precomputed_days": done,
            "precompute_hits": hit_total,
            "range_scan_completed": completed,
            "stock_offset_end": len(stocks) if completed else int(stock_offset or 0),
        }
    )
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
            f"BREAKOUT 假突破 {dcfg.get('false_break_days', 3)} 日；"
            f"PROBE 基准止损缓冲 "
            f"{float(dcfg.get('probe_stop_buffer_pct', 0.01)) * 100:.1f}% × "
            f"连续 {int(dcfg.get('probe_stop_confirm_days', 2))} 日；"
            f"通道失效下轨缓冲 "
            f"{float(dcfg.get('channel_fail_buffer_pct', 0.015)) * 100:.1f}% × "
            f"连续 {int(dcfg.get('channel_fail_confirm_days', 3))} 日；派发减仓 + "
            f"MA{dcfg.get('trail_ma_fast', 10)}/MA{dcfg.get('trail_ma', 20)} 阶梯跟踪；"
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
                "信号：CSB BREAKOUT/LPS/PROBE 且得分 ≥ 门槛" + ("；读 csb_signal_trace。" if use_trace else "；实时扫描。"),
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
    checkpoint: Optional[Dict[str, Any]] = None,
    checkpoint_cb: Optional[Callable[[Dict[str, Any]], None]] = None,
    initial_details: Optional[List[Dict[str, Any]]] = None,
    backtest_filters: Optional[Dict[str, Any]] = None,
    defense_overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    mode = (exit_mode or "hit_rate").strip().lower()
    if mode not in ("hit_rate", "risk_exit", "structure_exit"):
        mode = "hit_rate"

    cm = CSBConfigManager()
    cm.ensure_default_row(db)
    cfg = cm.get_config(strategy_config_id, db=db)
    bt = cfg.get("backtest") or {}
    if isinstance(backtest_filters, dict) and backtest_filters:
        cfg = cm.merge_overrides(cfg, backtest={k: v for k, v in backtest_filters.items() if v is not None})
        bt = cfg.get("backtest") or {}
    if isinstance(defense_overrides, dict) and defense_overrides:
        cfg = cm.merge_overrides(
            cfg, defense={k: v for k, v in defense_overrides.items() if v is not None}
        )
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

    cp = checkpoint if isinstance(checkpoint, dict) else {}
    cp_phase = str(cp.get("phase") or "")
    try:
        precompute_offset = int(cp.get("precompute_stock_offset") or 0)
    except (TypeError, ValueError):
        precompute_offset = 0
    try:
        date_start_index = int(cp.get("backtest_date_index") or 0)
    except (TypeError, ValueError):
        date_start_index = 0
    if cp_phase == "backtest":
        precompute_offset = 0
        date_start_index = max(0, min(len(dates), date_start_index))
    else:
        date_start_index = 0

    precompute_meta: Dict[str, Any] = {}
    if isinstance(cp.get("precompute_meta"), dict):
        precompute_meta = dict(cp.get("precompute_meta") or {})
    skip_precompute = cp_phase == "backtest"
    if use_trace and resolved_id is not None and not skip_precompute:
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
                stock_offset=precompute_offset,
                checkpoint_cb=checkpoint_cb,
            )
        except Exception as e:
            logger.exception("CSB 回测预计算补齐失败: %s", e)
            precompute_meta = {"error": str(e)}
        if cancel_check and cancel_check():
            return {
                "summary": {"cancelled": True, "precompute": precompute_meta},
                "details": list(initial_details or []),
                "paused_or_cancelled": True,
            }

    details: List[Dict[str, Any]] = initial_details if initial_details is not None else []
    cooldown: Dict[str, str] = {}
    if isinstance(cp.get("cooldown"), dict):
        cooldown = {str(k): str(v)[:10] for k, v in (cp.get("cooldown") or {}).items()}
    use_trace_ok = bool(use_trace and resolved_id is not None)
    trade_start = 45 if use_trace_ok else 0

    loaded_before_filter = 0
    kept_after_filter = 0
    type_counts_before_filter: Dict[str, int] = {}

    for i, d in enumerate(dates):
        if i < date_start_index:
            continue
        if cancel_check and cancel_check():
            if checkpoint_cb:
                checkpoint_cb(
                    {
                        "phase": "backtest",
                        "precompute_stock_offset": 0,
                        "backtest_date_index": i,
                        "cooldown": cooldown,
                        "precompute_meta": precompute_meta,
                    }
                )
            return {
                "summary": {"cancelled": True, "precompute": precompute_meta},
                "details": details,
                "paused_or_cancelled": True,
            }
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
                    # 须带 scope/candidates，否则 dates_ready 不认「已全市场扫描」的空买点日
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
                    logger.debug("CSB 当日落库失败 %s: %s", d, e)
        elif not use_trace_ok:
            stocks = loader.list_a_share_candidates(stock_codes=pool)
            signals = engine.screen(stocks, as_of_end_date=d, require_entry=True)

        if pool:
            allow = set(pool)
            signals = [s for s in signals if str(s.get("code")) in allow]

        for s in signals:
            st = str(s.get("signal_type") or "").strip() or "UNKNOWN"
            type_counts_before_filter[st] = type_counts_before_filter.get(st, 0) + 1
        loaded_before_filter += len(signals)

        signals = filter_backtest_signals(signals, cfg)
        kept_after_filter += len(signals)

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
            channel_lower = sig.get("channel_lower")
            if mode == "structure_exit":
                exit_info = evaluate_structure_exit_rules(
                    entry_price=entry_price,
                    entry_low=entry_low,
                    channel_upper=channel_upper,
                    bars_after_entry=future,
                    signal_date=d,
                    config=cfg,
                    prior_bars=_prior_bars(db, code, d, 40),
                    signal_type=str(sig.get("signal_type") or ""),
                    channel_lower=channel_lower,
                )
            else:
                exit_info = evaluate_risk_exit_rules(
                    entry_price=entry_price,
                    entry_low=entry_low,
                    bars_after_entry=future,
                    config=cfg,
                    signal_date=d,
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

        if checkpoint_cb:
            checkpoint_cb(
                {
                    "phase": "backtest",
                    "precompute_stock_offset": 0,
                    "backtest_date_index": i + 1,
                    "cooldown": cooldown,
                    "precompute_meta": precompute_meta,
                }
            )

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

    bt_cfg = cfg.get("backtest") if isinstance(cfg.get("backtest"), dict) else {}
    allowed_types = bt_cfg.get("allowed_signal_types") if isinstance(bt_cfg, dict) else None
    pc_hits = None
    if isinstance(precompute_meta, dict):
        raw_hits = precompute_meta.get("hits")
        if raw_hits is None:
            raw_hits = precompute_meta.get("precompute_hits")
        try:
            pc_hits = int(raw_hits) if raw_hits is not None else None
        except (TypeError, ValueError):
            pc_hits = None

    zero_hint = build_zero_signal_diagnostics(
        total_signals=total,
        loaded_before_filter=loaded_before_filter,
        kept_after_filter=kept_after_filter,
        type_counts_before_filter=type_counts_before_filter,
        allowed_signal_types=allowed_types if isinstance(allowed_types, (list, tuple, set)) else None,
        precompute_hits=pc_hits,
        min_score=cfg.get("min_score"),
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
        "filter_diagnostics": {
            "loaded_before_filter": loaded_before_filter,
            "kept_after_filter": kept_after_filter,
            "type_counts_before_filter": type_counts_before_filter,
            "allowed_signal_types": (
                [str(x) for x in allowed_types] if isinstance(allowed_types, (list, tuple, set)) else None
            ),
        },
        "zero_signal_hint": zero_hint,
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
