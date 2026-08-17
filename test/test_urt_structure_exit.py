# -*- coding: utf-8 -*-
"""URT 结构出场：止损/止盈价位与逐日判定（含全路径保护 / 分批 / 跟踪）。"""

from __future__ import annotations

from backend_core.strategies.urt.signal_detector import (
    compute_weak_structure_levels,
    evaluate_structure_exit_rules,
    extract_signal_structure_levels,
    resolve_structure_exit_levels,
    step_structure_fallback_protection,
)


def test_resolve_structure_stop_and_resistance_target():
    levels = resolve_structure_exit_levels(
        entry_price=10.0,
        nearest_support=9.5,
        nearest_resistance=11.5,
        cfg={"structure_stop_buffer_pct": 0.02, "structure_exit_min_upside_pct": 0.05},
        target_pct=0.10,
    )
    assert levels["structure_fallback"] is False
    assert levels["fallback_reason"] is None
    assert levels["stop_basis"] == "structure_support"
    assert abs(levels["stop_price"] - 9.5 * 0.98) < 1e-6
    assert levels["target_basis"] == "structure_resistance"
    assert levels["target_price"] == 11.5


def test_resolve_fallback_no_support_and_low_upside():
    levels = resolve_structure_exit_levels(
        entry_price=10.0,
        nearest_support=None,
        nearest_resistance=10.1,  # +1% < 5%
        cfg={
            "structure_stop_buffer_pct": 0.02,
            "structure_exit_min_upside_pct": 0.05,
            "structure_fallback_stop_loss_pct": 10,
            "risk": {"stop_loss_pct_max": 10},
        },
        target_pct=0.10,
    )
    assert levels["structure_fallback"] is True
    assert levels["fallback_reason"] == "no_support"
    assert levels["stop_basis"] == "pct_fallback_no_support"
    assert levels["stop_price"] == 9.0
    assert levels["target_basis"] == "pct_target_low_upside"
    assert levels["target_price"] == 11.0


def test_exit_min_upside_rejects_near_resistance():
    # +4% 阻力：旧 3% 门槛会用阻力；新默认 5% 应改走百分比
    levels = resolve_structure_exit_levels(
        entry_price=10.0,
        nearest_support=9.5,
        nearest_resistance=10.4,
        cfg={"structure_exit_min_upside_pct": 0.05},
        target_pct=0.10,
    )
    assert levels["target_basis"] == "pct_target_low_upside"
    assert levels["target_price"] == 11.0


def test_resolve_fallback_stop_above_entry_reason():
    levels = resolve_structure_exit_levels(
        entry_price=10.0,
        nearest_support=10.5,  # 10.5×0.98=10.29 ≥ 入场 → 回退
        nearest_resistance=None,
        cfg={"structure_stop_buffer_pct": 0.02, "structure_fallback_stop_loss_pct": 8},
        target_pct=0.10,
    )
    assert levels["structure_fallback"] is True
    assert levels["fallback_reason"] == "stop_above_entry"
    assert abs(levels["stop_price"] - 9.2) < 1e-6


def test_p3_default_fallback_stop_is_8():
    levels = resolve_structure_exit_levels(
        entry_price=10.0,
        nearest_support=None,
        cfg={"risk": {"stop_loss_pct_max": 10}},
        target_pct=0.10,
    )
    assert abs(levels["stop_price"] - 9.2) < 1e-6
    assert levels["fallback_stop_loss_pct"] == 8.0


def test_evaluate_structure_stop_priority_over_target():
    hit = evaluate_structure_exit_rules(
        entry_price=10.0,
        last_close=9.2,
        last_high=11.6,
        stop_price=9.31,
        target_price=11.5,
        target_basis="structure_resistance",
        stop_basis="structure_support",
    )
    assert hit is not None
    assert hit["exit_reason"] == "structure_stop"


