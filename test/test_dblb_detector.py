# -*- coding: utf-8 -*-
"""双底 detector：forming / confirmed / 拒绝分支。"""

from backend_core.strategies.double_bottom.detector import detect_double_bottom


def _bars_w(*, breakout: bool = False, gap: int = 12, tol_bad: bool = False):
    """合成一段 W：下跌 → 底1 → 反弹颈线 → 底2 → 可选突破。"""
    bars = []
    # 前导
    for i in range(10):
        px = 12.0 - i * 0.05
        bars.append(
            {
                "date": f"2025-01-{i+1:02d}",
                "high": px + 0.1,
                "low": px - 0.1,
                "close": px,
                "volume": 1e6,
            }
        )
    # 底1 区域
    base1 = 10.0
    bars.append(
        {
            "date": "2025-01-11",
            "high": base1 + 0.3,
            "low": base1,
            "close": base1 + 0.15,
            "volume": 1.2e6,
        }
    )
    # 上升到颈线
    for i in range(1, gap // 2 + 1):
        px = base1 + i * 0.25
        bars.append(
            {
                "date": f"2025-01-{11+i:02d}",
                "high": px + 0.15,
                "low": px - 0.15,
                "close": px,
                "volume": 1e6,
            }
        )
    neck = base1 + (gap // 2) * 0.25
    # 回落到底2
    for i in range(1, gap // 2 + 1):
        px = neck - i * 0.25
        bars.append(
            {
                "date": f"2025-02-{i:02d}",
                "high": px + 0.15,
                "low": px - 0.15,
                "close": px,
                "volume": 1e6,
            }
        )
    base2 = base1 * (1.05 if tol_bad else 1.01)
    bars.append(
        {
            "date": "2025-02-20",
            "high": base2 + 0.3,
            "low": base2,
            "close": base2 + 0.1,
            "volume": 1.1e6,
        }
    )
    # 再抬升
    for i in range(1, 6):
        px = base2 + i * 0.2
        bars.append(
            {
                "date": f"2025-02-{20+i:02d}",
                "high": px + 0.1,
                "low": px - 0.1,
                "close": px,
                "volume": 1.5e6 if breakout and i == 5 else 1e6,
            }
        )
    if breakout:
        # 确保最后收盘突破颈线
        bars[-1]["close"] = neck + 0.5
        bars[-1]["high"] = neck + 0.6
        bars[-1]["low"] = neck + 0.2
        bars[-1]["volume"] = 2e6
    else:
        # 停留在颈线下方
        bars[-1]["close"] = neck - 0.2
        bars[-1]["high"] = neck - 0.05
        bars[-1]["low"] = neck - 0.4
    return bars


def test_forming_without_breakout():
    hit = detect_double_bottom(
        _bars_w(breakout=False),
        pattern_cfg={
            "lookback_days": 120,
            "swing_left": 1,
            "swing_right": 1,
            "min_trough_gap_bars": 4,
            "max_trough_gap_bars": 40,
            "trough_tol_pct": 0.05,
            "min_rise_to_neck_pct": 0.03,
            "max_rise_to_neck_pct": 0.25,
        },
    )
    assert hit is not None
    assert hit["status"] == "forming"
    assert hit["neckline"] is not None
    assert hit["confirm_date"] is None


def test_confirmed_with_breakout():
    hit = detect_double_bottom(
        _bars_w(breakout=True),
        pattern_cfg={
            "lookback_days": 120,
            "swing_left": 1,
            "swing_right": 1,
            "min_trough_gap_bars": 4,
            "max_trough_gap_bars": 40,
            "trough_tol_pct": 0.05,
            "min_rise_to_neck_pct": 0.03,
            "max_rise_to_neck_pct": 0.25,
        },
    )
    assert hit is not None
    assert hit["status"] == "confirmed"
    assert hit["confirm_date"]


def test_reject_trough_too_far():
    hit = detect_double_bottom(
        _bars_w(breakout=False, tol_bad=True),
        pattern_cfg={
            "lookback_days": 120,
            "swing_left": 1,
            "swing_right": 1,
            "min_trough_gap_bars": 4,
            "max_trough_gap_bars": 40,
            "trough_tol_pct": 0.01,  # 很严
            "min_rise_to_neck_pct": 0.03,
            "max_rise_to_neck_pct": 0.25,
        },
    )
    assert hit is None


def test_reject_rise_to_neck_too_deep():
    """深度超过 max_rise_to_neck_pct 时硬否决。"""
    # gap=20 → 上升 10*0.25=2.5 / base10 = 25% > 15%
    hit = detect_double_bottom(
        _bars_w(breakout=False, gap=20),
        pattern_cfg={
            "lookback_days": 160,
            "swing_left": 1,
            "swing_right": 1,
            "min_trough_gap_bars": 4,
            "max_trough_gap_bars": 60,
            "trough_tol_pct": 0.05,
            "min_rise_to_neck_pct": 0.03,
            "max_rise_to_neck_pct": 0.15,
        },
    )
    assert hit is None
    hit_ok = detect_double_bottom(
        _bars_w(breakout=False, gap=20),
        pattern_cfg={
            "lookback_days": 160,
            "swing_left": 1,
            "swing_right": 1,
            "min_trough_gap_bars": 4,
            "max_trough_gap_bars": 60,
            "trough_tol_pct": 0.05,
            "min_rise_to_neck_pct": 0.03,
            "max_rise_to_neck_pct": 0.40,
        },
    )
    assert hit_ok is not None
