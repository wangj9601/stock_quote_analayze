# -*- coding: utf-8 -*-
"""SMC 引擎单测：CHOCH/BOS、OB、FVG。"""

from __future__ import annotations

from datetime import date, timedelta

from backend_core.analysis.smc_engine import (
    analyze_smc,
    detect_fvgs,
    detect_order_blocks,
    detect_structure_events,
    parse_ohlc_bars,
    trend_to_structure_bias,
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


def test_trend_to_structure_bias():
    assert trend_to_structure_bias("uptrend") == "bullish"
    assert trend_to_structure_bias("downtrend") == "bearish"
    assert trend_to_structure_bias("range") == "neutral"


def test_choch_bullish_after_downtrend_labels():
    """空头语境（LH/LL）下收盘上破摆动高 → CHOCH bullish。"""
    base = date(2024, 1, 2)
    bars = []
    # 先构造下行：从 20 降到 10
    price = 20.0
    for i in range(60):
        price -= 0.12
        d = base + timedelta(days=i)
        bars.append(_bar(d, price + 0.05, price + 0.15, price - 0.15, price))
    # 脉冲上破
    for i in range(60, 80):
        price += 0.35
        d = base + timedelta(days=i)
        # 中间插阴线供 OB
        if i == 70:
            bars.append(_bar(d, price + 0.2, price + 0.25, price - 0.3, price - 0.25))
        else:
            bars.append(_bar(d, price - 0.1, price + 0.2, price - 0.2, price))

    labeled = [
        {"index": 10, "kind": "high", "price": 18.0, "date": "2024-01-12", "structure": "—"},
        {"index": 20, "kind": "low", "price": 16.0, "date": "2024-01-22", "structure": "—"},
        {"index": 30, "kind": "high", "price": 17.0, "date": "2024-02-01", "structure": "LH"},
        {"index": 40, "kind": "low", "price": 14.0, "date": "2024-02-11", "structure": "LL"},
        {"index": 50, "kind": "high", "price": 15.5, "date": "2024-02-21", "structure": "LH"},
        {"index": 55, "kind": "low", "price": 12.0, "date": "2024-02-26", "structure": "LL"},
    ]
    # 强制末价远高于最近摆动高 15.5
    bars[-1]["close"] = 16.0
    bars[-1]["high"] = 16.2
    bars[-1]["open"] = 15.8
    bars[-1]["low"] = 15.7

    ohlc = parse_ohlc_bars(bars)
    events = detect_structure_events(ohlc, labeled, confirm_right=2)
    assert events, "应检出结构事件"
    last = events[-1]
    assert last["direction"] == "bullish"
    assert last["type"] == "choch"
    assert last["event_key"] == "choch_bullish"

    obs = detect_order_blocks(ohlc, events)
    assert obs, "CHOCH 后应有看涨 OB"
    assert any(b["direction"] == "bullish" for b in obs)


def test_bos_bullish_in_uptrend():
    """多头语境上破前高 → BOS bullish。"""
    labeled = [
        {"index": 5, "kind": "low", "price": 10.0, "date": "2024-01-06", "structure": "—"},
        {"index": 15, "kind": "high", "price": 12.0, "date": "2024-01-16", "structure": "—"},
        {"index": 25, "kind": "low", "price": 10.5, "date": "2024-01-26", "structure": "HL"},
        {"index": 35, "kind": "high", "price": 13.0, "date": "2024-02-05", "structure": "HH"},
        {"index": 45, "kind": "low", "price": 11.0, "date": "2024-02-15", "structure": "HL"},
        {"index": 55, "kind": "high", "price": 14.0, "date": "2024-02-25", "structure": "HH"},
    ]
    base = date(2024, 1, 2)
    bars = []
    for i in range(70):
        lvl = 10.0 + i * 0.08
        d = base + timedelta(days=i)
        bars.append(_bar(d, lvl - 0.05, lvl + 0.1, lvl - 0.1, lvl))
    bars[-1]["close"] = 14.2
    bars[-1]["high"] = 14.3
    bars[-1]["open"] = 14.0
    bars[-1]["low"] = 13.9

    ohlc = parse_ohlc_bars(bars)
    events = detect_structure_events(ohlc, labeled, confirm_right=2)
    assert events
    last = events[-1]
    assert last["direction"] == "bullish"
    assert last["type"] == "bos"
    assert last["event_key"] == "bos_bullish"


def test_fvg_open_then_filled():
    base = date(2024, 1, 2)
    bars = [
        _bar(base, 10, 10.2, 9.8, 10.0),
        _bar(base + timedelta(days=1), 10.1, 10.3, 10.0, 10.2),
        # 看涨 FVG：bar0.high=10.2 < bar2.low=11.0
        _bar(base + timedelta(days=2), 11.0, 11.5, 11.0, 11.4),
        _bar(base + timedelta(days=3), 11.3, 11.6, 11.2, 11.5),
        # 回填并向下穿越
        _bar(base + timedelta(days=4), 11.0, 11.1, 9.5, 9.6),
    ]
    ohlc = parse_ohlc_bars(bars)
    # 只用前 4 根 → open/partial
    fvgs_open = detect_fvgs(ohlc[:4], atr=1.0, min_pct=0.001, atr_mult=0.01)
    bull = [f for f in fvgs_open if f["direction"] == "bullish"]
    assert bull
    assert bull[0]["status"] in ("open", "partial")

    fvgs_all = detect_fvgs(ohlc, atr=1.0, min_pct=0.001, atr_mult=0.01)
    bull2 = [f for f in fvgs_all if f["direction"] == "bullish"]
    assert bull2
    assert bull2[0]["status"] == "filled"


def test_fvg_small_gap_filtered():
    base = date(2024, 1, 2)
    bars = [
        _bar(base, 10, 10.10, 9.9, 10.0),
        _bar(base + timedelta(days=1), 10.0, 10.12, 9.95, 10.05),
        # 极小缺口 10.10 → 10.12
        _bar(base + timedelta(days=2), 10.12, 10.2, 10.12, 10.18),
    ]
    ohlc = parse_ohlc_bars(bars)
    fvgs = detect_fvgs(ohlc, atr=1.0, atr_mult=0.15, min_pct=0.003)
    assert fvgs == []


def test_analyze_smc_keys():
    base = date(2024, 1, 2)
    bars = []
    price = 10.0
    for i in range(100):
        wave = i % 20
        if wave < 8:
            price -= 0.05
        else:
            price += 0.12
        level = price + i * 0.01
        bars.append(
            _bar(base + timedelta(days=i), level - 0.05, level + 0.1, level - 0.1, level)
        )
    labeled = [
        {"index": 10, "kind": "low", "price": 10.0, "date": "2024-01-12", "structure": "—"},
        {"index": 20, "kind": "high", "price": 12.0, "date": "2024-01-22", "structure": "—"},
        {"index": 30, "kind": "low", "price": 10.5, "date": "2024-02-01", "structure": "HL"},
        {"index": 40, "kind": "high", "price": 13.0, "date": "2024-02-11", "structure": "HH"},
        {"index": 50, "kind": "low", "price": 11.0, "date": "2024-02-21", "structure": "HL"},
        {"index": 60, "kind": "high", "price": 14.0, "date": "2024-03-02", "structure": "HH"},
    ]
    smc = analyze_smc(bars, labeled)
    assert smc["ok"] is True
    assert "events" in smc
    assert "order_blocks" in smc
    assert "fvgs" in smc
    assert "summary" in smc
    assert smc["structure_bias"] in ("bullish", "bearish", "neutral")


def test_order_blocks_and_fvgs_sorted_by_date_desc():
    """OB/FVG 对外列表按日期新→旧。"""
    from backend_core.analysis.smc_engine import detect_fvgs, detect_order_blocks, parse_ohlc_bars

    base = date(2024, 1, 2)
    bars = []
    for i in range(80):
        lvl = 10.0 + (i % 7) * 0.3
        bars.append(_bar(base + timedelta(days=i), lvl, lvl + 0.5, lvl - 0.4, lvl + 0.1))
    # 人为放大缺口便于检出 FVG
    bars[20] = _bar(base + timedelta(days=20), 10, 10.1, 9.9, 10.0)
    bars[21] = _bar(base + timedelta(days=21), 10.2, 10.3, 10.1, 10.2)
    bars[22] = _bar(base + timedelta(days=22), 11.5, 11.8, 11.4, 11.6)
    bars[40] = _bar(base + timedelta(days=40), 12, 12.1, 11.9, 12.0)
    bars[41] = _bar(base + timedelta(days=41), 12.0, 12.2, 11.95, 12.1)
    bars[42] = _bar(base + timedelta(days=42), 13.5, 13.8, 13.4, 13.6)

    ohlc = parse_ohlc_bars(bars)
    events = [
        {
            "type": "bos",
            "direction": "bullish",
            "event_key": "bos_bullish",
            "bar_index": 30,
            "bar_date": "2024-02-01",
            "leg_start_index": 10,
        },
        {
            "type": "bos",
            "direction": "bullish",
            "event_key": "bos_bullish",
            "bar_index": 55,
            "bar_date": "2024-02-26",
            "leg_start_index": 40,
        },
        {
            "type": "choch",
            "direction": "bearish",
            "event_key": "choch_bearish",
            "bar_index": 70,
            "bar_date": "2024-03-12",
            "leg_start_index": 60,
        },
    ]
    obs = detect_order_blocks(ohlc, events, max_blocks=6)
    assert obs
    dates = [str(b.get("bar_date") or "") for b in obs]
    assert dates == sorted(dates, reverse=True)

    fvgs = detect_fvgs(ohlc, atr=1.0, min_pct=0.001, atr_mult=0.01, max_fvgs=8)
    assert fvgs
    fvg_dates = [str(f.get("end_date") or "") for f in fvgs]
    assert fvg_dates == sorted(fvg_dates, reverse=True)