def test_evaluate_structure_target_and_pct_target():
    st = evaluate_structure_exit_rules(
        entry_price=10.0,
        last_close=10.5,
        last_high=11.6,
        stop_price=9.0,
        target_price=11.5,
        target_basis="structure_resistance",
        stop_basis="structure_support",
    )
    assert st and st["exit_reason"] == "structure_target"

    pt = evaluate_structure_exit_rules(
        entry_price=10.0,
        last_close=10.8,
        last_high=11.1,
        stop_price=9.0,
        target_price=11.0,
        target_basis="pct_target",
        stop_basis="pct_fallback_no_support",
    )
    assert pt and pt["exit_reason"] == "pct_target"


def test_evaluate_pct_fallback_stop_reason():
    hit = evaluate_structure_exit_rules(
        entry_price=10.0,
        last_close=8.9,
        last_high=9.5,
        stop_price=9.0,
        target_price=11.0,
        stop_basis="pct_fallback_no_support",
        target_basis="pct_target",
    )
    assert hit and hit["exit_reason"] == "price_stop"


def test_extract_signal_structure_from_score_detail():
    sig = {
        "score_detail": {
            "structure": {
                "nearest_support": 12.3,
                "nearest_resistance": 14.0,
                "rr": 2.5,
                "kde_ok": True,
            }
        }
    }
    st = extract_signal_structure_levels(sig)
    assert st["nearest_support"] == 12.3
    assert st["nearest_resistance"] == 14.0
    assert st["structure_rr"] == 2.5


def test_p1_fallback_protection_breakeven_and_trail():
    # 浮盈未达 6.5%：不武装
    s0 = step_structure_fallback_protection(
        entry_price=10.0,
        peak_high=10.5,
        last_close=10.4,
        stop_price=9.2,
        armed=False,
        cfg={"structure_protect_arm_pct": 0.065, "structure_protect_trail_drawdown_pct": 0.04},
    )
    assert s0["armed"] is False
    assert s0["exit_reason"] is None

    # 峰值 +8%：武装，止损抬到 max(成本, 峰值回撤)
    s1 = step_structure_fallback_protection(
        entry_price=10.0,
        peak_high=10.8,
        last_close=10.6,
        stop_price=9.2,
        armed=False,
        cfg={"structure_protect_arm_pct": 0.065, "structure_protect_trail_drawdown_pct": 0.04},
    )
    assert s1["armed"] is True
    assert s1["stop_price"] >= 10.0

    # 收盘跌破抬升止损 → trail / breakeven
    s2 = step_structure_fallback_protection(
        entry_price=10.0,
        peak_high=11.0,
        last_close=10.0,
        stop_price=9.2,
        armed=True,
        cfg={"structure_protect_arm_pct": 0.065, "structure_protect_trail_drawdown_pct": 0.04},
    )
    assert s2["exit_reason"] in ("breakeven_stop", "fallback_trail")


def test_global_protect_enabled_key():
    s = step_structure_fallback_protection(
        entry_price=10.0,
        peak_high=11.0,
        last_close=10.5,
        stop_price=9.2,
        armed=False,
        cfg={"structure_protect_enabled": False, "structure_fallback_protect_enabled": False},
    )
    assert s["armed"] is False
    assert s["stop_price"] == 9.2


def test_p2_weak_structure_from_swing_low():
    # DESC: 最新在前；信号日 close=10，前几日低点 9.0
    bars = [
        {"close": 10.0, "high": 10.2, "low": 9.8},
        {"close": 9.7, "high": 9.9, "low": 9.5},
        {"close": 9.6, "high": 10.5, "low": 9.0},
        {"close": 9.4, "high": 9.8, "low": 9.2},
        {"close": 9.3, "high": 9.6, "low": 9.1},
        {"close": 9.2, "high": 9.5, "low": 9.0},
    ]
    weak = compute_weak_structure_levels(bars, price=10.0, cfg={"structure_weak_lookback": 20})
    assert weak["ok"] is True
    assert weak["nearest_support"] == 9.0
    assert weak["structure_source"] == "weak_swing"
    assert weak["nearest_resistance"] == 10.5
