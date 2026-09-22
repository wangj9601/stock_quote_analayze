# -*- coding: utf-8 -*-
"""KGT 袋鼠尾 detector：看涨 / 看跌 / 边界拒绝。"""

from backend_core.strategies.kangaroo_tail.detector import (
    detect_kangaroo_tail,
    detect_kangaroo_tail_bar,
)


def _pad_ma_bars(n: int = 25, close: float = 10.0):
    """前导平稳 K 线，使 MA20 ≈ close。"""
    bars = []
    for i in range(1, n + 1):
        bars.append(
            {
                "date": f"2025-01-{i:02d}",
                "open": close,
                "high": close + 0.05,
                "low": close - 0.05,
                "close": close,
                "volume": 1e6,
            }
        )
    return bars


def _bullish_tail_bar(date: str = "2025-02-01", *, base: float = 10.0):
    """典型看涨袋鼠尾：长下影、短上影、小实体、收在上半区。"""
    # low=9.0, open=9.9, close=10.0, high=10.05 → range=1.05, body=0.1
    # lower=0.9 ≥ max(0.2, 0.525)；upper=0.05 ≤ 0.03? body*0.3=0.03 — 稍紧
    # 调整：open=9.85, close=10.0, high=10.02, low=9.0
    # range=1.02, body=0.15, lower=0.85, upper=0.02
    # need=max(0.3, 0.51)=0.51；opp=0.045；close_pos=(10-9)/1.02≈0.98
    return {
        "date": date,
        "open": base - 0.15,
        "high": base + 0.02,
        "low": base - 1.0,
        "close": base,
        "volume": 1.2e6,
    }


def _bearish_tail_bar(date: str = "2025-02-01", *, base: float = 10.0):
    """典型看跌袋鼠尾：长上影、短下影、小实体、收在下半区。"""
    return {
        "date": date,
        "open": base + 0.15,
        "high": base + 1.0,
        "low": base - 0.02,
        "close": base,
        "volume": 1.2e6,
    }


def test_bullish_bar_hit():
    bar = _bullish_tail_bar()
    hit = detect_kangaroo_tail_bar(
        bar,
        pattern_cfg={"require_trend_filter": False},
        ma20=None,
    )
    assert hit is not None
    assert hit["direction"] == "bullish"
    assert hit["pattern_type"] == "kangaroo_tail_bullish"
    assert hit["score"] > 0
    assert hit["signal_date"] == "2025-02-01"


def test_bearish_bar_hit():
    bar = _bearish_tail_bar()
    hit = detect_kangaroo_tail_bar(
        bar,
        pattern_cfg={"require_trend_filter": False},
        ma20=None,
    )
    assert hit is not None
    assert hit["direction"] == "bearish"
    assert hit["pattern_type"] == "kangaroo_tail_bearish"


def test_reject_large_body():
    # 实体过大：open=9.2 close=10.0 high=10.05 low=9.0 → body/range≈0.76
    bar = {
        "date": "2025-02-01",
        "open": 9.2,
        "high": 10.05,
        "low": 9.0,
        "close": 10.0,
    }
    hit = detect_kangaroo_tail_bar(
        bar, pattern_cfg={"require_trend_filter": False}, ma20=None
    )
    assert hit is None


def test_reject_small_range():
    # 振幅 <2%
    bar = {
        "date": "2025-02-01",
        "open": 10.0,
        "high": 10.05,
        "low": 9.95,
        "close": 10.02,
    }
    hit = detect_kangaroo_tail_bar(
        bar, pattern_cfg={"require_trend_filter": False}, ma20=None
    )
    assert hit is None


def test_trend_filter_bullish_requires_low_below_ma():
    bar = _bullish_tail_bar()
    # low=9.0；若 MA20=8.5，则 low > MA，趋势过滤应拒绝
    hit = detect_kangaroo_tail_bar(
        bar,
        pattern_cfg={"require_trend_filter": True},
        ma20=8.5,
    )
    assert hit is None
    hit_ok = detect_kangaroo_tail_bar(
        bar,
        pattern_cfg={"require_trend_filter": True},
        ma20=10.5,
    )
    assert hit_ok is not None
    assert hit_ok["direction"] == "bullish"


def test_directions_filter_bearish_only():
    bar = _bullish_tail_bar()
    hit = detect_kangaroo_tail_bar(
        bar,
        pattern_cfg={"require_trend_filter": False, "directions": "bearish"},
        ma20=None,
    )
    assert hit is None


def test_detect_kangaroo_tail_on_series():
    bars = _pad_ma_bars(25, close=10.0)
    # 末根看涨尾，且 low=9 < MA20≈10
    bars.append(_bullish_tail_bar(date="2025-02-01", base=10.0))
    hit = detect_kangaroo_tail(
        bars,
        pattern_cfg={"require_trend_filter": True, "ma_period": 20},
    )
    assert hit is not None
    assert hit["direction"] == "bullish"
    assert hit["signal_date"] == "2025-02-01"


def test_detect_in_bars_chart_fields():
    """形态工具扫描字段（不经 chart_patterns 包，避免 cup_bottom 循环导入）。"""
    from backend_core.strategies.kangaroo_tail.detector import (
        detect_kangaroo_tails_in_bars,
    )

    bars = _pad_ma_bars(25, close=10.0)
    bars.append(_bullish_tail_bar(date="2025-02-01", base=10.0))
    hits = detect_kangaroo_tails_in_bars(
        bars, pattern_cfg={"require_trend_filter": False}, max_hits=5
    )
    assert hits
    h0 = hits[0]
    assert h0["pattern_type"] == "kangaroo_tail_bullish"
    assert h0["formed_at"] == "2025-02-01"
    assert 0 < h0["confidence"] <= 1
    assert "key_levels" in h0
    assert h0["pivots"]


def test_engine_registers_kangaroo_tail_family():
    """直接读 engine 源，确认家族已注册（避免触发包循环导入）。"""
    from pathlib import Path

    text = (
        Path(__file__).resolve().parents[1]
        / "backend_core"
        / "analysis"
        / "chart_patterns"
        / "engine.py"
    ).read_text(encoding="utf-8")
    assert '"kangaroo_tail"' in text
    assert "detect_kangaroo_tail_patterns" in text
