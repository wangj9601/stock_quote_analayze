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


def test_penalty_ma60_flat_halves_deduction():
    config = {
        "scoring": {
            "mechanism": "tiered_dual_penalty",
            "penalty_rules": [
                {"id": "close_below_ma60", "enabled": True, "points": 10, "half_when_ma60_flat": True},
            ],
        }
    }
    row = _sample_row(close=10.0, ma60=12.0)
    row["ma60_flat"] = True
    row["ma60_d_lag"] = 11.9
    penalized = TieredDualPenaltyScorer(config).calculate(row)
    assert penalized is not None
    assert penalized.score_penalty_deduction == 5.0
    assert penalized.penalty_details[0]["base_points"] == 10.0
    assert penalized.penalty_details[0]["ma60_flat"] is True


def test_penalty_ma60_not_flat_full_deduction():
    config = {
        "scoring": {
            "penalty_rules": [{"id": "close_below_ma60", "enabled": True, "points": 10}],
        }
    }
    row = _sample_row(close=10.0, ma60=12.0)
    row["ma60_flat"] = False
    total, details = PenaltyEngine(config).apply(row)
    assert total == 10.0
    assert details[0]["ma60_flat"] is False


def test_penalty_ma60_missing_lag_full_deduction():
    config = {
        "scoring": {
            "penalty_rules": [{"id": "close_below_ma60", "enabled": True, "points": 10}],
        }
    }
    row = _sample_row(close=10.0, ma60=12.0)
    total, details = PenaltyEngine(config).apply(row)
    assert total == 10.0
    assert details[0].get("ma60_flat") is False


def test_validate_penalty_ma60_flat_params():
    errs = validate_scoring_config(
        {
            "mechanism": "tiered_dual_penalty",
            "ma60_flat_lookback_days": 0,
            "ma60_flat_tol": 0.2,
            "penalty_rules": [{"id": "close_below_ma60", "enabled": True, "points": 10}],
        }
    )
    assert any("ma60_flat_lookback_days" in e for e in errs)
    assert any("ma60_flat_tol" in e for e in errs)


def test_validate_standard_rejects_penalty_rules():
    errs = validate_scoring_config(
        {"mechanism": "tiered_dual_max", "penalty_rules": [{"id": "close_below_ma60", "enabled": True, "points": 10}]}
    )
    assert errs


def test_validate_penalty_requires_enabled_rule():
    errs = validate_scoring_config({"mechanism": "tiered_dual_penalty", "penalty_rules": []})
    assert errs


def test_penalty_volume_shrink_after_breakout():
    config = {
        "scoring": {
            "penalty_rules": [
                {"id": "volume_shrink_after_breakout", "enabled": True, "points": 8},
            ],
        }
    }
    row = _sample_row()
    row["volume_ratio"] = 0.5
    row["ratio_d1"] = -0.02
    total, details = PenaltyEngine(config).apply(row)
    assert total == 8.0
    assert details[0]["id"] == "volume_shrink_after_breakout"


def test_penalty_momentum_fade():
    config = {
        "scoring": {
            "momentum_batch_threshold": 80,
            "penalty_rules": [{"id": "momentum_fade", "enabled": True, "points": 6}],
        }
    }
    row = _sample_row()
    row["score_momentum"] = 50
    row["fz_ratio"] = 0.3
    total, _ = PenaltyEngine(config).apply(row)
    assert total == 6.0


def test_penalty_excessive_deviation():
    config = {
        "scoring": {
            "overbought_ratio": 0.12,
            "penalty_rules": [{"id": "excessive_deviation", "enabled": True, "points": 12}],
        },
        "overbought_ratio": 0.12,
    }
    row = _sample_row()
    row["ratio_d20"] = 0.2
    total, details = PenaltyEngine(config).apply(row)
    assert total == 12.0
    assert details[0]["id"] == "excessive_deviation"
