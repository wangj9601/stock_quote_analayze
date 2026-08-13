# -*- coding: utf-8 -*-
"""短期三态与结构买点（pattern_tactical）单测。"""

from __future__ import annotations

from backend_core.analysis.pattern_tactical import (
    RESONANCE_PRESSURE_MIN_STRENGTH,
    build_buy_hints,
    build_pattern_tactical,
    classify_short_bias,
)


def _hit(
    pattern_type,
    status,
    *,
    confidence=0.8,
    neckline=None,
    upper=None,
    lower=None,
    last_close=None,
    formed_at="2026-01-10",
):
    levels = {}
    if neckline is not None:
        levels["neckline"] = neckline
    if upper is not None:
        levels["upper"] = upper
    if lower is not None:
        levels["lower"] = lower
    if last_close is not None:
        levels["last_close"] = last_close
    return {
        "pattern_type": pattern_type,
        "pattern_family": "test",
        "status": status,
        "confidence": confidence,
        "reason": "unit",
        "key_levels": levels,
        "formed_at": formed_at,
        "pivots": [],
    }


def test_bull_confirmed_above_neck():
    hits = [
        _hit(
            "head_shoulders_bottom",
            "confirmed",
            neckline=10.0,
            lower=8.5,
            last_close=10.2,
        )
    ]
    out = build_pattern_tactical(hits)
    assert out["short_bias"] == "看多"
    assert out["grade"] == "base"
    assert out["buy_hints"]
    assert out["buy_hints"][0]["type"] in ("pullback_buy", "watch")
    assert out["disclaimer"]


def test_bear_confirmed_below_neck_no_hints():
    hits = [
        _hit(
            "head_shoulders_top",
            "confirmed",
            neckline=20.0,
            upper=22.0,
            last_close=19.5,
        )
    ]
    out = build_pattern_tactical(hits)
    assert out["short_bias"] == "看空"
    assert out["buy_hints"] == []
    assert out["risk_note"]
    assert "破位" in out["risk_note"] or "不宜" in out["risk_note"]


def test_forming_with_strong_pressure_is_range():
    hits = [
        _hit(
            "ascending_triangle",
            "forming",
            upper=12.0,
            lower=10.0,
            last_close=11.5,
            confidence=0.7,
        )
    ]
    confluence = {
        "ok": True,
        "nearest_resistance_zone": {
            "center": 11.8,
            "low": 11.7,
            "high": 11.9,
            "strength": RESONANCE_PRESSURE_MIN_STRENGTH + 5,
        },
        "resistances": [],
        "supports": [],
    }
    out = build_pattern_tactical(hits, confluence=confluence)
    assert out["short_bias"] == "震荡"
    assert any(e.get("code") == "resonance_pressure" and e.get("ok") for e in out["evidence"])
    assert out["buy_hints"]
    assert out["buy_hints"][0]["type"] == "watch"


def test_vp_rpe_only_lift_grade_not_bias():
    hits = [
        _hit(
            "double_bottom",
            "confirmed",
            neckline=5.0,
            lower=4.2,
            last_close=5.2,
        )
    ]
    base = build_pattern_tactical(hits)
    assert base["short_bias"] == "看多"
    assert base["grade"] == "base"

    vp = {
        "ok": True,
        "vah": 5.0,
        "last_close": 5.2,
        "nearest_resistance": None,
        "resistance_note": "已突破60日VAH(5.00)，上方无60日筹码压制",
    }
    rpe = {"z_score": 2.5, "signal_type": "领涨观察"}
    enh = build_pattern_tactical(hits, vp=vp)
    assert enh["short_bias"] == "看多"
    assert enh["grade"] == "enhanced"

    strong = build_pattern_tactical(hits, vp=vp, rpe=rpe)
    assert strong["short_bias"] == "看多"
    assert strong["grade"] == "strong"
    assert any(e.get("code") == "vp_break_vah" and e.get("ok") for e in strong["evidence"])
    assert any(e.get("code") == "rpe_lead" and e.get("ok") for e in strong["evidence"])


def test_zero_hits_with_invalidated_count():
    out = build_pattern_tactical([], invalidated_count=3)
    assert out["short_bias"] in ("震荡", "insufficient")
    assert out["buy_hints"] == []
    assert any(e.get("code") == "no_active_hits" for e in out["evidence"])


def test_consol_confirmed_up_is_bull():
    hits = [
        _hit(
            "falling_wedge",
            "confirmed",
            upper=10.0,
            lower=8.0,
            last_close=10.1,  # > upper * 1.005
            confidence=0.75,
        )
    ]
    c = classify_short_bias(hits)
    assert c["short_bias"] == "看多"


def test_consol_confirmed_down_is_bear():
    hits = [
        _hit(
            "rising_wedge",
            "confirmed",
            upper=10.0,
            lower=8.0,
            last_close=7.9,  # < lower * 0.995
            confidence=0.75,
        )
    ]
    c = classify_short_bias(hits)
    assert c["short_bias"] == "看空"
    hints, risk = build_buy_hints("看空", hits[0], grade="base")
    assert hints == []
    assert risk


def test_forming_without_pressure_is_range():
    hits = [
        _hit(
            "double_bottom",
            "forming",
            neckline=10.0,
            lower=8.0,
            last_close=9.5,
        )
    ]
    out = build_pattern_tactical(hits)
    assert out["short_bias"] == "震荡"
    assert out["grade"] == "base"
