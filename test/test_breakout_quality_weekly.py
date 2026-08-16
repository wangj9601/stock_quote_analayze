# -*- coding: utf-8 -*-
"""突破软确认与周线逆势谨慎。"""

from backend_core.analysis.market_structure import (
    aggregate_daily_to_weekly,
    weekly_counter_trend_caution,
)
from backend_core.analysis.pattern_tactical import (
    assess_breakout_quality,
    _demote_hints_for_weak_breakout,
)


def _bar(d, c, v=1000, h=None, l=None):
    return {
        "date": d,
        "open": c,
        "high": h if h is not None else c * 1.01,
        "low": l if l is not None else c * 0.99,
        "close": c,
        "volume": v,
    }


def test_breakout_quality_strong():
    # 20 日均量约 1000；突破日 2000；之后再站稳一日
    bars = [_bar(f"2024-01-{i:02d}", 9.5, 1000) for i in range(1, 21)]
    bars.append(_bar("2024-01-21", 10.1, 2000))
    bars.append(_bar("2024-01-22", 10.15, 1100))
    q = assess_breakout_quality(bars, 10.0)
    assert q is not None
    assert q["quality"] == "strong"
    assert q["vol_ok"] is True
    assert q["hold_ok"] is True
    assert "breakout_vol_ok" in q["evidence_codes"]
    assert "breakout_hold_2d" in q["evidence_codes"]


def test_breakout_quality_weak_volume():
    bars = [_bar(f"2024-01-{i:02d}", 9.5, 1000) for i in range(1, 21)]
    bars.append(_bar("2024-01-21", 10.1, 1100))  # 仅 1.1×
    bars.append(_bar("2024-01-22", 10.2, 1000))
    q = assess_breakout_quality(bars, 10.0)
    assert q is not None
    assert q["quality"] == "weak"
    assert q["vol_ok"] is False


def test_breakout_quality_unconfirmed_hold():
    bars = [_bar(f"2024-01-{i:02d}", 9.5, 1000) for i in range(1, 21)]
    bars.append(_bar("2024-01-21", 10.1, 2000))  # 仅 1 日站稳
    q = assess_breakout_quality(bars, 10.0)
    assert q is not None
    assert q["quality"] == "unconfirmed_hold"
    assert q["vol_ok"] is True
    assert q["hold_ok"] is False


def test_demote_weak_breakout_hints():
    hints = [
        {
            "type": "breakout_buy",
            "trigger": "上破跟进",
            "priority": 1,
            "entry_zone": {"anchor": "break_upper", "low": 10, "high": 10.2},
        }
    ]
    out, tip = _demote_hints_for_weak_breakout(hints, "weak")
    assert tip
    assert out[0]["type"] == "watch"
    assert out[0]["priority"] >= 3
    assert "假突破" in out[0]["trigger"]


def test_aggregate_daily_to_weekly_and_caution():
    bars = []
    # 三周：周一起
    for i, c in enumerate([10, 10.2, 10.1, 10.3, 10.4]):
        bars.append(_bar(f"2024-01-{1+i:02d}", c, 1000))  # Mon-Fri week1
    for i, c in enumerate([10.5, 10.6, 10.4, 10.7, 10.8]):
        bars.append(_bar(f"2024-01-{8+i:02d}", c, 1000))
    for i, c in enumerate([10.2, 10.0, 9.8, 9.7, 9.5]):
        bars.append(_bar(f"2024-01-{15+i:02d}", c, 1000))
    weekly = aggregate_daily_to_weekly(bars)
    assert len(weekly) == 3
    assert weekly[0]["high"] >= weekly[0]["low"]
    assert weekly[-1]["close"] == 9.5

    caution = weekly_counter_trend_caution("downtrend", "看多")
    assert caution and caution["counter_trend_caution"] is True
    assert "逆势谨慎" in caution["text"]
    assert weekly_counter_trend_caution("uptrend", "看多") is None
    assert weekly_counter_trend_caution("downtrend", "看空") is None
