# -*- coding: utf-8 -*-
"""URT 结构盈亏比风险提示（软标签）。"""

from backend_core.strategies.urt.config import URTConfigManager
from backend_core.strategies.urt.risk_tags import (
    build_structure_rr_risk_tags,
    enrich_structure_with_rr,
)
from backend_core.strategies.urt.signal_detector import evaluate_buy_signal


def test_build_tags_rr_low_warn():
    cfg = {
        "structure_rr_warn_enabled": True,
        "structure_rr_min_rr": 1.5,
        "structure_hang_min_upside_pct": 0.20,  # 抬高悬空阈值，避免本例同时打悬空标签
    }
    st = {"nearest_support": 14.0, "nearest_resistance": 16.47}
    enriched = enrich_structure_with_rr(st, price=15.84, cfg=cfg)
    assert enriched["structure"]["rr"] is not None
    assert enriched["structure"]["rr"] < 1.5
    assert "rr_downside_floored" in enriched["structure"]
    tags = enriched["risk_tags"]
    assert len(tags) == 1
    assert tags[0]["id"] == "poor_structure_rr"
    assert tags[0]["level"] == "warn"


def test_enrich_near_support_applies_downside_floor():
    cfg = {
        "structure_rr_warn_enabled": True,
        "structure_rr_min_rr": 1.5,
        "structure_rr_min_downside_pct": 0.015,
    }
    enriched = enrich_structure_with_rr(
        {"nearest_support": 7.87, "nearest_resistance": 10.07},
        price=7.91,
        cfg=cfg,
    )
    st = enriched["structure"]
    assert st["rr_downside_floored"] is True
    assert abs(st["rr"] - 18.2048) < 0.01
    # RR 经下限后仍远高于 1.5 → 无偏低标签
    assert enriched["risk_tags"] == []

    cfg_hi = dict(cfg)
    cfg_hi["structure_rr_min_rr"] = 20
    tags = build_structure_rr_risk_tags(
        {"nearest_support": 7.87, "nearest_resistance": 10.07},
        cfg_hi,
        price=7.91,
    )
    assert len(tags) == 1
    assert "已用分母下限" in tags[0]["reason"]


def test_default_config_has_min_downside_pct():
    cfg = URTConfigManager().get_default_config()
    assert abs(float(cfg.get("structure_rr_min_downside_pct")) - 0.015) < 1e-9
    assert abs(float(cfg.get("structure_rr_min_rr")) - 2.0) < 1e-9
    assert cfg.get("structure_rr_hard_gate_enabled") is True
    assert abs(float(cfg.get("structure_rr_atr_k")) - 0.75) < 1e-9
    assert cfg.get("structure_rr_use_second_level") is True


def test_build_tags_below_support_danger():
    cfg = {"structure_rr_warn_enabled": True, "structure_rr_min_rr": 2.0}
    tags = build_structure_rr_risk_tags(
        {"nearest_support": 16.0, "nearest_resistance": 18.0},
        cfg,
        price=15.0,
    )
    assert len(tags) == 1
    assert tags[0]["level"] == "danger"
    assert "破位" in tags[0]["label"]


def test_build_tags_no_resistance_silent():
    cfg = {"structure_rr_warn_enabled": True, "structure_rr_min_rr": 1.5}
    tags = build_structure_rr_risk_tags(
        {"nearest_support": 14.0, "nearest_resistance": None},
        cfg,
        price=15.0,
    )
    assert tags == []


def test_build_tags_disabled():
    cfg = {"structure_rr_warn_enabled": False, "structure_rr_min_rr": 1.5}
    tags = build_structure_rr_risk_tags(
        {"nearest_support": 14.0, "nearest_resistance": 16.47},
        cfg,
        price=15.84,
    )
    assert tags == []


def _bars_with_clusters(n=80):
    import random

    random.seed(11)
    bars = []
    for i in range(n):
        cluster = [13.0, 15.0, 17.0][i % 3]
        close = round(cluster + random.uniform(-0.08, 0.08), 2)
        bars.append(
            {
                "date": f"2026-{(8 if i < 30 else 7):02d}-{max(1, 28 - (i % 28)):02d}",
                "open": close - 0.2,
                "close": close,
                "volume": 1_000_000 + (i % 3) * 400_000,
                "turnover_rate": 2.0,
            }
        )
    bars[0]["close"] = 15.2
    bars[0]["open"] = 14.8
    bars[0]["volume"] = 4_000_000
    for i in range(1, 5):
        bars[i]["close"] = 15.0 + i * 0.05
        bars[i]["open"] = bars[i]["close"] - 0.15
        bars[i]["volume"] = 3_000_000
    return bars


