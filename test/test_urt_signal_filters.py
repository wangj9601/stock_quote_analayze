# -*- coding: utf-8 -*-
"""URT 信号因子硬闸与精选模式。"""

from backend_core.strategies.urt.signal_filters import (
    build_signal_filter_from_cfg,
    evaluate_ma_bull_mid_gate,
    needs_confluence_enrichment,
    passes_signal_factor_filter,
    signal_quality_mode_label,
)
from backend_core.strategies.urt.signal_detector import build_buy_logic


def _cfg(**kw):
    base = {
        "exclude_ma_bull_score_mid_enabled": True,
        "exclude_ma_bull_score_lo": 4.0,
        "exclude_ma_bull_score_hi": 7.0,
        "premium_signal_near_support_max_pct": 2.0,
        "premium_signal_exclude_score_ge": 90.0,
        "premium_signal_exclude_hvz_near_max_pct": 1.0,
        "min_score": 70,
    }
    base.update(kw)
    return base


def test_ma_bull_mid_gate_blocks_weak_band():
    sd = {"parts": {"ma_bull": {"score": 5.0, "depth": 3}}}
    gate = evaluate_ma_bull_mid_gate(sd, _cfg())
    assert gate["blocked"] is True
    assert gate["pass"] is False


def test_ma_bull_mid_gate_allows_outside_band():
    sd = {"parts": {"ma_bull": {"score": 7.5, "depth": 5}}}
    gate = evaluate_ma_bull_mid_gate(sd, _cfg())
    assert gate["blocked"] is False


def test_ma_bull_mid_gate_disabled():
    sd = {"parts": {"ma_bull": {"score": 5.0}}}
    gate = evaluate_ma_bull_mid_gate(sd, _cfg(exclude_ma_bull_score_mid_enabled=False))
    assert gate["enabled"] is False
    assert gate["blocked"] is False


def test_build_signal_filter_standard_vs_premium():
    std = build_signal_filter_from_cfg(_cfg(), "standard")
    assert std == {"exclude_ma_bull_range": [4.0, 7.0]}
    prem = build_signal_filter_from_cfg(_cfg(), "premium")
    assert prem["require_dist_to_support_max"] == 2.0
    assert prem["exclude_score_ge"] == 90.0
    assert prem["exclude_hvz_near_resistance_max_pct"] == 1.0
    # 显式关闭 HVZ 闸
    prem_off = build_signal_filter_from_cfg(
        _cfg(premium_signal_exclude_hvz_near_max_pct=0), "premium"
    )
    assert "exclude_hvz_near_resistance_max_pct" not in prem_off


def test_passes_signal_factor_filter_premium():
    sig = {
        "score": 85,
        "score_detail": {
            "parts": {
                "ma_bull": {"score": 7.0},
                "structure_position": {
                    "score": 10.0,
                    "close": 10.0,
                    "nearest_support": 9.85,
                },
            }
        },
    }
    flt = build_signal_filter_from_cfg(_cfg(), "premium")
    assert passes_signal_factor_filter(sig, flt) is True

    sig_weak = {
        "score": 85,
        "score_detail": {"parts": {"ma_bull": {"score": 5.0}}},
    }
    assert passes_signal_factor_filter(sig_weak, flt) is False

    sig_hvz = {
        "score": 85,
        "close": 10.9,
        "score_detail": {
            "parts": {
                "ma_bull": {"score": 7.0},
                "structure_position": {
                    "close": 10.9,
                    "nearest_support": 10.7,
                },
            },
            "structure": {
                "nearest_resistance": 10.97,
                "confluence_resistance_zone": {
                    "chips_hvz": True,
                    "center": 10.97,
                    "low": 10.96,
                },
            },
        },
    }
    assert passes_signal_factor_filter(sig_hvz, flt) is False


def test_needs_confluence_enrichment():
    assert needs_confluence_enrichment({}, {"exclude_chips_void_support": True}) is True
    assert needs_confluence_enrichment({"structure_use_zone_band_exit": True}, None) is True
    assert needs_confluence_enrichment({}, {"exclude_ma_bull_range": [4, 7]}) is False


def test_passes_chips_void_filter():
    sig_void = {
        "score": 80,
        "score_detail": {
            "structure": {
                "nearest_support": 10.55,
                "confluence_support_zone": {"tier": "strong", "chips_void": True, "center": 10.55},
            }
        },
    }
    flt = {"exclude_chips_void_support": True, "require_support_tier_strong": True}
    assert passes_signal_factor_filter(sig_void, flt) is False

    sig_ok = {
        "score": 80,
        "score_detail": {
            "structure": {
                "nearest_support": 10.2,
                "confluence_support_zone": {"tier": "strong", "center": 10.2},
            }
        },
    }
    assert passes_signal_factor_filter(sig_ok, flt) is True


def test_passes_hvz_near_gate():
    sig_hvz = {
        "score": 80,
        "close": 10.9,
        "score_detail": {
            "structure": {
                "nearest_resistance": 10.97,
                "confluence_resistance_zone": {
                    "tier": "strong",
                    "chips_hvz": True,
                    "center": 10.97,
                    "low": 10.96,
                },
            }
        },
    }
    flt = {"exclude_hvz_near_resistance_max_pct": 1.0}
    assert passes_signal_factor_filter(sig_hvz, flt) is False

    sig_far = {
        "score": 80,
        "score_detail": {
            "structure": {
                "nearest_resistance": 12.0,
                "confluence_resistance_zone": {"chips_hvz": True, "center": 12.0},
            },
            "parts": {
                "structure_position": {"close": 10.0, "nearest_support": 9.8},
            },
        },
    }
    assert passes_signal_factor_filter(sig_far, flt) is True


def test_build_buy_logic_includes_ma_bull_mid_step():
    detail = {
        "score": 78,
        "score_ok": True,
        "filter_ok": True,
        "structure_gate_ok": True,
        "overheat_gate_ok": True,
        "ma_bull_mid_gate_ok": True,
        "score_detail": {"parts": {"ma_bull": {"score": 7.5}}},
    }
    logic = build_buy_logic(detail, _cfg())
    ids = [s["id"] for s in logic["steps"]]
    assert "ma_bull_mid_gate" in ids


def test_signal_quality_mode_label():
    assert "精选" in signal_quality_mode_label("premium")
    assert "HVZ" in signal_quality_mode_label("premium")
    assert "标准" in signal_quality_mode_label("standard")
