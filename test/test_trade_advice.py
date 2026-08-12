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
        "nearest_cam_support": 9.52,
        "nearest_cam_resistance": 11.1,
    }
    adv = build_trade_advice(
        "urt",
        {"buy_signal": True, "nearest_support": 9.55, "close": 10.0},
        reference_levels=ref,
    )
    assert "参考" in adv["summary"]
    assert adv["reference_levels"] is ref


def test_urt_buy_pullback_when_extended_and_overheat_soft():
    """买点成立但现价远离支撑且过热软标 → 建议回踩承接区，不宜追高。"""
    adv = build_trade_advice(
        "urt",
        {
            "buy_signal": True,
            "close": 11.20,
            "ma20": 9.51,
            "nearest_support": 10.75,
            "nearest_resistance": 12.44,
            "structure_rr": 2.76,
            "risk_tags": [
                {"id": "recent_overheat", "level": "warn", "label": "近期涨幅偏大"},
                {"id": "ma20_overheat", "level": "warn", "label": "均线乖离偏大"},
            ],
        },
    )
    assert adv["action"] == "buy"
    assert adv["buy_zone"] is not None
    assert "pullback" in (adv["buy_zone"].get("basis") or "")
    assert adv["buy_zone"].get("low") == 9.51
    assert adv["buy_zone"].get("high") == 10.75
    assert adv["stop_zone"]["price"] == 10.75
    assert adv["take_profit"]["prices"][0] == 12.44
    assert "回踩" in adv["summary"]
    assert "RR" in adv["summary"] or "2.76" in adv["summary"]


def test_confluence_soft_aligns_stop_display():
    ref = {
        "ok": True,
        "confluence_zones": {
            "ok": True,
            "nearest_support_zone": {
                "center": 10.05,
                "low": 10.0,
                "high": 10.1,
                "sources": ["kde", "fib"],
                "strength": 3.4,
            },
            "nearest_resistance_zone": {
                "center": 12.02,
                "low": 11.9,
                "high": 12.1,
                "sources": ["kde", "camarilla"],
                "strength": 2.8,
            },
        },
    }
    adv = build_trade_advice(
        "gms",
        {
            "left_buy_signal": True,
            "buy_type": "左侧",
            "nearest_support": 10.0,
            "nearest_resistance": 12.0,
        },
        reference_levels=ref,
    )
    assert adv["stop_zone"]["basis"] == "kde+confluence"
    assert adv["stop_zone"]["price"] == 10.05
    assert adv["stop_zone"].get("kde_price") == 10.0
    assert adv["take_profit"]["basis"] == "kde+confluence"
    assert "共振" in adv["summary"]
