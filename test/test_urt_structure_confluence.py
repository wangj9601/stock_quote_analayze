# -*- coding: utf-8 -*-
"""URT 信号日结构位：结构锚窗 + confluence 选取。"""

from __future__ import annotations

from backend_core.strategies.urt.signal_detector import _pick_confluence_nearest


def test_pick_confluence_nearest_prefers_strong_tier():
    conf = {
        "ok": True,
        "supports": [
            {"center": 9.0, "tier": "normal", "low": 8.9, "high": 9.1},
            {"center": 9.5, "tier": "strong", "low": 9.4, "high": 9.6},
            {"center": 8.5, "tier": "strong", "low": 8.4, "high": 8.6},
        ],
        "resistances": [
            {"center": 11.0, "tier": "normal", "low": 10.9, "high": 11.1},
            {"center": 10.8, "tier": "strong", "low": 10.7, "high": 10.9},
        ],
        "nearest_support_zone": {"center": 9.0, "tier": "normal"},
        "nearest_resistance_zone": {"center": 11.0, "tier": "normal"},
    }
    picked = _pick_confluence_nearest(conf, 10.0, prefer_strong=True)
    assert picked["nearest_support"] == 9.5  # 下方最近 strong
    assert picked["nearest_resistance"] == 10.8  # 上方最近 strong
    assert picked["pick"] == "confluence_strong"


def test_pick_confluence_falls_back_to_nearest_zone():
    conf = {
        "ok": True,
        "supports": [{"center": 9.2, "tier": "normal"}],
        "resistances": [{"center": 11.2, "tier": "normal"}],
        "nearest_support_zone": {"center": 9.2, "tier": "normal"},
        "nearest_resistance_zone": {"center": 11.2, "tier": "normal"},
    }
    picked = _pick_confluence_nearest(conf, 10.0, prefer_strong=True)
    assert picked["nearest_support"] == 9.2
    assert picked["nearest_resistance"] == 11.2
    assert picked["pick"] == "confluence"
