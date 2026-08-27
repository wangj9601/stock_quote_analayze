# -*- coding: utf-8 -*-
"""
URT 回测执行器（A 股）：
- 优先读 urt_signal_trace；区间内缺失日先按时间范围全市场（或股票池）补算一次
- 按交易日取买点信号；信号次日开盘入场
- exit_mode：hit_rate（命中率不止损）/ risk_exit（百分比纪律）/ structure_exit（信号日 KDE 支撑止损、阻力止盈）
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Sequence

from sqlalchemy import cast, String
from sqlalchemy.orm import Session

from .config import URTConfigManager
from .data_loader import URTDataLoader
from .strategy_engine import URTStrategyEngine
from .backtest_factor_report import (
    assign_score_buckets,
    build_factor_buckets,
    build_hit_rate_compare,
    enrich_detail_with_factors,
)
from .signal_filters import (
    build_signal_filter_from_cfg,
    passes_signal_factor_filter,
    signal_quality_mode_label,
)
from .trace_store import (
    dates_ready_for_universe_backtest,
    mark_date_scanned,
    query_buy_signals_for_date,
    upsert_trace_rows,
)

logger = logging.getLogger(__name__)


def resolve_target_pct_range(
    target_pct: Any = 0.10,
    target_pct_max: Any = None,
) -> tuple[float, float]:
    """目标涨幅区间（小数）。缺省上限=下限；裁剪到 0.1%～100%；上下限颠倒则交换。"""

    def _one(v: Any, default: float) -> float:
        try:
            x = float(v)
        except (TypeError, ValueError):
            return default
        if x != x:
            return default
        return min(1.0, max(0.001, x))

    lo = _one(target_pct, 0.10)
    if target_pct_max is None:
        hi = lo
    else:
        hi = _one(target_pct_max, lo)
    if hi < lo:
        lo, hi = hi, lo
    return lo, hi


def format_target_pct_range_label(target_lo: float, target_hi: float) -> str:
    lo, hi = float(target_lo), float(target_hi)
    if abs(hi - lo) < 1e-12:
        return f"{lo * 100:.1f}%"
    return f"{lo * 100:.1f}%～{hi * 100:.1f}%"


def classify_target_hits(
    *,
    entry_price: float,
    max_high: float,
    target_lo: float,
    target_hi: float,
) -> Dict[str, bool]:
    """观察期最高价：命中=最大涨幅 ≥ 下限；上限/区间为辅助统计。"""
    if entry_price is None or float(entry_price) <= 0:
        return {"hit_target": False, "hit_target_lower": False, "hit_target_upper": False, "hit_in_band": False}
    entry = float(entry_price)
    high = float(max_high)
    gain = high / entry - 1.0
    lo, hi = float(target_lo), float(target_hi)
    hit_lo = high + 1e-12 >= entry * (1.0 + lo)
    hit_hi = high + 1e-12 >= entry * (1.0 + hi)
    if abs(hi - lo) < 1e-12:
        in_band = hit_lo
    else:
        in_band = gain + 1e-12 >= lo and gain <= hi + 1e-12
    return {
        "hit_target": bool(hit_lo),
        "hit_target_lower": bool(hit_lo),
        "hit_target_upper": bool(hit_hi),
        "hit_in_band": bool(in_band),
    }


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

    span = max(1, progress_end - progress_start)

    def _range_progress(done_stocks: int, total_stocks: int, message: str) -> None:
        if not progress_cb:
            return
        pct = progress_start + int(span * done_stocks / max(1, total_stocks))
        progress_cb(min(progress_end - 1, pct), message)

    hits_by_date, completed = engine.screen_universe_for_dates(
        stocks,
        missing,
        require_pass=True,
        progress_cb=_range_progress,
        cancel_check=cancel_check,
    )
    hit_total = 0
    done = 0
    if completed:
        try:
            all_hits = [h for rows in hits_by_date.values() for h in rows]
            if all_hits:
                upsert_trace_rows(db, config_id=config_id, rows=all_hits)
                hit_total = len(all_hits)
            for d in missing:
                day_hits = hits_by_date.get(d) or []
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
            logger.warning("URT 回测补算预计算落库失败: %s", e)
            try:
                db.rollback()
            except Exception:
                pass
    else:
        logger.info("URT 回测区间扫描未完成，不打扫描占位以免误标覆盖")

    meta["precomputed_days"] = done
    meta["precompute_hits"] = hit_total
    meta["range_scan"] = True
    meta["range_scan_completed"] = bool(completed)
    if progress_cb:
        progress_cb(
            progress_end,
            f"预计算补齐完成：新增 {done} 日，买点 {hit_total} 条",
        )
    return meta


def build_urt_trade_meta(
    *,
    target_pct: float = 0.10,
    target_pct_max: Optional[float] = None,
    horizon_days: int = 10,
    min_score: Optional[float] = None,
    use_trace: bool = True,
    risk: Optional[Dict[str, Any]] = None,
    exit_mode: str = "hit_rate",
    structure_stop_buffer_pct: float = 0.02,
    structure_rr_min_upside_pct: float = 0.03,
    structure_cfg: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """回测详情用：交易逻辑说明 + 风控参数快照。"""
    risk = dict(risk or {})
    sc = dict(structure_cfg or {})
    stop_max = float(risk.get("stop_loss_pct_max") or 10)
    stop_min = float(risk.get("stop_loss_pct_min") or 5)
    time_stop_days = int(risk.get("time_stop_down_days") or 3)
    alert_min = float(risk.get("take_profit_alert_pct_min") or 8)
    alert_max = float(risk.get("take_profit_alert_pct_max") or 10)
    trail = float(risk.get("trailing_drawdown_pct") or 5)
    try:
        time_stop_min_loss = float(
            risk.get("time_stop_min_loss_pct") if risk.get("time_stop_min_loss_pct") is not None else 4.0
        )
    except (TypeError, ValueError):
        time_stop_min_loss = 4.0
    ms = float(min_score) if min_score is not None else 70.0
    target_lo, target_hi = resolve_target_pct_range(target_pct, target_pct_max)
    tp_label = format_target_pct_range_label(target_lo, target_hi)
    tp = float(target_lo) * 100.0
    range_open = abs(float(target_hi) - float(target_lo)) >= 1e-12
    if range_open:
        hit_stat_rule = (
            f"观察期最大涨幅 ≥ +{target_lo * 100:.1f}% 则 hit_target=是；"
            f"≥ +{target_hi * 100:.1f}% 则 hit_target_upper=是；"
            f"落在 [{target_lo * 100:.1f}%, {target_hi * 100:.1f}%] 则 hit_in_band=是"
        )
        hit_stat_short = f"目标涨幅区间 {tp_label}（命中=≥ 下限 {target_lo * 100:.1f}%）"
        hit_priority_desc = (
            f"观察期最大涨幅 ≥ +{target_lo * 100:.1f}%（上限/区间内为辅助统计）"
        )
    else:
        hit_stat_rule = f"观察期内最高价 ≥ 入场价 × (1+{tp:.1f}%) 则 hit_target=是"
        hit_stat_short = f"目标涨幅 {tp_label}"
        hit_priority_desc = f"观察期内最高价触及 +{tp:.1f}%"
    hz = int(horizon_days)
    mode = (exit_mode or "hit_rate").strip().lower()
    if mode not in ("hit_rate", "risk_exit", "structure_exit"):
        mode = "hit_rate"
    try:
        stop_buf = float(structure_stop_buffer_pct)
    except (TypeError, ValueError):
        stop_buf = 0.02
    try:
        min_up = float(structure_rr_min_upside_pct)
    except (TypeError, ValueError):
        min_up = 0.03

    def _sc_float(key: str, default: float) -> float:
        try:
            v = sc.get(key)
            return float(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    def _sc_bool(key: str, default: bool) -> bool:
        v = sc.get(key)
        if v is None:
            return default
        return bool(v)

    fb_stop = _sc_float("structure_fallback_stop_loss_pct", 8.0)
    arm_pct = _sc_float("structure_protect_arm_pct", _sc_float("structure_fallback_arm_pct", 0.065))
    fb_trail = _sc_float(
        "structure_protect_trail_drawdown_pct",
        _sc_float("structure_fallback_trail_drawdown_pct", 0.04),
    )
    exit_min_up = _sc_float("structure_exit_min_upside_pct", min_up if min_up else 0.05)
    partial_frac = _sc_float("structure_partial_exit_frac", 0.5)
    if partial_frac <= 0 or partial_frac > 1:
        partial_frac = 0.5

    risk_params = {
        "stop_loss_pct_min": stop_min,
        "stop_loss_pct_max": stop_max,
        "time_stop_down_days": time_stop_days,
        "time_stop_min_loss_pct": time_stop_min_loss,
        "take_profit_alert_pct_min": alert_min,
        "take_profit_alert_pct_max": alert_max,
        "trailing_drawdown_pct": trail,
        "exit_mode": mode,
        "structure_stop_buffer_pct": stop_buf,
        "structure_rr_min_upside_pct": min_up,
        "structure_exit_min_upside_pct": exit_min_up,
        "structure_fallback_stop_loss_pct": fb_stop,
        "structure_protect_enabled": _sc_bool("structure_protect_enabled", True),
        "structure_protect_arm_pct": arm_pct,
        "structure_protect_trail_drawdown_pct": fb_trail,
        "structure_fallback_protect_enabled": _sc_bool("structure_fallback_protect_enabled", True),
        "structure_fallback_arm_pct": arm_pct,
        "structure_fallback_trail_drawdown_pct": fb_trail,
        "structure_partial_exit_enabled": _sc_bool("structure_partial_exit_enabled", True),
        "structure_partial_exit_frac": partial_frac,
        "structure_pct_target_trail_enabled": _sc_bool("structure_pct_target_trail_enabled", True),
        "structure_recompute_on_missing": _sc_bool("structure_recompute_on_missing", True),
        "structure_weak_fallback_enabled": _sc_bool("structure_weak_fallback_enabled", True),
    }

    if mode == "structure_exit":
        try:
            fb_stop = float(fb_stop)
        except (TypeError, ValueError):
            fb_stop = 8.0
        trade_logic = {
            "summary": (
                f"URT 交易回测（结构出场 structure_exit）：信号次日开盘入场；最长观察期 {hz} 个交易日；"
                f"止损=信号日最近支撑下移 {stop_buf * 100:.0f}%；"
                f"止盈=最近阻力（上行≥{exit_min_up * 100:.1f}% 且可分批）或目标下限 {tp:.1f}% 跟踪；"
                f"全路径浮盈保本/回撤；结构缺失回退止损 −{fb_stop:.0f}%；同时统计 {hit_stat_short}；最低得分 {ms:.0f}。"
            ),
            "rules": [
                (
                    "信号筛选：硬筛通过，"
                    f"且得分 ≥ {ms:.0f}；"
                    + ("优先读取 urt_signal_trace 预计算买点。" if use_trace else "实时引擎扫描买点。")
                ),
                "入场：信号日之后下一交易日开盘价买入；开盘价无效则跳过。",
                f"最长持有：自入场日起至多 {hz} 根交易日 K 线。",
                (
                    f"结构止损：信号日 nearest_support × (1−{stop_buf * 100:.0f}%)；"
                    "持仓第 2 日起若收盘跌破止损价→structure_stop；"
                    f"无支撑或止损不低于入场则回退浮亏 {fb_stop:.0f}%（price_stop）；"
                    "回退原因拆分为 no_support / stop_above_entry。"
                ),
                (
                    "P0：缓存缺结构位时按个股同口径重算（结构锚窗 KDE + confluence）；"
                    "仍缺失则用弱结构（近窗低点/MA20）兜底并标记 structure_source。"
                ),
                (
                    f"结构止盈：信号日 nearest_resistance（相对入场上行 ≥ {exit_min_up * 100:.1f}%）；"
                    f"否则回退入场价 × (1+{tp:.1f}%) 目标区；过近阻力不硬平。"
                ),
                (
                    f"分批：触及首阻力可先平 {partial_frac * 100:.0f}% 仓，余仓取消阻力硬平、改移动止盈。"
                ),
                (
                    f"全路径保护：浮盈达约 +{arm_pct * 100:.1f}% 后保本；"
                    f"峰值回撤约 {fb_trail * 100:.1f}%→breakeven_stop / fallback_trail；"
                    f"百分比目标触及后默认跟踪而非全仓硬平。"
                ),
                f"目标统计：{hit_stat_rule}（独立统计）。",
                f"到期平仓：未触发结构纪律则满 {hz} 日以收盘价出场（horizon_end）。",
                "同标的去重：上一笔出场日之前不再接受新信号开仓。",
                "说明：结构位与个股关键价位同口径（结构锚窗 KDE + confluence）；持仓期不重算。",
            ],
            "exit_priority": [
                {
                    "code": "structure_stop",
                    "label": "结构止损",
                    "desc": f"收盘 ≤ 支撑×(1−{stop_buf * 100:.0f}%)",
                },
                {
                    "code": "structure_target",
                    "label": "阻力止盈",
                    "desc": f"最高价触及信号日最近阻力（可分批 {partial_frac * 100:.0f}%）",
                },
                {
                    "code": "pct_target",
                    "label": "百分比止盈",
                    "desc": f"阻力不足时触及 +{tp:.1f}%（默认可改跟踪）",
                },
                {
                    "code": "price_stop",
                    "label": "百分比止损（回退）",
                    "desc": f"无有效结构止损时浮亏 ≤ −{fb_stop:.0f}%",
                },
                {
                    "code": "breakeven_stop",
                    "label": "保本止损",
                    "desc": f"全路径浮盈达约 +{arm_pct * 100:.1f}% 后止损抬至成本",
                },
                {
                    "code": "fallback_trail",
                    "label": "移动止盈",
                    "desc": f"全路径自峰值回撤约 {fb_trail * 100:.1f}% 出场",
                },
                {
                    "code": "horizon_end",
                    "label": "到期平仓",
                    "desc": f"满 {hz} 个交易日以收盘价出场",
                },
            ],
        }
    elif mode == "risk_exit":
        trade_logic = {
            "summary": (
                f"URT 交易回测（纪律出场 risk_exit）：信号次日开盘入场；最长观察期 {hz} 个交易日；"
                f"持仓期按止损/连跌/回撤止盈离场；同时统计 {hit_stat_short}；最低得分 {ms:.0f}。"
            ),
            "rules": [
                (
                    "信号筛选：硬筛通过，"
                    f"且得分 ≥ {ms:.0f}；"
                    + ("优先读取 urt_signal_trace 预计算买点。" if use_trace else "实时引擎扫描买点。")
                ),
                "入场：信号日之后下一交易日开盘价买入；开盘价无效则跳过。",
                f"最长持有：自入场日起至多 {hz} 根交易日 K 线。",
                (
                    f"纪律出场：浮亏达 {stop_max:.0f}%→price_stop；"
                    f"连跌 {time_stop_days} 日且浮亏≥{time_stop_min_loss:.0f}%→time_stop；"
                    f"涨幅达警惕区 {alert_min:.0f}%–{alert_max:.0f}% 后自高点回撤 {trail:.0f}%→trailing_take_profit。"
                ),
                f"目标统计：{hit_stat_rule}（不必然立即平仓）。",
                f"到期平仓：未触发纪律则满 {hz} 日以收盘价出场（horizon_end）。",
                "同标的去重：上一笔出场日之前不再接受新信号开仓。",
            ],
            "exit_priority": [
                {"code": "price_stop", "label": "价格止损", "desc": f"浮亏 ≤ -{stop_max:.0f}%"},
                {"code": "time_stop", "label": "连跌离场", "desc": f"连续收跌 ≥ {time_stop_days} 日且浮亏 ≥ {time_stop_min_loss:.0f}%"},
                {
                    "code": "trailing_take_profit",
                    "label": "回撤止盈",
                    "desc": f"达警惕涨幅后自峰值回撤 ≥ {trail:.0f}%",
                },
                {
                    "code": "horizon_end",
                    "label": "到期平仓",
                    "desc": f"满 {hz} 个交易日以收盘价出场",
                },
            ],
        }
    else:
        trade_logic = {
            "summary": (
                f"URT 交易回测（对齐 GMS 命中率）：信号次日开盘入场；观察期 {hz} 个交易日；"
                f"以观察期内最高价判定{hit_stat_short}；不止损；最低得分 {ms:.0f}。"
            ),
            "rules": [
                (
                    "信号筛选：硬筛（站上均线、连阳规则 A/B、放量倍数等）通过，"
                    f"且得分 ≥ {ms:.0f}；"
                    + ("优先读取 urt_signal_trace 预计算买点。" if use_trace else "实时引擎扫描买点。")
                ),
                "入场：信号日之后下一交易日开盘价买入；开盘价无效则跳过。",
                f"观察期：自入场日起共 {hz} 根交易日 K 线（默认 10，短线定位）。",
                (
                    f"命中判定：{hit_stat_rule}；"
                    "不模拟止损/止盈/到期平仓，仅统计观察期内是否触达目标涨幅。"
                ),
                f"观察期：自入场日起共 {hz} 根交易日 K 线；记录观察期最高价与最大涨幅。",
                "同标的去重：上一笔观察期结束日之前不再计入新信号（对齐 GMS signal_hit_rate）。",
                (
                    "说明：策略配置中的风控参数（止损/连跌/回撤）在 hit_rate 模式下仅作文档参考，"
                    f"本模式不启用（止损区间约 {stop_min:.0f}%–{stop_max:.0f}%，"
                    f"连跌 {time_stop_days} 日、回撤止盈警惕 {alert_min:.0f}%–{alert_max:.0f}% / {trail:.0f}%）。"
                    "启用纪律出场请设 exit_mode=risk_exit；结构出场请设 structure_exit。"
                ),
            ],
            "exit_priority": [
                {
                    "code": "target_hit",
                    "label": "触及目标（统计）",
                    "desc": f"{hit_priority_desc}；不模拟交易出场",
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


def _observation_end_date(future: Sequence[Dict[str, Any]], fallback: str = "") -> str:
    if not future:
        return str(fallback)[:10]
    return str(future[-1].get("date") or fallback)[:10]


def _history_bars_until(db: Session, code: str, until_date: str, limit: int) -> List[Dict[str, Any]]:
    """信号日及之前的 K 线，日期 DESC（最新在前），供 KDE / 弱结构重算。"""
    from backend_api.models import HistoricalQuotes

    until = str(until_date)[:10]
    rows = (
        db.query(
            HistoricalQuotes.date,
            HistoricalQuotes.open,
            HistoricalQuotes.high,
            HistoricalQuotes.low,
            HistoricalQuotes.close,
            HistoricalQuotes.volume,
        )
        .filter(HistoricalQuotes.code == code, cast(HistoricalQuotes.date, String) <= until)
        .order_by(HistoricalQuotes.date.desc())
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
                "volume": float(r[5]) if r[5] is not None else None,
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
    target_pct_max: Optional[float] = None,
    horizon_days: int = 10,
    min_score: Optional[float] = None,
    use_trace: bool = True,
    stock_pool: Optional[List[str]] = None,
    exit_mode: str = "hit_rate",
    progress_cb: Optional[Callable[[int, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    config_overrides: Optional[Dict[str, Any]] = None,
    signal_filter: Optional[Dict[str, Any]] = None,
    signal_quality_mode: Optional[str] = None,
) -> Dict[str, Any]:
    from .signal_detector import (
        _compute_structure_levels,
        compute_weak_structure_levels,
        evaluate_exit_rules,
        evaluate_structure_exit_rules,
        extract_signal_structure_levels,
        resolve_structure_exit_levels,
        step_structure_fallback_protection,
    )

    mode = (exit_mode or "hit_rate").strip().lower()
    if mode not in ("hit_rate", "risk_exit", "structure_exit"):
        mode = "hit_rate"
    target_lo, target_hi = resolve_target_pct_range(target_pct, target_pct_max)

    cm = URTConfigManager()
    cm.ensure_default_row(db)
    cfg = cm.get_config(strategy_config_id, db=db)
    if min_score is not None:
        cfg = cm.merge_overrides(cfg, min_score=min_score)
    if config_overrides:
        cfg = cm.merge_overrides(cfg, **config_overrides)

    quality_mode = (signal_quality_mode or cfg.get("signal_quality_mode") or "standard").strip().lower()
    if quality_mode not in ("standard", "premium"):
        quality_mode = "standard"
    effective_signal_filter = signal_filter
    if effective_signal_filter is None:
        effective_signal_filter = build_signal_filter_from_cfg(cfg, quality_mode)

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
    use_trace_ok = bool(use_trace and resolved_id is not None)
    trade_progress_start = 45 if use_trace_ok else 85
    realtime_hits_by_date: Dict[str, List[Dict[str, Any]]] = {}
    if not use_trace_ok:
        stocks = loader.list_a_share_candidates(stock_codes=pool)
        if pool:
            allow = set(pool)
            stocks = [(c, n) for c, n in stocks if c in allow]
        span = max(1, trade_progress_start)

        def _rt_progress(done_stocks: int, total_stocks: int, message: str) -> None:
            if not progress_cb:
                return
            pct = int(span * done_stocks / max(1, total_stocks))
            progress_cb(min(trade_progress_start - 1, pct), message)

        realtime_hits_by_date, _completed = engine.screen_universe_for_dates(
            stocks,
            dates,
            require_pass=True,
            progress_cb=_rt_progress,
            cancel_check=cancel_check,
        )
        if progress_cb:
            progress_cb(trade_progress_start, "区间扫描完成，开始模拟交易")

    for i, d in enumerate(dates):
        if cancel_check and cancel_check():
            break
        if progress_cb:
            pct = trade_progress_start + int(
                (100 - trade_progress_start) * i / max(1, len(dates))
            )
            progress_cb(min(99, pct), f"扫描交易日 {d}")

        signals: List[Dict[str, Any]] = []
        if use_trace_ok:
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
            if use_trace_ok:
                # 仅「全市场/池级」未覆盖时回退实时；零星个股 trace 不算覆盖
                covered = dates_ready_for_universe_backtest(
                    db,
                    config_id=int(resolved_id),
                    dates=[d],
                    stock_pool=pool,
                )
                need_realtime = d not in covered
            else:
                signals = list(realtime_hits_by_date.get(d) or [])

        if need_realtime:
            stocks = loader.list_a_share_candidates(stock_codes=pool)
            if pool:
                stocks = [(c, n) for c, n in stocks if c in set(pool)]
            day_hits = engine.screen_universe(stocks, as_of_end_date=d)
            signals = [h for h in day_hits if str(h.get("signal_date"))[:10] == d]
            if use_trace_ok:
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

        vol_need = float(cfg.get("volume_multiple") or 3.0)
        if vol_need > 0:
            signals = [
                s
                for s in signals
                if float(s.get("volume_multiple") or 0) >= vol_need
            ]

        if effective_signal_filter:
            signals = [s for s in signals if passes_signal_factor_filter(s, effective_signal_filter)]

        for sig in signals:
            code = str(sig.get("code") or "")
            if not code:
                continue
            if code in cooldown:
                cd = str(cooldown[code] or "")[:10]
                if cd and (d <= cd if mode == "hit_rate" else d < cd):
                    continue
            # 信号日之后 horizon_days 根 K 线为观察窗（首根为入场日）
            future = _future_bars(db, code, d, horizon_days)
            if not future or future[0].get("open") is None or float(future[0]["open"]) <= 0:
                continue
            entry_date = future[0]["date"]
            entry_price = float(future[0]["open"])
            target_lo_px = entry_price * (1.0 + float(target_lo))
            target_hi_px = entry_price * (1.0 + float(target_hi))

            max_high = entry_price
            hit = False
            hit_date = None
            hit_upper = False
            hit_upper_date = None
            for bar in future:
                hi = bar.get("high")
                if hi is None:
                    cl = bar.get("close")
                    hi = cl if cl is not None else entry_price
                hi_f = float(hi)
                if hi_f > max_high:
                    max_high = hi_f
                if (not hit) and hi_f >= target_lo_px:
                    hit = True
                    hit_date = bar.get("date")
                if (not hit_upper) and hi_f >= target_hi_px:
                    hit_upper = True
                    hit_upper_date = bar.get("date")

            max_gain = (max_high / entry_price - 1.0) if entry_price else 0.0
            band = classify_target_hits(
                entry_price=entry_price,
                max_high=max_high,
                target_lo=target_lo,
                target_hi=target_hi,
            )
            hit = bool(band["hit_target"])
            hit_lower = bool(band["hit_target_lower"])
            hit_upper = bool(band["hit_target_upper"])
            hit_in_band = bool(band["hit_in_band"])
            if not hit:
                hit_date = None

            if mode == "hit_rate":
                obs_end = _observation_end_date(future, entry_date)
                last = future[-1] if future else {}
                exit_date = last.get("date") or entry_date
                exit_close = last.get("close")
                if exit_close is None:
                    exit_close = (
                        last.get("open") if last.get("open") is not None else entry_price
                    )
                exit_price = float(exit_close) if exit_close is not None else entry_price
                pnl_pct = (
                    (exit_price - entry_price) / entry_price * 100.0 if entry_price else 0.0
                )
                row_out: Dict[str, Any] = {
                    "code": code,
                    "name": sig.get("name") or "",
                    "signal_date": d,
                    "score": sig.get("score"),
                    "entry_date": entry_date,
                    "entry_price": round(entry_price, 4),
                    "observation_end_date": obs_end,
                    "horizon_days": len(future),
                    "max_high": round(max_high, 4),
                    "max_gain_pct": round(max_gain * 100.0, 2),
                    "hit_target": hit,
                    "hit_date": hit_date,
                    "hit_target_lower": hit_lower,
                    "hit_target_upper": hit_upper,
                    "hit_date_upper": hit_upper_date,
                    "hit_in_band": hit_in_band,
                    "exit_date": exit_date,
                    "exit_price": round(exit_price, 4),
                    "exit_reason": "horizon_end",
                    "pnl_pct": round(pnl_pct, 2),
                    "bars_held": len(future),
                }
                enrich_detail_with_factors(row_out, sig, future, entry_price)
                details.append(row_out)
                cooldown[code] = obs_end
                continue

            struct_levels: Dict[str, Any] = {}
            if mode == "structure_exit":
                sig_st = extract_signal_structure_levels(sig)
                structure_source = (
                    sig_st.get("structure_level_source")
                    or ("kde" if sig_st.get("nearest_support") is not None else None)
                )
                hist_bars: List[Dict[str, Any]] = []
                recompute = cfg.get("structure_recompute_on_missing")
                if recompute is None:
                    recompute = True
                weak_en = cfg.get("structure_weak_fallback_enabled")
                if weak_en is None:
                    weak_en = True

                need_levels = (
                    sig_st.get("nearest_support") is None
                    or sig_st.get("kde_ok") is False
                )
                if bool(recompute) and need_levels:
                    hist_n = int(cfg.get("kde_lookback_max") or 750)
                    hist_n = min(max(hist_n, 80), 800)
                    hist_bars = _history_bars_until(db, code, d, hist_n)
                    sig_close = None
                    if hist_bars:
                        try:
                            sig_close = float(hist_bars[0].get("close") or 0) or None
                        except (TypeError, ValueError):
                            sig_close = None
                    if not sig_close:
                        sig_close = entry_price
                    recomputed = _compute_structure_levels(hist_bars, cfg, price=sig_close)
                    if recomputed.get("nearest_support") is not None:
                        sig_st = {
                            **sig_st,
                            "nearest_support": recomputed.get("nearest_support"),
                            "nearest_resistance": recomputed.get("nearest_resistance")
                            or sig_st.get("nearest_resistance"),
                            "kde_ok": recomputed.get("kde_ok"),
                            "kde_reason": recomputed.get("kde_reason"),
                            "structure_level_source": recomputed.get("structure_level_source"),
                            "confluence_ok": recomputed.get("confluence_ok"),
                        }
                        structure_source = (
                            recomputed.get("structure_level_source") or "kde_recomputed"
                        )

                if (
                    bool(weak_en)
                    and sig_st.get("nearest_support") is None
                ):
                    if not hist_bars:
                        hist_bars = _history_bars_until(
                            db, code, d, int(cfg.get("structure_weak_lookback") or 20) + 5
                        )
                    weak = compute_weak_structure_levels(
                        hist_bars, price=entry_price, cfg=cfg
                    )
                    if weak.get("ok"):
                        sig_st = {
                            **sig_st,
                            "nearest_support": weak.get("nearest_support"),
                            "nearest_resistance": weak.get("nearest_resistance")
                            or sig_st.get("nearest_resistance"),
                        }
                        structure_source = weak.get("structure_source") or "weak_swing"

                struct_levels = resolve_structure_exit_levels(
                    entry_price=entry_price,
                    nearest_support=sig_st.get("nearest_support"),
                    nearest_resistance=sig_st.get("nearest_resistance"),
                    cfg=cfg,
                    target_pct=float(target_lo),
                    structure_source=structure_source,
                )
                struct_levels["kde_ok"] = sig_st.get("kde_ok")
                struct_levels["structure_rr"] = sig_st.get("structure_rr")
                struct_levels["kde_reason"] = sig_st.get("kde_reason")
                struct_levels["confluence_ok"] = sig_st.get("confluence_ok")
                if not struct_levels.get("structure_source"):
                    struct_levels["structure_source"] = structure_source
                exit_date = future[-1].get("date") or entry_date
                exit_price = float(future[-1].get("close") or entry_price)
                exit_reason = "horizon_end"
                bars_held = len(future)
                cur_stop = struct_levels.get("stop_price")
                cur_stop_basis = struct_levels.get("stop_basis")
                cur_target = struct_levels.get("target_price")
                cur_target_basis = str(struct_levels.get("target_basis") or "")
                protect_armed = False
                peak_hold = entry_price
                remaining_frac = 1.0
                partial_frac = 0.5
                try:
                    pf = cfg.get("structure_partial_exit_frac")
                    if pf is not None:
                        partial_frac = float(pf)
                except (TypeError, ValueError):
                    partial_frac = 0.5
                if partial_frac <= 0 or partial_frac >= 1.0:
                    partial_frac = 0.5
                partial_en = cfg.get("structure_partial_exit_enabled")
                if partial_en is None:
                    partial_en = True
                pct_trail_en = cfg.get("structure_pct_target_trail_enabled")
                if pct_trail_en is None:
                    pct_trail_en = True
                protect_en = cfg.get("structure_protect_enabled")
                if protect_en is None:
                    protect_en = cfg.get("structure_fallback_protect_enabled")
                if protect_en is None:
                    protect_en = True
                partial_exit_price = None
                partial_exit_date = None
                partial_taken = False

                for bi, bar in enumerate(future):
                    cl = bar.get("close")
                    if cl is None:
                        cl = bar.get("open") if bar.get("open") is not None else entry_price
                    cl_f = float(cl)
                    hi = bar.get("high")
                    if hi is None:
                        hi = cl_f
                    hi_f = float(hi)
                    peak_hold = max(peak_hold, hi_f, cl_f)
                    if bi == 0:
                        continue
                    # 全路径浮盈保护（含结构正路径；回退路径同样适用）
                    if bool(protect_en):
                        prot = step_structure_fallback_protection(
                            entry_price=entry_price,
                            peak_high=peak_hold,
                            last_close=cl_f,
                            stop_price=cur_stop,
                            armed=protect_armed,
                            cfg=cfg,
                        )
                        protect_armed = bool(prot.get("armed"))
                        cur_stop = prot.get("stop_price")
                        if prot.get("exit_reason"):
                            exit_date = bar.get("date") or exit_date
                            exit_price = cl_f
                            exit_reason = str(prot.get("exit_reason"))
                            bars_held = bi + 1
                            cur_stop_basis = prot.get("protect_basis") or cur_stop_basis
                            break
                        if protect_armed and prot.get("protect_basis"):
                            cur_stop_basis = str(prot.get("protect_basis"))

                    hit_exit = evaluate_structure_exit_rules(
                        entry_price=entry_price,
                        last_close=cl_f,
                        last_high=hi_f,
                        stop_price=cur_stop,
                        target_price=cur_target,
                        target_basis=cur_target_basis,
                        stop_basis=cur_stop_basis,
                    )
                    if not hit_exit:
                        continue

                    reason = str(hit_exit.get("exit_reason") or "structure_exit")

                    # 百分比目标：触及后改跟踪，不全仓硬平
                    if (
                        reason == "pct_target"
                        and bool(pct_trail_en)
                        and remaining_frac > 1e-9
                    ):
                        protect_armed = True
                        cur_target = None
                        cur_target_basis = "pct_target_trail"
                        prot2 = step_structure_fallback_protection(
                            entry_price=entry_price,
                            peak_high=peak_hold,
                            last_close=cl_f,
                            stop_price=cur_stop,
                            armed=True,
                            cfg=cfg,
                        )
                        cur_stop = prot2.get("stop_price")
                        if prot2.get("protect_basis"):
                            cur_stop_basis = str(prot2.get("protect_basis"))
                        if prot2.get("exit_reason"):
                            exit_date = bar.get("date") or exit_date
                            exit_price = cl_f
                            exit_reason = str(prot2.get("exit_reason"))
                            bars_held = bi + 1
                            break
                        continue

                    # 阻力止盈：可先平部分仓，余仓跟踪
                    if (
                        reason == "structure_target"
                        and bool(partial_en)
                        and not partial_taken
                        and remaining_frac >= 0.999
                    ):
                        partial_taken = True
                        remaining_frac = max(0.0, 1.0 - partial_frac)
                        partial_exit_price = cl_f
                        partial_exit_date = bar.get("date")
                        cur_target = None
                        cur_target_basis = "structure_partial_remain"
                        protect_armed = True
                        prot2 = step_structure_fallback_protection(
                            entry_price=entry_price,
                            peak_high=peak_hold,
                            last_close=cl_f,
                            stop_price=cur_stop,
                            armed=True,
                            cfg=cfg,
                        )
                        cur_stop = prot2.get("stop_price")
                        if prot2.get("protect_basis"):
                            cur_stop_basis = str(prot2.get("protect_basis"))
                        if remaining_frac <= 1e-9:
                            exit_date = bar.get("date") or exit_date
                            exit_price = cl_f
                            exit_reason = "structure_target"
                            bars_held = bi + 1
                            break
                        if prot2.get("exit_reason"):
                            exit_date = bar.get("date") or exit_date
                            exit_price = cl_f
                            exit_reason = str(prot2.get("exit_reason"))
                            bars_held = bi + 1
                            break
                        continue

                    exit_date = bar.get("date") or exit_date
                    exit_price = cl_f
                    exit_reason = reason
                    bars_held = bi + 1
                    break

                # 分批加权盈亏
                if partial_taken and partial_exit_price is not None and entry_price > 0:
                    f1 = 1.0 - remaining_frac
                    pnl_partial = (float(partial_exit_price) / entry_price - 1.0) * 100.0
                    pnl_remain = (float(exit_price) / entry_price - 1.0) * 100.0
                    weighted_pnl = f1 * pnl_partial + remaining_frac * pnl_remain
                    # 标记供 row_out 使用（循环外赋值）
                    struct_levels["_partial_taken"] = True
                    struct_levels["_partial_frac"] = f1
                    struct_levels["_partial_exit_price"] = round(float(partial_exit_price), 4)
                    struct_levels["_partial_exit_date"] = partial_exit_date
                    struct_levels["_remaining_frac"] = remaining_frac
                    struct_levels["_weighted_pnl_pct"] = round(weighted_pnl, 2)
                    if exit_reason == "horizon_end" and remaining_frac < 0.999:
                        # 余仓到期：总原因仍记为 horizon，但已有分批
                        pass
                    elif exit_reason == "structure_target" and remaining_frac < 1e-9:
                        pass
                    elif partial_taken and exit_reason not in (
                        "structure_target",
                        "pct_target",
                    ):
                        # 首腿阻力分批 + 余仓其它原因
                        struct_levels["_exit_reason_combo"] = f"structure_target+{exit_reason}"
            elif mode == "risk_exit":
                closes: List[float] = []
                peak = entry_price
                exit_date = future[-1].get("date") or entry_date
                exit_price = float(future[-1].get("close") or entry_price)
                exit_reason = "horizon_end"
                bars_held = len(future)
                for bi, bar in enumerate(future):
                    cl = bar.get("close")
                    if cl is None:
                        cl = bar.get("open") if bar.get("open") is not None else entry_price
                    cl_f = float(cl)
                    closes.append(cl_f)
                    hi = bar.get("high")
                    if hi is None:
                        hi = cl_f
                    peak = max(peak, float(hi), cl_f)
                    # 入场日当日仅建仓，从第二根 K 起检查纪律（仍统计 hit）
                    if bi == 0:
                        continue
                    hit_exit = evaluate_exit_rules(
                        entry_price=entry_price,
                        closes=closes,
                        peak_price=peak,
                        cfg=cfg,
                    )
                    if hit_exit:
                        exit_date = bar.get("date") or exit_date
                        exit_price = cl_f
                        exit_reason = str(hit_exit.get("exit_reason") or "risk_exit")
                        bars_held = bi + 1
                        break
            else:
                # 不止损：持有满观察期，参考出场=末日收盘
                last = future[-1]
                exit_date = last.get("date") or entry_date
                exit_close = last.get("close")
                exit_price = float(exit_close) if exit_close is not None else entry_price
                exit_reason = "horizon_end"
                bars_held = len(future)
            pnl_pct = (exit_price - entry_price) / entry_price * 100.0
            if mode == "structure_exit" and struct_levels.get("_weighted_pnl_pct") is not None:
                pnl_pct = float(struct_levels["_weighted_pnl_pct"])
            # 去重窗口=完整观察期结束日（对齐 GMS block_until_obs_end）
            cooldown[code] = exit_date
            row_out: Dict[str, Any] = {
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
                "hit_target_lower": hit_lower,
                "hit_target_upper": hit_upper,
                "hit_date_upper": hit_upper_date,
                "hit_in_band": hit_in_band,
                "max_high": round(max_high, 4),
                "max_gain_pct": round(max_gain * 100.0, 2),
                "pnl_pct": round(pnl_pct, 2),
                "bars_held": bars_held,
            }
            enrich_detail_with_factors(row_out, sig, future, entry_price)
            if mode == "structure_exit" and struct_levels:
                row_out.update(
                    {
                        "stop_price": struct_levels.get("stop_price"),
                        "target_price": struct_levels.get("target_price"),
                        "stop_basis": struct_levels.get("stop_basis"),
                        "target_basis": struct_levels.get("target_basis"),
                        "structure_fallback": bool(struct_levels.get("structure_fallback")),
                        "fallback_reason": struct_levels.get("fallback_reason"),
                        "structure_source": struct_levels.get("structure_source"),
                        "nearest_support": struct_levels.get("nearest_support"),
                        "nearest_resistance": struct_levels.get("nearest_resistance"),
                        "kde_ok": struct_levels.get("kde_ok"),
                        "kde_reason": struct_levels.get("kde_reason"),
                        "structure_rr": struct_levels.get("structure_rr"),
                        "fallback_stop_loss_pct": struct_levels.get("fallback_stop_loss_pct"),
                        "partial_exit": bool(struct_levels.get("_partial_taken")),
                        "partial_frac": struct_levels.get("_partial_frac"),
                        "partial_exit_price": struct_levels.get("_partial_exit_price"),
                        "partial_exit_date": struct_levels.get("_partial_exit_date"),
                        "remaining_frac": struct_levels.get("_remaining_frac"),
                        "exit_reason_combo": struct_levels.get("_exit_reason_combo"),
                    }
                )
            details.append(row_out)

    total = len(details)
    hits = sum(1 for r in details if r.get("hit_target"))
    hits_lower = sum(1 for r in details if r.get("hit_target_lower"))
    hits_upper = sum(1 for r in details if r.get("hit_target_upper"))
    in_band_n = sum(1 for r in details if r.get("hit_in_band"))
    wins = sum(1 for r in details if float(r.get("pnl_pct") or 0) > 0)
    avg_pnl = sum(float(r.get("pnl_pct") or 0) for r in details) / total if total else 0.0
    avg_max_gain = (
        sum(float(r.get("max_gain_pct") or 0) for r in details) / total if total else 0.0
    )

    by_score_bucket = assign_score_buckets(details)
    by_factor_bucket = build_factor_buckets(details)
    hit_rate_compare = None if mode == "hit_rate" else build_hit_rate_compare(details, mode)

    holding_hist = {"1-3": 0, "4-10": 0, "11-20": 0, "21+": 0}
    if mode != "hit_rate":
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
    elif details:
        hz_n = int(horizon_days)
        if hz_n <= 3:
            holding_hist["1-3"] = total
        elif hz_n <= 10:
            holding_hist["4-10"] = total
        elif hz_n <= 20:
            holding_hist["11-20"] = total
        else:
            holding_hist["21+"] = total

    exit_reason_dist: Dict[str, int] = {}
    if mode != "hit_rate":
        for r in details:
            reason = str(r.get("exit_reason") or "unknown")
            exit_reason_dist[reason] = exit_reason_dist.get(reason, 0) + 1

    structure_exit_stats: Optional[Dict[str, Any]] = None
    if mode == "structure_exit" and total:
        fb_no = sum(1 for r in details if r.get("fallback_reason") == "no_support")
        fb_above = sum(1 for r in details if r.get("fallback_reason") == "stop_above_entry")
        weak_n = sum(
            1
            for r in details
            if str(r.get("structure_source") or "").startswith("weak_")
        )
        kde_re_n = sum(1 for r in details if r.get("structure_source") == "kde_recomputed")
        partial_n = sum(1 for r in details if r.get("partial_exit"))
        structure_exit_stats = {
            "structure_stop": exit_reason_dist.get("structure_stop", 0),
            "structure_target": exit_reason_dist.get("structure_target", 0),
            "pct_target": exit_reason_dist.get("pct_target", 0),
            "price_stop": exit_reason_dist.get("price_stop", 0),
            "breakeven_stop": exit_reason_dist.get("breakeven_stop", 0),
            "fallback_trail": exit_reason_dist.get("fallback_trail", 0),
            "horizon_end": exit_reason_dist.get("horizon_end", 0),
            "partial_exit_count": partial_n,
            "partial_exit_rate": round(partial_n / total, 4),
            "structure_fallback_count": sum(1 for r in details if r.get("structure_fallback")),
            "structure_fallback_rate": round(
                sum(1 for r in details if r.get("structure_fallback")) / total, 4
            ),
            "fallback_no_support": fb_no,
            "fallback_stop_above_entry": fb_above,
            "fallback_no_support_rate": round(fb_no / total, 4),
            "fallback_stop_above_entry_rate": round(fb_above / total, 4),
            "weak_structure_count": weak_n,
            "weak_structure_rate": round(weak_n / total, 4),
            "kde_recomputed_count": kde_re_n,
            "structure_stop_rate": round(exit_reason_dist.get("structure_stop", 0) / total, 4),
            "structure_target_rate": round(exit_reason_dist.get("structure_target", 0) / total, 4),
            "pct_target_rate": round(exit_reason_dist.get("pct_target", 0) / total, 4),
        }

    # 分月收益：按出场月汇总 pnl_pct 均值（简化；命中率模式不统计）
    monthly_map: Dict[str, List[float]] = {}
    if mode != "hit_rate":
        for r in details:
            ed = str(r.get("exit_date") or "")[:7]
            if not ed:
                continue
            monthly_map.setdefault(ed, []).append(float(r.get("pnl_pct") or 0))
    monthly_returns = [
        {"month": m, "return_pct": round(sum(vs) / len(vs), 2), "count": len(vs)}
        for m, vs in sorted(monthly_map.items())
    ]

    avg_bars = (
        float(horizon_days)
        if mode == "hit_rate"
        else (sum(int(r.get("bars_held") or 0) for r in details) / total if total else 0.0)
    )

    trade_meta = build_urt_trade_meta(
        target_pct=float(target_lo),
        target_pct_max=float(target_hi),
        horizon_days=int(horizon_days),
        min_score=cfg.get("min_score"),
        use_trace=bool(use_trace),
        risk=cfg.get("risk") if isinstance(cfg.get("risk"), dict) else {},
        exit_mode=mode,
        structure_stop_buffer_pct=float(cfg.get("structure_stop_buffer_pct") or 0.02),
        structure_rr_min_upside_pct=float(cfg.get("structure_rr_min_upside_pct") or 0.03),
        structure_cfg=cfg,
    )
    summary_base = {
        "total_signals": total,
        "total_samples": total,
        "target_hits": hits,
        "hit_count": hits,
        "hit_rate": round(hits / total, 4) if total else 0.0,
        "target_hits_lower": hits_lower,
        "hit_count_lower": hits_lower,
        "hit_rate_lower": round(hits_lower / total, 4) if total else 0.0,
        "target_hits_upper": hits_upper,
        "hit_rate_upper": round(hits_upper / total, 4) if total else 0.0,
        "in_band_count": in_band_n,
        "in_band_rate": round(in_band_n / total, 4) if total else 0.0,
        "avg_max_gain_pct": round(avg_max_gain, 2),
        "target_pct": target_lo,
        "target_pct_max": target_hi,
        "target_range_open": abs(float(target_hi) - float(target_lo)) >= 1e-12,
        "horizon_days": horizon_days,
        "backtest_mode": (
            "structure_exit"
            if mode == "structure_exit"
            else ("risk_exit" if mode == "risk_exit" else "signal_hit_rate")
        ),
        "exit_mode": mode,
        "apply_stop_loss": mode in ("risk_exit", "structure_exit"),
        "start_date": start_date,
        "end_date": end_date,
        "strategy_config_id": resolved_id,
        "min_score": cfg.get("min_score"),
        "signal_quality_mode": quality_mode,
        "signal_quality_mode_label": signal_quality_mode_label(quality_mode),
        "signal_filter": effective_signal_filter,
        "by_score_bucket": by_score_bucket,
        "by_factor_bucket": by_factor_bucket,
        "holding_days_histogram": holding_hist,
        "stock_pool_size": len(pool) if pool else None,
        "risk_params": trade_meta["risk_params"],
        "trade_logic": trade_meta["trade_logic"],
        "precompute": precompute_meta or None,
    }
    if mode == "hit_rate":
        summary = {
            **summary_base,
            "avg_bars_held": round(avg_bars, 2),
        }
    else:
        summary = {
            **summary_base,
            "win_count": wins,
            "win_rate": round(wins / total, 4) if total else 0.0,
            "avg_pnl_pct": round(avg_pnl, 2),
            "avg_bars_held": round(avg_bars, 2),
            "hit_rate_compare": hit_rate_compare,
            "exit_reason_dist": exit_reason_dist,
            "structure_exit_stats": structure_exit_stats,
            "monthly_returns": monthly_returns,
        }
    if progress_cb:
        progress_cb(100, "回测完成")
    return {"summary": summary, "details": details}
