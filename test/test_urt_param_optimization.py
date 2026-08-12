# -*- coding: utf-8 -*-
"""URT 参数优化：混合结构硬闸、悬空标签、空头趋势。"""

from backend_core.strategies.urt.config import URTConfigManager
from backend_core.strategies.urt.risk_tags import (
    build_trend_risk_tags,
    enrich_structure_with_rr,
    evaluate_structure_hard_gate,
    is_structure_hanging,
)


def test_default_config_optimization_flags():
    cfg = URTConfigManager().load_file_config()
    assert cfg["volume_multiple"] == 3.0
    assert cfg["volume_score_full_multiple"] == 4.0
    assert cfg["use_yang_medium"] is True
    assert cfg["require_ma_bull"] is True
    assert cfg["use_turnover"] is True
    assert cfg["min_turnover"] == 3.0
    assert cfg["structure_rr_min_rr"] == 2.0
    assert cfg["structure_rr_hard_gate_enabled"] is True
    assert abs(float(cfg["structure_hang_min_upside_pct"]) - 0.08) < 1e-9


def test_hanging_detection():
    hanging, dist = is_structure_hanging(100.0, 90.0, {"structure_hang_min_upside_pct": 0.08})
    assert hanging is True
    assert abs(dist - 0.1) < 1e-9
    hanging2, _ = is_structure_hanging(100.0, 95.0, {"structure_hang_min_upside_pct": 0.08})
    assert hanging2 is False


def test_structure_hard_gate_blocks_hang_and_at_resistance():
    cfg = {
        "structure_rr_hard_gate_enabled": True,
        "structure_hang_min_upside_pct": 0.08,
        "structure_rr_min_rr": 2.0,
    }
    # 悬空
    st = {"kde_ok": True, "nearest_support": 90.0, "nearest_resistance": 120.0, "rr_reason": "ok"}
    gate = evaluate_structure_hard_gate(st, cfg, price=100.0, rr_info={"reason": "ok", "rr": 3.0})
    assert gate["blocked"] is True
    assert "悬空离支撑" in gate["reasons"]

    # 贴阻力
    gate2 = evaluate_structure_hard_gate(
        {"kde_ok": True, "nearest_support": 98.0, "nearest_resistance": 100.0},
        cfg,
        price=100.0,
        rr_info={"reason": "at_resistance", "rr": 0},
    )
    assert gate2["blocked"] is True
    assert "贴/超阻力" in gate2["reasons"]

    # 仅 RR 偏低：不硬闸
    gate3 = evaluate_structure_hard_gate(
        {"kde_ok": True, "nearest_support": 99.0, "nearest_resistance": 101.0},
        cfg,
        price=100.0,
        rr_info={"reason": "ok", "rr": 1.0, "should_penalize": None},
    )
    assert gate3["blocked"] is False


def test_rr_low_soft_tag_only_and_hanging_tag():
    cfg = {
        "structure_rr_warn_enabled": True,
        "structure_rr_min_rr": 2.0,
        "structure_hang_min_upside_pct": 0.08,
        "structure_rr_hard_gate_enabled": True,
    }
    # 距离约 1% → 不悬空；RR=(16-15)/(15-14)=1 < 2 → 软标签
    enriched = enrich_structure_with_rr(
        {"nearest_support": 14.0, "nearest_resistance": 16.0, "kde_ok": True},
        price=15.0,
        cfg=cfg,
    )
    assert enriched["structure"]["rr"] is not None
    assert enriched["structure"]["rr"] < 2.0
    assert enriched["structure_hard_gate"]["blocked"] is False
    assert any(t["label"] == "结构盈亏比偏低" for t in enriched["risk_tags"])

    # 悬空标签
    enriched2 = enrich_structure_with_rr(
        {"nearest_support": 90.0, "nearest_resistance": 130.0, "kde_ok": True},
        price=100.0,
        cfg=cfg,
    )
    assert any(t["id"] == "structure_hanging" for t in enriched2["risk_tags"])
    assert enriched2["structure_hard_gate"]["blocked"] is True


def test_bearish_trend_risk_tags():
    tags = build_trend_risk_tags({"ma_bear_ok": True, "ma_bull_periods": [5, 10, 20]})
    assert len(tags) == 1
    assert tags[0]["id"] == "bearish_ma_trend"
    tags2 = build_trend_risk_tags({"ma_bear_ok": False, "above_ma20": False})
    assert any(t["id"] == "below_ma20" for t in tags2)


