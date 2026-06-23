"""
GMS 打分机制注册表与减分规则单元测试。
"""

from __future__ import annotations

from backend_core.strategies.gms.indicators_calculator import GMSIndicatorsCalculator
from backend_core.strategies.gms.scoring import validate_scoring_config
from backend_core.strategies.gms.scoring.penalties import PenaltyEngine
from backend_core.strategies.gms.scoring.tiered_dual_max import TieredDualMaxScorer
from backend_core.strategies.gms.scoring.tiered_dual_penalty import TieredDualPenaltyScorer


def _sample_row(close=10.0, ma60=12.0):
    return {
        "code": "600519",
        "date": "2026-05-10",
        "market_type": "CN",
        "macro_displacement_delta": -0.5,
        "ma20_d": 10.0,
        "ratio_d20": 0.01,
        "ratio_d1": 0.02,
        "instant_deviation": 0.1,
        "rising_days_z": 5,
        "falling_days_f": 10,
        "mavol20_m": 1000.0,
        "efficiency_m20_minus_m": 100.0,
        "current_volume": 800.0,
        "volume_ratio": 0.8,
        "ratio_d": 0.01,
        "d20": close,
        "ma60_d": ma60,
    }


def test_tiered_dual_max_matches_calculator_facade():
    config = {"scoring": {"mechanism": "tiered_dual_max"}}
    row = _sample_row()
    a = TieredDualMaxScorer(config).calculate(row)
    b = GMSIndicatorsCalculator(config).calculate(row)
    assert a is not None and b is not None
    assert a.score_total == b.score_total
    assert a.score_accumulation == b.score_accumulation
    assert a.score_momentum == b.score_momentum


def test_penalty_ma60_deducts_points():
    config = {
        "scoring": {
            "mechanism": "tiered_dual_penalty",
            "penalty_rules": [
                {"id": "close_below_ma60", "enabled": True, "points": 10, "label": "低于MA60"},
            ],
        }
    }
    base = TieredDualMaxScorer(config).calculate(_sample_row(close=10.0, ma60=12.0))
    penalized = TieredDualPenaltyScorer(config).calculate(_sample_row(close=10.0, ma60=12.0))
    assert base is not None and penalized is not None
    assert penalized.score_penalty_deduction == 10.0
    assert penalized.score_total == max(0.0, base.score_total - 10.0)
    assert penalized.score_base_total == base.score_total


def test_validate_standard_rejects_penalty_rules():
    errs = validate_scoring_config(
        {"mechanism": "tiered_dual_max", "penalty_rules": [{"id": "close_below_ma60", "enabled": True, "points": 10}]}
    )
    assert errs


def test_validate_penalty_requires_enabled_rule():
    errs = validate_scoring_config({"mechanism": "tiered_dual_penalty", "penalty_rules": []})
    assert errs
