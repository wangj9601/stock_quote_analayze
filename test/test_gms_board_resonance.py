# -*- coding: utf-8 -*-
"""GMS 主行业板共振 / board_weak 软减分。"""

from backend_core.strategies.gms.board_resonance import (
    _is_board_weak,
    apply_board_weak_penalty_to_item,
    empty_board_resonance,
    resolve_board_resonance_config,
)
from backend_core.strategies.gms.scoring.penalties import PENALTY_RULE_TYPES, PenaltyEngine


def test_board_weak_rule_registered():
    assert "board_weak" in PENALTY_RULE_TYPES
    assert PENALTY_RULE_TYPES["board_weak"]["default_points"] == 10


def test_is_board_weak_by_slope_and_fallback():
    weak, reason = _is_board_weak(
        sector_slope_v=-0.01,
        board_change_percent=1.0,
        slope_threshold=0.0,
        use_realtime_fallback=True,
    )
    assert weak is True
    assert reason == "sector_slope_negative"

    ok, reason2 = _is_board_weak(
        sector_slope_v=0.02,
        board_change_percent=-3.0,
        slope_threshold=0.0,
        use_realtime_fallback=True,
    )
    assert ok is False
    assert reason2 == "sector_slope_ok"

    weak_rt, reason3 = _is_board_weak(
        sector_slope_v=None,
        board_change_percent=-1.2,
        slope_threshold=0.0,
        use_realtime_fallback=True,
    )
    assert weak_rt is True
    assert reason3 == "realtime_change_negative"


def test_apply_board_weak_penalty_post_process():
    cfg = {
        "scoring": {
            "mechanism": "tiered_dual_penalty",
            "penalty_rules": [
                {"id": "board_weak", "enabled": True, "points": 10, "label": "主行业板走弱"},
            ],
        }
    }
    item = {
        "score_total": 80.0,
        "signal_strength": 0.8,
        "board_weak": True,
        "sector_slope": -0.05,
        "primary_board_code": "BK0001",
        "primary_board_name": "测试板",
        "board_weak_reason": "sector_slope_negative",
        "score_detail": {"score_total": 80.0, "penalties": []},
        "risk_tags": [],
    }
    apply_board_weak_penalty_to_item(item, config=cfg)
    assert item["score_total"] == 70.0
    assert abs(item["signal_strength"] - 0.7) < 1e-6
    assert "board_weak" in item["risk_tags"]
    pens = item["score_detail"]["penalties"]
    assert any(p.get("id") == "board_weak" for p in pens)
    assert item["score_detail"]["score_penalty_deduction"] == 10


def test_penalty_engine_board_weak_from_row_flag():
    cfg = {
        "scoring": {
            "penalty_rules": [
                {"id": "board_weak", "enabled": True, "points": 8, "label": "主行业板走弱"},
            ],
        }
    }
    eng = PenaltyEngine(cfg)
    total, details = eng.apply({"board_weak": True, "sector_slope": -0.1})
    assert total == 8
    assert details[0]["id"] == "board_weak"

    total2, _ = eng.apply({"board_weak": False, "sector_slope": 0.1})
    assert total2 == 0


def test_resolve_board_resonance_config_defaults():
    c = resolve_board_resonance_config({})
    assert c["enabled"] is True
    assert c["enable_board_fund_flow"] is False
    assert c["sector_slope_window"] == 60
    empty = empty_board_resonance()
    assert empty["board_main_net_inflow"] is None
    assert empty["enable_board_fund_flow"] is False
