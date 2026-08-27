# -*- coding: utf-8 -*-
"""URT 信号因子硬闸与精选模式。"""

from backend_core.strategies.urt.signal_filters import (
    build_signal_filter_from_cfg,
    evaluate_ma_bull_mid_gate,
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
    assert "标准" in signal_quality_mode_label("standard")
