# -*- coding: utf-8 -*-
"""URT 打分优化：MA20 梯度、连阳实体、位置/RR、过热扣分。"""

from __future__ import annotations

from backend_core.strategies.urt.config import URTConfigManager
from backend_core.strategies.urt.indicators import compute_candle_quality, ma_relative_slope
from backend_core.strategies.urt.scoring import (
    _ma20_trend_score,
    _overheat_penalty_score,
    _structure_position_score,
    _yang_quality_score,
    compute_score_breakdown,
)


def _cfg(**overrides):
    return URTConfigManager().merge_overrides(None, **overrides)


def test_ma20_slope_helper():
    closes = [20.0 + i * 0.1 for i in range(30)][::-1]  # DESC rising
    slope = ma_relative_slope(closes, ma_period=20, slope_days=5)
    assert slope is not None and slope > 0


def test_ma20_trend_score_gradient_vs_flat():
    cfg = _cfg()
    mild, meta_m = _ma20_trend_score(
        {"above_ma20": True, "ma20_bias": 0.04, "ma20_slope": 0.01},
        cfg,
    )
    flat, meta_f = _ma20_trend_score(
        {"above_ma20": True, "ma20_bias": 0.002, "ma20_slope": 0.0},
        cfg,
    )
    assert mild > flat
    assert meta_m["max"] == 10
    assert meta_f["score"] >= 10 * 0.35  # floor
    zero, _ = _ma20_trend_score({"above_ma20": False, "ma20_bias": 0.05}, cfg)
    assert zero == 0.0


def test_yang_quality_from_candles():
    bars = []
    for i in range(6):
        # 饱满阳线
        bars.append(
            {
                "open": 10.0,
                "close": 11.0,
                "high": 11.1,
                "low": 9.95,
                "volume": 5000.0 if i == 0 else 1000.0,
            }
        )
    q = compute_candle_quality(bars, window=5)
    assert q["avg_body_ratio"] is not None and q["avg_body_ratio"] > 0.5
    assert q["quality_raw"] > 0.4
    part, meta = _yang_quality_score({"yang_quality": q}, _cfg())
    assert meta["max"] == 10
    assert part > 4


def test_yang_days_scaled_to_20():
    cfg = _cfg()
    ind = {
        "above_ma20": True,
        "ma20_bias": 0.03,
        "ma20_slope": 0.005,
        "yang_count_4": 3,
        "yang_count_5": 4,
        "yang_quality": {"quality_raw": 0.5},
        "volume_multiple": 3.0,
        "yang_medium_detail": [],
        "ma_bull_ok": False,
        "ma_bear_ok": False,
        "turnover_rate": None,
    }
    _, detail = compute_score_breakdown(ind, cfg)
    # raw 36 → 36*20/40 = 18
    assert detail["parts"]["yang"]["max"] == 20
    assert detail["parts"]["yang"]["score"] == 18.0
    assert detail["parts"]["yang_quality"]["max"] == 10


def test_structure_position_near_support_and_rr():
    cfg = _cfg()
    near, meta = _structure_position_score(
        {
            "close": 100.0,
            "nearest_support": 99.0,  # 1%
            "structure_rr": 3.5,
            "kde_ok": True,
        },
        cfg,
    )
    assert meta["proximity_score"] == 8.0
    assert meta["rr_score"] == 7.0
    assert near == 15.0

    hang, meta_h = _structure_position_score(
        {
            "close": 100.0,
            "nearest_support": 90.0,  # 10% hanging
            "structure_rr": 1.0,
            "kde_ok": True,
        },
        cfg,
    )
    assert meta_h["proximity_score"] == 0.0
    assert meta_h["rr_score"] == 0.0
    assert hang == 0.0

    missing, meta_m = _structure_position_score(
        {"close": 100.0, "nearest_support": None, "structure_rr": None, "kde_ok": False},
        cfg,
    )
    assert meta_m["proximity_reason"] == "kde_missing_neutral"
    assert meta_m["rr_reason"] == "rr_missing"
    assert missing > 0  # 中性偏低，不误杀


def test_overheat_penalty_ladder():
    cfg = _cfg()
    none, _ = _overheat_penalty_score({"ret_from_low_n": 0.05, "ma20_bias": 0.05}, cfg)
    assert none == 0.0
    soft, meta_s = _overheat_penalty_score({"ret_from_low_n": 0.15, "ma20_bias": 0.0}, cfg)
    assert soft == 0.0 or soft > -10  # 恰在软阈起点 ≈0
    mid, _ = _overheat_penalty_score({"ret_from_low_n": 0.20, "ma20_bias": 0.0}, cfg)
    hard, meta_h = _overheat_penalty_score({"ret_from_low_n": 0.25, "ma20_bias": 0.20}, cfg)
    assert mid < soft
    assert hard == -10.0
    assert meta_h["min"] == -10.0


def test_default_weight_caps():
    cfg = URTConfigManager().get_default_config()
    assert cfg.get("volume_score_max") == 25.0
    assert cfg.get("yang_score_max") == 20.0
    assert cfg.get("yang_quality_score_max") == 10.0
    assert cfg.get("yang_medium_score_max") == 5.0
    assert cfg.get("ma_bull_score_max") == 8.0
    assert cfg.get("ma20_score_mode") == "slope_bias"
    assert cfg.get("overheat_penalty_max") == 10.0
    assert cfg.get("min_score") == 70
