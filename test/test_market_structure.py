# -*- coding: utf-8 -*-
"""波段与趋势结构（Market Structure）单测。"""

from __future__ import annotations

from datetime import date, timedelta

from backend_core.analysis.market_structure import (
    analyze_market_structure,
    contrast_with_pattern_bias,
    _label_hhhl,
    _last_bos_like,
    _trend_from_labels,
)


def _bar(d: date, o: float, h: float, l: float, c: float) -> dict:
    return {
        "date": d.isoformat(),
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "volume": 1000.0,
    }


def _synth_uptrend(n: int = 120) -> list:
    """合成抬升波段：若干峰谷抬高。"""
    bars = []
    base = date(2024, 1, 2)
    # 以 20 根为一波：下跌 8 → 上涨 12，整体抬升
    price = 10.0
    for i in range(n):
        wave = i % 20
        if wave < 8:
            price -= 0.08
        else:
            price += 0.15
        # 缓慢抬升偏移
        level = price + i * 0.02
        d = base + timedelta(days=i)
        bars.append(_bar(d, level - 0.05, level + 0.12, level - 0.12, level))
    return bars


def _synth_range(n: int = 100) -> list:
    bars = []
    base = date(2024, 1, 2)
    for i in range(n):
        # 10～12 震荡
        phase = (i % 16) / 16.0
        import math

        level = 11.0 + math.sin(phase * 2 * math.pi) * 0.8
        d = base + timedelta(days=i)
        bars.append(_bar(d, level - 0.05, level + 0.1, level - 0.1, level))
    return bars


def test_label_hhhl_basic():
    zz = [
        {"index": 0, "kind": "low", "price": 10.0, "date": "2024-01-01"},
        {"index": 5, "kind": "high", "price": 12.0, "date": "2024-01-06"},
        {"index": 10, "kind": "low", "price": 10.5, "date": "2024-01-11"},
        {"index": 15, "kind": "high", "price": 13.0, "date": "2024-01-16"},
        {"index": 20, "kind": "low", "price": 11.0, "date": "2024-01-21"},
        {"index": 25, "kind": "high", "price": 14.0, "date": "2024-01-26"},
    ]
    labeled = _label_hhhl(zz)
    structs = [p["structure"] for p in labeled]
    assert structs[0] == "—"  # first low
    assert structs[1] == "—"  # first high
    assert structs[2] == "HL"
    assert structs[3] == "HH"
    assert structs[4] == "HL"
    assert structs[5] == "HH"


def test_trend_uptrend_from_labels():
    pts = [
        {"kind": "low", "structure": "—", "price": 10},
        {"kind": "high", "structure": "—", "price": 12},
        {"kind": "low", "structure": "HL", "price": 10.5},
        {"kind": "high", "structure": "HH", "price": 13},
        {"kind": "low", "structure": "HL", "price": 11},
        {"kind": "high", "structure": "HH", "price": 14},
    ]
    trend, meta = _trend_from_labels(pts)
    assert trend == "uptrend"
    assert meta["hh"] >= 2
    assert meta["hl"] >= 2


def test_trend_downtrend_from_labels():
    pts = [
        {"kind": "high", "structure": "—", "price": 14},
        {"kind": "low", "structure": "—", "price": 12},
        {"kind": "high", "structure": "LH", "price": 13},
        {"kind": "low", "structure": "LL", "price": 11},
        {"kind": "high", "structure": "LH", "price": 12.5},
        {"kind": "low", "structure": "LL", "price": 10},
    ]
    trend, _ = _trend_from_labels(pts)
    assert trend == "downtrend"


def test_bos_break_swing_high():
    pts = [
        {"kind": "low", "structure": "HL", "price": 10.0, "date": "2024-01-01"},
        {"kind": "high", "structure": "HH", "price": 12.0, "date": "2024-01-10"},
    ]
    bos = _last_bos_like(pts, last_close=12.1)
    assert bos is not None
    assert bos["type"] == "break_swing_high"


def test_bos_break_swing_low():
    pts = [
        {"kind": "high", "structure": "LH", "price": 12.0, "date": "2024-01-01"},
        {"kind": "low", "structure": "LL", "price": 10.0, "date": "2024-01-10"},
    ]
    bos = _last_bos_like(pts, last_close=9.9)
    assert bos is not None
    assert bos["type"] == "break_swing_low"


def test_analyze_uptrend_synth():
    bars = _synth_uptrend(140)
    ms = analyze_market_structure(bars, max_bars=140, max_points=12)
    assert ms["ok"] is True
    assert len(ms["points"]) >= 4
    assert ms["trend"] in ("uptrend", "transition", "range")
    assert ms["summary"]
    assert "params" in ms


def test_analyze_insufficient():
    bars = _synth_uptrend(5)
    ms = analyze_market_structure(bars)
    assert ms["ok"] is False
    assert ms["trend"] == "insufficient"


def test_contrast_with_pattern_bias():
    assert "形态偏空" in (contrast_with_pattern_bias("uptrend", "看空") or "")
    assert "一致偏多" in (contrast_with_pattern_bias("uptrend", "看多") or "")
    assert contrast_with_pattern_bias("uptrend", "insufficient") is None


def test_transition_after_bear_then_hh_hl():
    pts = [
        {"kind": "high", "structure": "LH", "price": 13.0, "date": "2026-06-01"},
        {"kind": "low", "structure": "LL", "price": 11.0, "date": "2026-06-15"},
        {"kind": "high", "structure": "LH", "price": 12.5, "date": "2026-07-01"},
        {"kind": "low", "structure": "LL", "price": 10.0, "date": "2026-07-15"},
        {"kind": "high", "structure": "HH", "price": 13.5, "date": "2026-07-22"},
        {"kind": "low", "structure": "HL", "price": 12.4, "date": "2026-08-10"},
    ]
    trend, meta = _trend_from_labels(pts)
    assert trend == "transition"
    assert meta.get("reason") == "bull_pair_after_bear"
    from backend_core.analysis.market_structure import build_trend_analysis

    bos = {
        "type": "break_swing_high",
        "label": "收盘越过近期摆动高点",
        "level": 13.5,
        "level_date": "2026-07-22",
    }
    note = build_trend_analysis(trend, pts, bos, last_close=14.31, trend_meta=meta)
    assert "读图" in note["legend"]
    assert "HH" in note["structure_read"]
    assert "转换" in note["stage"]
    assert "越过" in note["watch"] or "摆动高" in note["watch"]
    assert len(note["paragraphs"]) >= 3
