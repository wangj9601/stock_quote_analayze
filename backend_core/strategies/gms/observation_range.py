"""
GMS 观察周期内最高/最低区间振幅：从行情表批量计算 (period_high - period_low) / period_high。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import desc
from sqlalchemy.orm import Session

from .ma60_source import DEFAULT_OBSERVATION_PERIOD, Ma60Key, ma60_key, normalize_indicator_date

logger = logging.getLogger(__name__)

DEFAULT_OBSERVATION_AMPLITUDE_THRESHOLD = 0.30

RangeResult = Tuple[Optional[float], Optional[float], Optional[float]]  # high, low, amplitude_pct


def resolve_observation_period_days(config: Optional[Dict[str, Any]] = None) -> int:
    """解析观察周期交易日数，默认与 GMS observation_period 一致（20）。"""
    cfg = config or {}
    obs = cfg.get("observation_period", DEFAULT_OBSERVATION_PERIOD)
    try:
        return max(1, int(obs))
    except (TypeError, ValueError):
        return DEFAULT_OBSERVATION_PERIOD


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def resolve_amplitude_threshold_pct(
    rule: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """解析振幅阈值：优先规则 amplitude_threshold_pct，否则 scoring.observation_range_amplitude_threshold。"""
    if isinstance(rule, dict) and rule.get("amplitude_threshold_pct") is not None:
        return _safe_float(rule.get("amplitude_threshold_pct"), DEFAULT_OBSERVATION_AMPLITUDE_THRESHOLD)
    scoring = (config or {}).get("scoring") or {}
    return _safe_float(
        scoring.get("observation_range_amplitude_threshold"),
        DEFAULT_OBSERVATION_AMPLITUDE_THRESHOLD,
    )


def compute_range_amplitude_pct(period_high: Any, period_low: Any) -> Optional[float]:
    """(最高 - 最低) / 最高；无效输入返回 None。"""
    try:
        hi = float(period_high)
        lo = float(period_low)
    except (TypeError, ValueError):
        return None
    if hi <= 0 or lo <= 0:
        return None
    return (hi - lo) / hi


def _quote_model(market_type: str):
    mt = str(market_type or "CN").strip().upper()
    if mt == "HK":
        from backend_api.models import HistoricalQuotesHK

        return HistoricalQuotesHK
    if mt in ("ETF", "FUND"):
        from backend_api.models import FundHistoricalQuotes

        return FundHistoricalQuotes
    from backend_api.models import HistoricalQuotes

    return HistoricalQuotes


def batch_lookup_observation_range(
    db: Session,
    keys: Iterable[Ma60Key],
    period_days: int = DEFAULT_OBSERVATION_PERIOD,
) -> Dict[Ma60Key, RangeResult]:
    """批量计算各 (code, date, market_type) 在观察周期内的最高/最低及振幅。"""
    period = max(1, int(period_days))
    norm: List[Ma60Key] = []
    seen: set[Ma60Key] = set()
    for code, date, mt in keys:
        k = ma60_key(code, date, mt)
        if not k[0] or not k[1] or k in seen:
            continue
        seen.add(k)
        norm.append(k)
    if not norm:
        return {}

    by_cm: Dict[Tuple[str, str], List[str]] = {}
    for code, date, mt in norm:
        by_cm.setdefault((code, mt), []).append(date)

    out: Dict[Ma60Key, RangeResult] = {}
    for (code, mt), dates in by_cm.items():
        model = _quote_model(mt)
        max_date = max(dates)
        rows = (
            db.query(model.date, model.high, model.low)
            .filter(
                model.code == code,
                model.date <= max_date,
                model.high.isnot(None),
                model.low.isnot(None),
            )
            .order_by(desc(model.date))
            .all()
        )
        history: List[Tuple[str, float, float]] = []
        for d, hi, lo in rows:
            try:
                h = float(hi)
                l = float(lo)
                if h > 0 and l > 0:
                    history.append((normalize_indicator_date(d), h, l))
            except (TypeError, ValueError):
                continue

        for target_date in dates:
            window = [(d, h, l) for d, h, l in history if d <= target_date][:period]
            if len(window) < period:
                continue
            period_high = max(h for _, h, _ in window)
            period_low = min(l for _, _, l in window)
            amp = compute_range_amplitude_pct(period_high, period_low)
            out[ma60_key(code, target_date, mt)] = (period_high, period_low, amp)
    return out


def enrich_rows_observation_range(
    db: Session,
    rows: List[Dict[str, Any]],
    *,
    period_days: int = DEFAULT_OBSERVATION_PERIOD,
) -> None:
    """为 GMS 指标 row 补全 observation_period_high/low 与 observation_range_amplitude_pct。"""
    if not rows:
        return
    keys: List[Ma60Key] = []
    for r in rows:
        k = ma60_key(r.get("code"), r.get("date"), r.get("market_type"))
        if k[0] and k[1]:
            keys.append(k)
    if not keys:
        return
    try:
        cache = batch_lookup_observation_range(db, keys, period_days=period_days)
        for r in rows:
            k = ma60_key(r.get("code"), r.get("date"), r.get("market_type"))
            hit = cache.get(k)
            if not hit:
                r.setdefault("observation_period_high", None)
                r.setdefault("observation_period_low", None)
                r.setdefault("observation_range_amplitude_pct", None)
                continue
            ph, pl, amp = hit
            r["observation_period_high"] = ph
            r["observation_period_low"] = pl
            r["observation_range_amplitude_pct"] = amp
            r["observation_range_period_days"] = period_days
    except Exception:
        logger.exception("GMS 观察周期振幅 enrich 失败")
        try:
            db.rollback()
        except Exception:
            pass
