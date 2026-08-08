# -*- coding: utf-8 -*-
from backend_core.analysis.trade_advice import build_trade_advice


def test_gms_left_buy_advice():
    adv = build_trade_advice(
        "gms",
        {
            "left_buy_signal": True,
            "buy_type": "左侧",
            "nearest_support": 10.0,
            "nearest_resistance": 12.0,
        },
    )
    assert adv["action"] == "buy"
    assert adv["stop_zone"]["price"] == 10.0
    assert adv["kde_support"] == 10.0
    assert adv["kde_resistance"] == 12.0
    assert "左侧" in adv["summary"] or "吸筹" in adv["summary"]


def test_rpe_trend_veto_avoid():
    adv = build_trade_advice(
        "rpe",
        {"trend_veto": True, "signal_type": "catch_up", "entry_signal": True},
    )
    assert adv["action"] == "avoid"


def test_reference_levels_appended():
    ref = {
        "ok": True,
        "nearest_fib_support": 9.5,
        "nearest_fib_resistance": 11.2,
        "nearest_pivot_support": 9.6,
        "nearest_pivot_resistance": 11.0,
    }
    adv = build_trade_advice(
        "urt",
        {"buy_signal": True, "nearest_support": 9.55, "close": 10.0},
        reference_levels=ref,
    )
    assert "参考" in adv["summary"]
    assert adv["reference_levels"] is ref
