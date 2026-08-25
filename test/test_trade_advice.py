# -*- coding: utf-8 -*-
from backend_core.analysis.trade_advice import build_trade_advice


def test_sbbr_bottom_watch_uses_position_advice_message_not_dict():
    pa = {
        "probe_pct": 50.0,
        "add_pct": 30.0,
        "reserve_cash_pct": 20.0,
        "max_open_positions": 3,
        "max_allocated_pct": 80.0,
        "can_open": True,
        "next_action": "probe",
        "next_pct": 50.0,
        "message": "确认弱转强后试探配置 50%",
        "allocated_pct": 0.0,
        "stage": None,
    }
    adv = build_trade_advice(
        "sbbr",
        {
            "bottom_matched": True,
            "entry_signal": False,
            "close": 6.43,
            "position_advice": pa,
        },
    )
    assert adv["action"] == "watch"
    assert "已筑底未入场" in adv["summary"]
    assert "确认弱转强后试探配置 50%" in adv["summary"]
    assert "probe_pct" not in adv["summary"]
    assert "{" not in adv["summary"]


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
    assert adv["stop_zone"]["price"] == 9.8
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
    """买点成立但现价远离支撑且过热软标 → 建议回踩承接区，不宜追高。

    MA20 远低于结构支撑时：短线可执行区钉近端支撑，MA20 降为中线更深回撤关注；
    止损须严格低于买入下沿（与个股分析失效位钳制同口径）。
    """
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
    stop_px = float(adv["stop_zone"]["price"])
    assert abs(stop_px - 10.75 * 0.98) < 1e-6
    assert adv["stop_zone"].get("buffer_pct") == 0.02
    assert "缓冲" in (adv["stop_zone"].get("label") or "")
    lo = float(adv["buy_zone"]["low"])
    hi = float(adv["buy_zone"]["high"])
    assert lo > stop_px
    assert hi == 10.75
    assert adv.get("deeper_watch") is not None
    assert abs(float(adv["deeper_watch"]["price"]) - 9.51) < 1e-6
    assert adv["take_profit"]["prices"][0] == 12.44
    assert "回踩" in adv["summary"] or "短线" in adv["summary"]
    assert adv.get("structure_rr") == 2.76
    assert adv["key_levels"]["support"] == 10.75
    assert adv["key_levels"]["close"] == 11.2
    assert adv["key_levels"]["resistance"] == 12.44
    assert adv.get("horizon", {}).get("short_term") is not None


def test_urt_entry_stop_no_deadlock_like_screenshot():
    """复现明细矛盾：承接 15.24–16.63 vs 止损 16.30 → 钳制后下沿高于止损。"""
    adv = build_trade_advice(
        "urt",
        {
            "buy_signal": True,
            "close": 17.35,
            "ma20": 15.24,
            "nearest_support": 16.63,
            "nearest_resistance": 17.97,
            "structure_rr": 0.86,
            "risk_tags": [
                {"id": "recent_overheat", "level": "warn", "label": "近期涨幅偏大"},
            ],
        },
    )
    stop_px = float(adv["stop_zone"]["price"])
    lo = float(adv["buy_zone"]["low"])
    hi = float(adv["buy_zone"]["high"])
    assert abs(stop_px - 16.63 * 0.98) < 1e-6
    assert lo > stop_px
    assert hi == 16.63
    assert abs(float(adv["deeper_watch"]["price"]) - 15.24) < 1e-6


def test_urt_soft_merge_pattern_tactical():
    adv = build_trade_advice(
        "urt",
        {
            "buy_signal": True,
            "close": 10.5,
            "ma20": 10.2,
            "nearest_support": 10.0,
            "nearest_resistance": 11.5,
            "structure_rr": 3.0,
            "tactical": {
                "bias": "震荡",
                "grade": "base",
                "buy_hints": [
                    {
                        "entry_zone": {
                            "low": 9.95,
                            "high": 10.05,
                            "center": 10.0,
                            "anchor": "near_support_pref",
                        },
                        "invalidation": 9.85,
                    }
                ],
                "shortTerm": "短线关注近端支撑回踩。",
                "mediumTerm": "中线宜按箱体观察。",
            },
        },
    )
    assert "形态短线" in adv["summary"] or "个股短线" in adv["summary"]
    assert "个股中线" in adv["summary"] or "中线" in adv["summary"]


def test_urt_entry_band_widens_when_ma20_near_support():
    """MA20 贴近支撑时，承接区上沿至少抬到约支撑×1.03，避免不可执行窄带。"""
    adv = build_trade_advice(
        "urt",
        {
            "buy_signal": True,
            "close": 8.50,
            "ma20": 7.74,
            "nearest_support": 7.71,
            "nearest_resistance": 9.20,
            "structure_rr": 5.52,
            "risk_tags": [
                {"id": "recent_overheat", "level": "warn", "label": "近期涨幅偏大"},
            ],
        },
    )
    lo = float(adv["buy_zone"]["low"])
    hi = float(adv["buy_zone"]["high"])
    assert lo == 7.71
    assert hi >= 7.71 * 1.03 - 1e-6
    assert hi <= 8.50 + 1e-9
    assert (hi - lo) / lo >= 0.025


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
    assert adv["stop_zone"]["price"] == 9.8
    assert float(adv["stop_zone"]["price"]) < float(
        adv["buy_zone"].get("low") or adv["buy_zone"].get("price")
    )
    assert adv["take_profit"]["basis"] == "structure_resistance"
    assert float(adv["take_profit"]["prices"][0]) == 12.0
    assert "结构" in adv["summary"]


def test_gms_left_buy_stop_below_entry_with_confluence_band():
    """GMS 左侧 + 距第一支撑过近：入场参考第二档，止损/止盈对齐 structure_exit。"""
    ref = {
        "ok": True,
        "confluence_zones": {
            "ok": True,
            "nearest_support_zone": {
                "center": 16.12,
                "low": 15.86,
                "high": 16.32,
                "sources": ["kde", "fib"],
                "strength": 3.0,
            },
        },
        "support_levels": [16.12, 15.50],
        "nearest_support": 16.12,
        "nearest_resistance": 18.30,
    }
    adv = build_trade_advice(
        "gms",
        {
            "left_buy_signal": True,
            "buy_type": "左侧",
            "nearest_support": 16.12,
            "nearest_resistance": 18.30,
            "close": 16.48,
            "support_levels": [16.12, 15.50],
        },
        reference_levels=ref,
    )
    entry_lo = float(adv["buy_zone"]["low"])
    stop_px = float(adv["stop_zone"]["price"])
    assert entry_lo == 15.5
    assert stop_px < entry_lo
    assert stop_px == round(15.5 * 0.98, 4)
    assert float(adv["take_profit"]["prices"][0]) == 18.30
    assert "第二档支撑" in adv["summary"]


def test_urt_buy_uses_second_support_when_near_first():
    adv = build_trade_advice(
        "urt",
        {
            "buy_signal": True,
            "close": 16.48,
            "ma20": 15.8,
            "nearest_support": 16.12,
            "nearest_resistance": 18.30,
            "support_levels": [16.12, 15.20],
        },
    )
    assert "第二档支撑" in adv["summary"]
    assert float(adv["buy_zone"]["low"]) <= 15.2 + 1e-6
    assert float(adv["stop_zone"]["price"]) < float(adv["buy_zone"]["low"])
    assert float(adv["take_profit"]["prices"][0]) == 18.30