def test_evaluate_buy_signal_attaches_rr_and_risk_tags_without_changing_score_logic():
    cfg = URTConfigManager().get_default_config()
    cfg["structure_rr_warn_enabled"] = True
    cfg["structure_rr_min_rr"] = 1.5
    cfg["structure_rr_hard_gate_enabled"] = False
    cfg["use_yang_medium"] = False
    cfg["require_ma_bull"] = False
    cfg["use_turnover"] = False
    bars = _bars_with_clusters(90)
    detail = evaluate_buy_signal(bars, cfg, require_pass=False)
    assert detail is not None
    score = detail.get("score")
    buy = detail.get("buy_signal")
    sd = detail.get("score_detail") or {}
    st = sd.get("structure") or {}
    assert "rr" in st
    assert "risk_tags" in sd
    assert detail.get("risk_tags") == sd.get("risk_tags")
    assert detail.get("structure_rr") == st.get("rr")
    # 软标签：得分与买点字段仍存在（不因标签被清空）
    assert score is not None
    assert buy is not None or buy is False


def test_query_trace_enrich_rr_from_old_structure(monkeypatch):
    from backend_core.strategies.urt import trace_store as ts

    class _Row:
        code = "000009"
        name = "中国宝安"
        date = "2026-08-04"
        config_id = 1
        buy_signal = True
        score = 80.0
        close = 15.84
        open = 14.8
        ma20 = 14.0
        above_ma20 = True
        yang_count_4 = 3
        yang_count_5 = 4
        yang_rule = "4d3"
        volume = 1e6
        avg_volume_20 = 5e5
        volume_multiple = 2.0
        volume_ratio = 1.2
        turnover_rate = 3.0
        score_detail = {
            "structure": {
                "method": "kde_volume_weighted",
                "support_levels": [14.0],
                "resistance_levels": [16.47],
                "nearest_support": 14.0,
                "nearest_resistance": 16.47,
                "kde_ok": True,
            }
        }

    class _Q:
        def filter(self, *a, **k):
            return self

        def order_by(self, *a, **k):
            return self

        def limit(self, *a, **k):
            return self

        def all(self):
            return [_Row()]

    class _DB:
        def query(self, *a, **k):
            return _Q()

    rows = ts.query_trace_by_code(_DB(), code="000009", config_id=1, limit=10)
    assert len(rows) == 1
    assert rows[0]["structure_rr"] is not None
    assert rows[0]["structure_rr"] < 1.5
    assert any(t.get("id") == "poor_structure_rr" for t in (rows[0].get("risk_tags") or []))


def test_pick_nth_level_second_support_and_resistance():
    from backend_core.strategies.gms.structure_levels import pick_nth_level

    px = 10.0
    supports = [9.8, 9.0, 8.2]
    resists = [10.15, 11.5, 13.0]
    assert pick_nth_level(supports, px, side="support", n=1) == 9.8
    assert pick_nth_level(supports, px, side="support", n=2) == 9.0
    assert pick_nth_level(resists, px, side="resistance", n=1) == 10.15
    assert pick_nth_level(resists, px, side="resistance", n=2) == 11.5
    assert pick_nth_level([9.8], px, side="support", n=2) == 9.8


def test_enrich_second_level_rr_hard_gate_uses_nearest():
    cfg = {
        "structure_rr_warn_enabled": True,
        "structure_rr_min_rr": 2.0,
        "structure_rr_min_upside_pct": 0.03,
        "structure_rr_hard_gate_enabled": True,
        "structure_rr_use_second_level": True,
        "structure_hang_min_upside_pct": 0.20,
        "kde_ok": True,
    }
    st = {
        "kde_ok": True,
        "nearest_support": 9.85,
        "nearest_resistance": 10.20,
        "support_levels": [9.85, 9.0],
        "resistance_levels": [10.20, 12.0],
    }
    enriched = enrich_structure_with_rr(st, price=10.0, cfg=cfg)
    out = enriched["structure"]
    assert out["rr_level_rank"] == 2
    assert abs(float(out["rr_support"]) - 9.0) < 1e-9
    assert abs(float(out["rr_resistance"]) - 12.0) < 1e-9
    # 结构 RR：上行 2 / 下行 1 = 2
    assert abs(float(out["rr"]) - 2.0) < 0.05
    gate = enriched["structure_hard_gate"]
    assert gate["blocked"] is True
    assert "上行空间不足" in (gate.get("reasons") or [])


def test_compute_structure_rr_atr_floor():
    from backend_core.strategies.gms.structure_levels import compute_structure_rr

    # 价 10、支撑 9.8 → raw=0.2；价×1.5%=0.15；k×ATR=0.75*1.0=0.75 → 分母 0.75
    info = compute_structure_rr(
        10.0, 9.8, 13.0, min_downside_pct=0.015, atr=1.0, atr_k=0.75
    )
    assert info["downside_floored"] is True
    assert info["floor_source"] == "atr"
    assert abs(info["downside"] - 0.75) < 1e-6
    assert abs(info["rr"] - (3.0 / 0.75)) < 1e-6
    assert abs(info["upside_pct"] - 0.3) < 1e-9
    assert abs(info["downside_pct"] - 0.02) < 1e-9
