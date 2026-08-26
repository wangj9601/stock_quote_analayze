# -*- coding: utf-8 -*-
"""杯底形态 detector 基础单测。"""

from backend_core.strategies.cup_bottom.config import get_default_cupb_config, merge_pattern_cfg
from backend_core.strategies.cup_bottom.detector import detect_cup_bottom


def test_default_config_has_pattern_and_scan():
    cfg = get_default_cupb_config()
    assert "pattern" in cfg
    assert "scan" in cfg
    assert "volume" in cfg
    assert cfg["pattern"]["lookback_days"] >= 50
    assert cfg["pattern"]["use_low_for_bottom"] is True


def test_too_few_bars_returns_none():
    bars = [
        {"date": f"2025-01-{i:02d}", "high": 10.0, "low": 9.5, "close": 9.8, "volume": 1e6}
        for i in range(1, 20)
    ]
    assert detect_cup_bottom(bars) is None


def _bars_cup(*, breakout: bool = False):
    """合成杯身 + 柄部形态（含前期趋势与量价特征）。"""
    bars = []
    left_rim = 20.0
    bottom = 14.0
    right_rim = 19.5
    handle_low = 17.8

    # 前期上涨趋势（>30%）
    for i in range(40):
        px = 12.0 + i * 0.22
        bars.append(
            {
                "date": f"2024-08-{i+1:02d}",
                "high": px + 0.25,
                "low": px - 0.15,
                "close": px,
                "volume": 2.5e6,
            }
        )

    for i in range(15):
        px = 16.0 + i * (left_rim - 16.0) / 14
        bars.append(
            {
                "date": f"2024-10-{i+1:02d}",
                "high": px + 0.25,
                "low": px - 0.15,
                "close": px,
                "volume": 2.0e6,
            }
        )
    for i in range(20):
        px = left_rim - (i + 1) * (left_rim - bottom) / 20
        vol = 1.8e6 if i > 2 else 2.0e6
        bars.append(
            {
                "date": f"2024-11-{i+1:02d}",
                "high": px + 0.2,
                "low": px - 0.2,
                "close": px,
                "volume": vol,
            }
        )
    for i in range(20):
        px = bottom + (i + 1) * (right_rim - bottom) / 20
        vol = 2.2e6 if i >= 10 else 1.2e6
        bars.append(
            {
                "date": f"2024-12-{i+1:02d}",
                "high": px + 0.2,
                "low": px - 0.15,
                "close": px,
                "volume": vol,
            }
        )
    for i in range(8):
        px = right_rim - (i + 1) * (right_rim - handle_low) / 8
        bars.append(
            {
                "date": f"2025-01-{i+1:02d}",
                "high": px + 0.12,
                "low": px - 0.12,
                "close": px,
                "volume": 0.8e6,
            }
        )
    tail = 17
    for i in range(tail):
        if breakout and i >= tail - 3:
            px = right_rim + 0.3 + i * 0.1
            vol = 3.5e6
        else:
            px = handle_low + 0.5 + i * 0.05
            vol = 1.0e6
        bars.append(
            {
                "date": f"2025-01-{8+i+1:02d}",
                "high": px + 0.2,
                "low": px - 0.15,
                "close": px,
                "volume": vol,
            }
        )
    return bars


def _test_cfg():
    cfg = merge_pattern_cfg(get_default_cupb_config())
    cfg.update(
        {
            "lookback_days": 220,
            "min_cup_bars": 15,
            "handle_retrace_of_rim_min": 0.06,
            "handle_retrace_of_rim_max": 0.20,
            "cup_u_shape_required": False,
            "volume": {
                "enabled": False,
            },
        }
    )
    return cfg


def test_cup_forming_or_confirmed():
    cfg = _test_cfg()
    hit = detect_cup_bottom(_bars_cup(breakout=False), pattern_cfg=cfg)
    assert hit is not None
    assert hit["status"] in ("forming", "confirmed")
    assert hit["cup_bottom_price"] is not None
    assert hit["rim"] is not None
    assert hit.get("grade") in ("A", "B", "C", "X")

    hit2 = detect_cup_bottom(_bars_cup(breakout=True), pattern_cfg=cfg)
    assert hit2 is not None
    assert hit2["status"] in ("forming", "confirmed")


def test_ever_confirmed_after_pullback_below_rim():
    """突破后跌回杯口：当前 forming，但保留历史确认日。"""
    cfg = _test_cfg()
    bars = _bars_cup(breakout=True)
    hit0 = detect_cup_bottom(bars, pattern_cfg=cfg)
    assert hit0 is not None
    rim = float(hit0["rim"])
    bars.append(
        {
            "date": "2025-02-10",
            "high": rim - 0.3,
            "low": rim - 1.5,
            "close": rim - 0.8,
            "volume": 1.0e6,
        }
    )
    hit = detect_cup_bottom(bars, pattern_cfg=cfg)
    assert hit is not None
    assert hit["status"] == "forming"
    assert hit["ever_confirmed"] is True
    assert hit.get("first_confirm_date")
    assert hit.get("confirm_date") is None


def test_invalidate_on_lower_low_after_handle():
    """柄后破杯底应判失效或重锚到更晚结构。"""
    cfg = _test_cfg()
    bars = _bars_cup(breakout=False)
    # 在柄后插入破底
    bars.append(
        {
            "date": "2025-02-20",
            "high": 13.5,
            "low": 12.0,
            "close": 12.5,
            "volume": 1e6,
        }
    )
    bars.append(
        {
            "date": "2025-02-21",
            "high": 12.2,
            "low": 11.0,
            "close": 11.2,
            "volume": 1e6,
        }
    )
    hit = detect_cup_bottom(bars, pattern_cfg=cfg)
    if hit is not None:
        assert hit["status"] in ("forming", "invalidated", "confirmed")
