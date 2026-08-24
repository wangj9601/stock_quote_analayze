# -*- coding: utf-8 -*-
"""综合交易策略合成：fixture 覆盖冲突、无命中、GMS 左侧买点。"""

from backend_core.analysis.integrated_trade_plan import build_integrated_trade_plan


def _base_pack(*, urt_hit=False, gms_hit=False, urt_row=None, gms_row=None):
    summaries = {
        "urt": {"hit": urt_hit, "name": "URT", "label": "买点" if urt_hit else "未命中", "reason": "test"},
        "gms": {"hit": gms_hit, "name": "GMS", "label": "左侧" if gms_hit else "未命中", "reason": "test"},
        "sbbr": {"hit": False, "name": "SBBR", "label": "未命中", "reason": "test"},
        "rpe": {"hit": False, "name": "RPE", "label": "未命中", "reason": "test"},
    }
    rows = {}
    if urt_row is not None:
        rows["urt"] = urt_row
    if gms_row is not None:
        rows["gms"] = gms_row
    return {"summaries": summaries, "rows": rows}


def test_urt_hit_pattern_bull_weekly_counter_trend_conflicts():
    ctx = {
        "meta": {"code": "600519", "trade_date": "2026-08-20"},
        "strategy_pack": _base_pack(
            urt_hit=True,
            urt_row={
                "buy_signal": True,
                "close": 10.0,
                "nearest_support": 9.5,
                "nearest_resistance": 11.0,
                "score_total": 70,
            },
        ),
        "levels": {
            "data": {
                "nearest_support": 9.5,
                "nearest_resistance": 11.0,
                "last_close": 10.0,
            }
        },
        "pattern": {"tactical": {"short_bias": "看多"}},
        "swing": {
            "data": {
                "market_structure": {"trend": "uptrend", "trend_label": "上升趋势"},
                "weekly": {"trend": "downtrend", "trend_label": "下降趋势"},
                "counter_trend_note": "日线偏多但周线逆势，短线宜谨慎",
            }
        },
        "gann": None,
    }
    plan = build_integrated_trade_plan(ctx)
    assert plan["primary_strategy"] == "urt"
    assert plan["stance_short"] == "buy"
    conflicts = " ".join(plan.get("conflicts") or [])
    assert "逆势" in conflicts or "周线" in conflicts


def test_no_strategy_hit_watch_with_structure_levels():
    ctx = {
        "meta": {"code": "000001"},
        "strategy_pack": _base_pack(),
        "levels": {
            "data": {
                "nearest_support": 8.0,
                "nearest_resistance": 9.0,
                "current_price": 8.5,
            }
        },
        "pattern": None,
        "swing": None,
        "gann": None,
    }
    plan = build_integrated_trade_plan(ctx)
    assert plan["primary_strategy"] == "none"
    assert plan["stance_short"] == "watch"
    assert plan["short_term"]["action"] == "watch"
    kl = plan.get("key_levels") or {}
    assert kl.get("close") == 8.5
    assert kl.get("support") == 8.0
    entry = plan["short_term"].get("entry_zone")
    assert entry is not None
    assert entry.get("basis") == "structure_watch"
    assert entry.get("low") is not None
    assert plan["medium_term"].get("watch_zone") is not None
    assert plan["short_term"].get("take_profit") is not None


def test_gms_left_buy_with_kde_support_short_buy_zone():
    ctx = {
        "meta": {"code": "600000"},
        "strategy_pack": _base_pack(
            gms_hit=True,
            gms_row={
                "left_buy_signal": True,
                "buy_type": "左侧",
                "nearest_support": 10.0,
                "nearest_resistance": 12.0,
                "close": 10.5,
                "score_total": 75,
            },
        ),
        "levels": {
            "data": {
                "nearest_support": 10.0,
                "nearest_resistance": 12.0,
                "last_close": 10.5,
            }
        },
        "pattern": None,
        "swing": None,
        "gann": None,
    }
    plan = build_integrated_trade_plan(ctx)
    assert plan["primary_strategy"] == "gms"
    assert plan["stance_short"] == "buy"
    entry = plan["short_term"].get("entry_zone")
    assert entry is not None
    assert entry.get("low") is not None or entry.get("price") is not None
