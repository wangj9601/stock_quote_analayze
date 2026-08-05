# -*- coding: utf-8 -*-
"""GMS 结构盈亏比减分 poor_structure_rr。"""

from backend_core.strategies.gms.scoring.penalties import PenaltyEngine, PENALTY_RULE_TYPES
from backend_core.strategies.gms.structure_levels import compute_structure_rr


def test_penalty_rule_type_registered():
    assert "poor_structure_rr" in PENALTY_RULE_TYPES
    assert PENALTY_RULE_TYPES["poor_structure_rr"]["default_min_rr"] == 1.5


def test_compute_structure_rr_ok_and_low():
    info = compute_structure_rr(10.0, 8.0, 14.0)
    assert info["reason"] == "ok"
    assert abs(info["rr"] - 2.0) < 1e-6
    assert info["should_penalize"] is None

    low = compute_structure_rr(10.0, 8.0, 11.0)
    assert low["reason"] == "ok"
    assert abs(low["rr"] - 0.5) < 1e-6


def test_compute_structure_rr_edge_cases():
    assert compute_structure_rr(10.0, None, 12.0)["should_penalize"] is False
    assert compute_structure_rr(10.0, 8.0, None)["should_penalize"] is False
    below = compute_structure_rr(7.0, 8.0, 12.0)
    assert below["should_penalize"] is True
    assert below["reason"] == "below_or_no_support"
    at_res = compute_structure_rr(12.0, 8.0, 12.0)
    assert at_res["should_penalize"] is True
    assert at_res["rr"] == 0.0


def _penalty_cfg(min_rr=1.5, points=10):
    return {
        "scoring": {
            "mechanism": "tiered_dual_penalty",
            "penalty_rules": [
                {
                    "id": "poor_structure_rr",
                    "enabled": True,
                    "points": points,
                    "label": "结构盈亏比偏低",
                    "min_rr": min_rr,
                }
            ],
        }
    }


def test_penalty_engine_deducts_when_rr_low():
    engine = PenaltyEngine(_penalty_cfg(min_rr=1.5, points=10))
    row = {
        "d20": 59.93,
        "nearest_support": 34.49,
        "nearest_resistance": 62.02,
    }
    total, details = engine.apply(row)
    assert total == 10
    assert len(details) == 1
    assert details[0]["id"] == "poor_structure_rr"
    assert details[0]["rr"] is not None
    assert details[0]["rr"] < 1.5
    assert details[0]["min_rr"] == 1.5


def test_penalty_engine_no_deduct_when_rr_ok():
    engine = PenaltyEngine(_penalty_cfg(min_rr=1.5, points=10))
    row = {
        "d20": 10.0,
        "nearest_support": 8.0,
        "nearest_resistance": 14.0,  # RR=2.0
    }
    total, details = engine.apply(row)
    assert total == 0
    assert details == []


def test_penalty_engine_no_deduct_without_resistance():
    engine = PenaltyEngine(_penalty_cfg())
    row = {"d20": 10.0, "nearest_support": 8.0, "nearest_resistance": None}
    total, _ = engine.apply(row)
    assert total == 0


def test_penalty_engine_deducts_below_support():
    engine = PenaltyEngine(_penalty_cfg(points=12))
    row = {"d20": 7.0, "nearest_support": 8.0, "nearest_resistance": 12.0}
    total, details = engine.apply(row)
    assert total == 12
    assert details[0]["rr_reason"] == "below_or_no_support"


def test_standard_mechanism_unaffected_by_structure_on_row():
    """标准版配置 penalty_rules 为空时即使有 SR 也不扣分。"""
    engine = PenaltyEngine({"scoring": {"mechanism": "tiered_dual_max", "penalty_rules": []}})
    row = {"d20": 59.93, "nearest_support": 34.49, "nearest_resistance": 62.02}
    total, details = engine.apply(row)
    assert total == 0
    assert details == []


def test_validate_scoring_accepts_min_rr():
    from backend_core.strategies.gms.scoring.registry import validate_scoring_config

    errs = validate_scoring_config(
        {
            "mechanism": "tiered_dual_penalty",
            "penalty_rules": [
                {"id": "poor_structure_rr", "enabled": True, "points": 10, "min_rr": 1.5}
            ],
        }
    )
    assert errs == []
    bad = validate_scoring_config(
        {
            "mechanism": "tiered_dual_penalty",
            "penalty_rules": [
                {"id": "poor_structure_rr", "enabled": True, "points": 10, "min_rr": 0}
            ],
        }
    )
    assert any("min_rr" in e for e in bad)
