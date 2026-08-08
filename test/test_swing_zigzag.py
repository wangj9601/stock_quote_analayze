# -*- coding: utf-8 -*-
from datetime import date, timedelta

from backend_core.analysis.swing_zigzag import (
    extract_zigzag_swing,
    select_swing_from_zigzag,
    wilder_atr,
)


def _v_shape_bars(n=60):
    """先跌后涨，形成清晰低点再高点。"""
    bars = []
    base = date(2025, 1, 2)
    mid = n // 2
    for i in range(n):
        if i <= mid:
            c = 20.0 - (i / mid) * 8.0  # 20 → 12
        else:
            c = 12.0 + ((i - mid) / (n - 1 - mid)) * 10.0  # 12 → 22
        bars.append(
            {
                "date": (base + timedelta(days=i)).isoformat(),
                "high": round(c + 0.4, 2),
                "low": round(c - 0.4, 2),
                "close": round(c, 2),
                "volume": 1_000_000,
            }
        )
    return bars


def test_wilder_atr_positive():
    bars = _v_shape_bars(30)
    parsed = []
    for b in bars:
        from datetime import datetime

        d = datetime.strptime(b["date"], "%Y-%m-%d").date()
        parsed.append((d, b["high"], b["low"], b["close"]))
    atr = wilder_atr(parsed)
    assert atr is not None and atr > 0


def test_fractal_and_zigzag_find_swing():
    bars = _v_shape_bars(60)
    zz = extract_zigzag_swing(bars, max_bars=180)
    assert zz["ok"] is True
    assert zz["anchor_method"] == "zigzag_fractal"
    swing = zz["swing"]
    assert swing is not None
    assert swing["swing_low"] < swing["swing_high"]
    assert swing["direction"] == "up"
    assert zz["min_swing_bars"] == 8
    assert swing["bar_span"] >= zz["min_swing_bars"]
    assert zz["depth_pct"] is not None and zz["depth_pct"] >= 0.025


def test_skip_one_day_crash_use_previous_leg():
    """最近一腿仅隔 1 根 K 时，回退到上一完整波段。"""
    zz_points = [
        {"index": 10, "kind": "low", "price": 30.0, "date": "2026-06-01"},
        {"index": 40, "kind": "high", "price": 38.88, "date": "2026-07-28"},
        {"index": 41, "kind": "low", "price": 34.75, "date": "2026-07-29"},
    ]
    swing = select_swing_from_zigzag(zz_points, min_swing_bars=8)
    assert swing is not None
    assert swing["skipped_short_leg"] is True
    assert swing["swing_high"] == 38.88
    assert swing["swing_low"] == 30.0
    assert swing["bar_span"] == 30
    assert swing["direction"] == "up"


def test_zigzag_depth_filters_noise():
    # 平坦序列：分形可能有，但深度不足 → 无确认波段
    bars = []
    base = date(2025, 3, 1)
    for i in range(40):
        c = 10.0 + (0.01 if i % 2 == 0 else -0.01)
        bars.append(
            {
                "date": (base + timedelta(days=i)).isoformat(),
                "high": c + 0.02,
                "low": c - 0.02,
                "close": c,
            }
        )
    zz = extract_zigzag_swing(bars)
    # 可能 ok=False（无确认）或深度很大导致无交替
    if zz["ok"]:
        assert zz["swing"]["swing_high"] - zz["swing"]["swing_low"] >= zz["depth"] * 0.9
    else:
        assert zz["reason"] in ("no_confirmed_swing", "insufficient_bars")