def test_overheat_soft_and_hard():
    from backend_core.strategies.urt.risk_tags import (
        build_overheat_risk_tags,
        evaluate_overheat_hard_gate,
    )

    cfg = {
        "overheat_warn_enabled": True,
        "overheat_hard_gate_enabled": True,
        "overheat_lookback_days": 10,
        "overheat_soft_pct": 0.15,
        "overheat_hard_pct": 0.25,
        "overheat_bias_soft_pct": 0.15,
        "overheat_bias_hard_pct": 0.20,
    }
    soft_ind = {"ret_from_low_n": 0.18, "ma20_bias": 0.10, "overheat_lookback_days": 10}
    tags = build_overheat_risk_tags(soft_ind, cfg)
    assert any(t["label"] == "近期涨幅偏大" and t["level"] == "warn" for t in tags)
    assert evaluate_overheat_hard_gate(soft_ind, cfg)["blocked"] is False

    hard_ind = {"ret_from_low_n": 0.30, "ma20_bias": 0.05, "overheat_lookback_days": 10}
    tags_h = build_overheat_risk_tags(hard_ind, cfg)
    assert any(t["label"] == "近期涨幅过大" and t["level"] == "danger" for t in tags_h)
    gate = evaluate_overheat_hard_gate(hard_ind, cfg)
    assert gate["blocked"] is True
    assert "近期涨幅过大" in gate["reasons"]

    bias_hard = {"ret_from_low_n": 0.05, "ma20_bias": 0.22, "overheat_lookback_days": 10}
    assert evaluate_overheat_hard_gate(bias_hard, cfg)["blocked"] is True


def test_ret_from_low_in_indicators():
    from backend_core.strategies.urt.config import URTConfigManager
    from backend_core.strategies.urt.indicators import build_indicators

    cfg = URTConfigManager().get_default_config()
    cfg["use_yang_medium"] = False
    cfg["require_ma_bull"] = False
    cfg["use_turnover"] = False
    # DESC: day0 high, previous days lower
    bars = []
    for i in range(40):
        close = 10.0 + (40 - i) * 0.05  # older higher? wait DESC i=0 newest
        # newest = 13, older = lower → rise from low
        close = 10.0 + max(0, 10 - i) * 0.3
        bars.append(
            {
                "date": f"2026-07-{30 - (i % 28):02d}",
                "open": close - 0.1,
                "close": close,
                "volume": 3000.0 if i == 0 else 1000.0,
                "turnover_rate": 5.0,
            }
        )
    # Force: newest 13, min in 10 days = 10 → ret=0.3
    for i in range(10):
        bars[i]["close"] = 10.0 + (9 - i) * (3.0 / 9.0)  # 13 .. 10
        bars[i]["open"] = bars[i]["close"] - 0.1
    bars[0]["close"] = 13.0
    bars[0]["open"] = 12.5
    bars[9]["close"] = 10.0
    ind = build_indicators(bars, cfg)
    assert ind is not None
    assert ind["ret_from_low_n"] is not None
    assert abs(ind["ret_from_low_n"] - 0.3) < 1e-6
    assert ind["ma20_bias"] is not None


def test_compute_structure_rr_thin_upside():
    """距阻力上行空间过窄：宁夏建材类 12.58/12.57/12.93。"""
    from backend_core.strategies.gms.structure_levels import compute_structure_rr

    info = compute_structure_rr(
        12.58,
        12.57,
        12.93,
        min_downside_pct=0.015,
        min_upside_pct=0.03,
    )
    assert info["reason"] == "thin_upside"
    assert info["should_penalize"] is True
    assert info["upside"] is not None and info["upside"] < 0.4
    assert info["upside_pct"] is not None and info["upside_pct"] < 0.03

    ok = compute_structure_rr(
        12.58,
        12.0,
        14.0,
        min_downside_pct=0.015,
        min_upside_pct=0.03,
    )
    assert ok["reason"] == "ok"
    assert ok["should_penalize"] is None


def test_urt_hard_gate_blocks_thin_upside():
    cfg = {
        "structure_rr_warn_enabled": True,
        "structure_rr_min_rr": 2.0,
        "structure_rr_min_downside_pct": 0.015,
        "structure_rr_min_upside_pct": 0.03,
        "structure_rr_hard_gate_enabled": True,
        "structure_hang_min_upside_pct": 0.08,
    }
    enriched = enrich_structure_with_rr(
        {
            "kde_ok": True,
            "nearest_support": 12.57,
            "nearest_resistance": 12.93,
        },
        price=12.58,
        cfg=cfg,
    )
    assert enriched["structure"]["rr_reason"] == "thin_upside"
    assert enriched["structure_hard_gate"]["blocked"] is True
    assert "上行空间不足" in enriched["structure_hard_gate"]["reasons"]
    assert any(t.get("label") == "上行空间不足" for t in enriched["risk_tags"])
