# -*- coding: utf-8 -*-
"""趋势模板：SEPA 第一道闸门。八条全为"与"关系。

口径：日线前复权价；52 周窗口取最近 250 根。相对强度按全市场横截面百分位，
由调用方传入（批量扫描时统一算，单票分析时可传 None → 条件 8 不通过）。
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

import numpy as np

from backend_core.analysis.sepa.bars import parse_bars, sma, weighted_momentum
from backend_core.analysis.sepa.config import TrendConfig

CONDITION_LABELS = {
    1: "股价在 150/200 日均线上方",
    2: "150 日均线高于 200 日均线",
    3: "200 日均线持续上行",
    4: "50 日均线高于 150/200 日均线",
    5: "股价在 50 日均线上方",
    6: "距 52 周低点涨幅达标",
    7: "距 52 周高点回撤可控",
    8: "相对强度排名达标",
}


def compute_trend_template(
    bars: Sequence[Dict[str, Any]],
    *,
    rs_rank: Optional[float] = None,
    cfg: Optional[TrendConfig] = None,
) -> Dict[str, Any]:
    """返回 {ok, ok_count, conditions, metrics, failed, reason}。"""
    c = cfg or TrendConfig()
    data = parse_bars(bars)
    close = data["close"]
    if close.size < c.min_bars:
        return {
            "ok": False,
            "ok_count": 0,
            "conditions": {},
            "metrics": {},
            "failed": list(CONDITION_LABELS.values()),
            "reason": "k_bars_insufficient",
        }

    ma_s = sma(close, c.ma_short)
    ma_m = sma(close, c.ma_mid)
    ma_l = sma(close, c.ma_long)
    last = float(close[-1])
    s, m, l = float(ma_s[-1]), float(ma_m[-1]), float(ma_l[-1])
    if not np.isfinite(l) or not np.isfinite(m) or not np.isfinite(s):
        return {
            "ok": False,
            "ok_count": 0,
            "conditions": {},
            "metrics": {},
            "failed": list(CONDITION_LABELS.values()),
            "reason": "ma_not_ready",
        }

    idx = len(close) - 1 - int(c.ma_long_rise_days)
    l_prev = float(ma_l[idx]) if idx >= 0 else float("nan")

    window = slice(max(0, len(close) - 250), len(close))
    high_52w = float(np.max(data["high"][window]))
    low_52w = float(np.min(data["low"][window]))

    conditions = {
        1: last > m and last > l,
        2: m > l,
        3: bool(np.isfinite(l_prev) and l > l_prev),
        4: s > m and s > l,
        5: last > s,
        6: bool(low_52w > 0 and last >= low_52w * (1.0 + c.min_low_gain)),
        7: bool(high_52w > 0 and last >= high_52w * (1.0 - c.max_high_drawdown)),
        8: bool(rs_rank is not None and np.isfinite(rs_rank) and rs_rank >= c.min_rs_rank),
    }
    ok_count = sum(1 for v in conditions.values() if v)
    passed = ok_count == 8 if c.require_all else ok_count >= 7

    slope_pct = (l / l_prev - 1.0) * 100.0 if np.isfinite(l_prev) and l_prev > 0 else 0.0
    quality = min(100.0, max(0.0, ok_count / 8.0 * 70.0 + min(slope_pct, 3.0) / 3.0 * 30.0))

    metrics = {
        "close": round(last, 3),
        "ma50": round(s, 3),
        "ma150": round(m, 3),
        "ma200": round(l, 3),
        "ma200_slope_pct": round(slope_pct, 3),
        "off_high_pct": round((last / high_52w - 1.0) * 100, 2) if high_52w > 0 else None,
        "off_low_pct": round((last / low_52w - 1.0) * 100, 2) if low_52w > 0 else None,
        "extended_pct": round((last / s - 1.0) * 100, 2) if s > 0 else None,
        "rs_rank": round(float(rs_rank), 1) if rs_rank is not None else None,
        "trend_quality": round(quality, 1),
    }
    failed = [CONDITION_LABELS[k] for k, v in conditions.items() if not v]
    return {
        "ok": bool(passed),
        "ok_count": int(ok_count),
        "conditions": {k: bool(v) for k, v in conditions.items()},
        "metrics": metrics,
        "failed": failed,
        "reason": "" if passed else "trend_template_failed",
    }


def momentum_of(bars: Sequence[Dict[str, Any]]) -> float:
    """供批量扫描计算相对强度用。"""
    return weighted_momentum(parse_bars(bars)["close"])
