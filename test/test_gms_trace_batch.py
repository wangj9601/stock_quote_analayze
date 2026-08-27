# -*- coding: utf-8 -*-
"""GMS trace 批量写入辅助函数单元测试（不连库）。"""

from backend_core.strategies.gms.frontend_interface import _build_trace_values


def test_build_trace_values_minimal():
    result = {
        "code": "600000",
        "market_type": "CN",
        "score_total": 72.5,
        "score_accumulation": 30,
        "score_momentum": 42.5,
        "signal_strength": 0.725,
        "buy_type": "左侧",
        "left_buy_signal": True,
        "right_buy_signal": False,
        "sell_signal": False,
        "score_detail": {"score_total": 72.5},
        "risk_tags": ["trend_ok"],
    }
    v = _build_trace_values(result, "2026-07-24", 1)
    assert v is not None
    assert v["code"] == "600000"
    assert v["date"] == "2026-07-24"
    assert v["config_id"] == 1
    assert v["score_total"] == 72.5
    assert v["left_buy_signal"] is True


def test_build_trace_values_empty_code():
    assert _build_trace_values({"score_total": 1}, "2026-07-24", 1) is None
