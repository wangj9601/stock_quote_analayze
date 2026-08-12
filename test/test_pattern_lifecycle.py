# -*- coding: utf-8 -*-
"""形态生命周期归档。"""

from datetime import date, timedelta

from backend_core.analysis.chart_patterns.lifecycle import apply_pattern_lifecycle
from backend_core.analysis.chart_patterns.schema import make_hit


def _bars_path(n=80, start=None, path=None):
    """path: 收盘价序列；缺省先涨后跌。"""
    d0 = start or date(2026, 5, 1)
    if path is None:
        path = []
        for i in range(n):
            if i < 30:
                path.append(100 + i * 3)  # 涨到约 187
            else:
                path.append(190 - (i - 30) * 2)  # 回落到约 90
    bars = []
    for i, c in enumerate(path):
        d = d0 + timedelta(days=i)
        bars.append(
            {
                "date": d.isoformat(),
                "open": c,
                "high": c * 1.01,
                "low": c * 0.99,
                "close": c,
            }
        )
    return bars


def test_double_bottom_archived_after_run_and_giveback():
    bars = _bars_path(80)
    hit = make_hit(
        pattern_family="double_extremes",
        pattern_type="double_bottom",
        status="confirmed",
        confidence=0.72,
        reason="双底",
        key_levels={"neckline": 133.53, "l1": 120.0, "l2": 121.0, "last_close": 90.0},
        pivots=[
            {"role": "l1", "date": "2026-05-01", "price": 120.0},
            {"role": "l2", "date": "2026-05-06", "price": 121.0},
        ],
        extra={"formed_at": "2026-05-06"},
    )
    out = apply_pattern_lifecycle([hit], bars)
    assert out[0]["status"] == "archived"
    assert "已归档" in out[0]["reason"] or "生命周期" in out[0]["reason"]


def test_fresh_confirmed_not_archived():
    bars = _bars_path(20, path=[100 + i for i in range(20)])
    hit = make_hit(
        pattern_family="double_extremes",
        pattern_type="double_bottom",
        status="confirmed",
        confidence=0.72,
        reason="双底",
        key_levels={"neckline": 105.0, "last_close": 119.0},
        pivots=[{"role": "l2", "date": bars[0]["date"], "price": 100.0}],
        extra={"formed_at": bars[0]["date"]},
    )
    out = apply_pattern_lifecycle([hit], bars)
    assert out[0]["status"] == "confirmed"
