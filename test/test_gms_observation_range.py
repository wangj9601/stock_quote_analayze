"""
GMS 观察周期振幅计算单元测试。
"""

from __future__ import annotations

from backend_core.strategies.gms.observation_range import (
    compute_range_amplitude_pct,
    resolve_amplitude_threshold_pct,
    resolve_observation_period_days,
)
from backend_core.strategies.gms.scoring.penalties import PenaltyEngine
from backend_core.strategies.gms.scoring.tiered_dual_penalty import TieredDualPenaltyScorer
from backend_core.strategies.gms.scoring.tiered_dual_max import TieredDualMaxScorer


def test_compute_range_amplitude_pct():
    assert compute_range_amplitude_pct(13.0, 10.0) == (13.0 - 10.0) / 13.0
    assert compute_range_amplitude_pct(10.0, 10.0) == 0.0
    assert compute_range_amplitude_pct(None, 10.0) is None


def test_resolve_observation_period_days():
    assert resolve_observation_period_days({"observation_period": 15}) == 15
    assert resolve_observation_period_days({}) == 20


def test_resolve_amplitude_threshold_from_rule():
    th = resolve_amplitude_threshold_pct(
        rule={"amplitude_threshold_pct": 0.25},
        config={"scoring": {"observation_range_amplitude_threshold": 0.40}},
    )
    assert th == 0.25


def test_penalty_observation_range_amplitude_triggers():
    config = {
        "scoring": {
            "penalty_rules": [
                {
                    "id": "observation_range_amplitude",
                    "enabled": True,
                    "points": 10,
                    "amplitude_threshold_pct": 0.30,
                },
            ],
        }
    }
    row = {
        "code": "600519",
        "date": "2026-05-10",
        "observation_range_amplitude_pct": 0.35,
        "observation_period_high": 13.5,
        "observation_period_low": 10.0,
    }
    total, details = PenaltyEngine(config).apply(row)
    assert total == 10.0
    assert details[0]["id"] == "observation_range_amplitude"
    assert details[0]["amplitude_threshold_pct"] == 0.30


def test_penalty_observation_range_amplitude_not_trigger_at_threshold():
    config = {
        "scoring": {
            "penalty_rules": [
                {"id": "observation_range_amplitude", "enabled": True, "points": 10, "amplitude_threshold_pct": 0.30},
            ],
        }
    }
    row = {"observation_range_amplitude_pct": 0.30}
    total, details = PenaltyEngine(config).apply(row)
    assert total == 0.0
    assert details == []


def test_penalty_observation_range_amplitude_scorer_integration():
    config = {
        "scoring": {
            "penalty_rules": [
                {"id": "observation_range_amplitude", "enabled": True, "points": 10, "amplitude_threshold_pct": 0.30},
            ],
        }
    }
    row = {
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
        "d20": 10.0,
        "observation_range_amplitude_pct": 0.45,
    }
    base = TieredDualMaxScorer(config).calculate(row)
    penalized = TieredDualPenaltyScorer(config).calculate(row)
    assert base is not None and penalized is not None
    assert penalized.score_penalty_deduction == 10.0
    assert penalized.score_total == max(0.0, base.score_total - 10.0)


def test_validate_observation_amplitude_threshold():
    from backend_core.strategies.gms.scoring import validate_scoring_config

    errs = validate_scoring_config(
        {
            "mechanism": "tiered_dual_penalty",
            "penalty_rules": [
                {
                    "id": "observation_range_amplitude",
                    "enabled": True,
                    "points": 10,
                    "amplitude_threshold_pct": 3.0,
                },
            ],
        }
    )
    assert any("amplitude_threshold_pct" in e for e in errs)
