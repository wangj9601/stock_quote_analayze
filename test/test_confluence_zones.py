# -*- coding: utf-8 -*-
from backend_core.analysis.confluence_zones import (
    build_confluence_zones,
    collect_candidate_points,
    compute_confluence_from_reference,
)


def test_collect_and_cluster_zones():
    pts = collect_candidate_points(
        kde_support=10.0,
        kde_resistance=12.0,
        kde_supports=[9.95, 9.9],
        fibonacci={
            "retracements": [
                {"ratio": 0.618, "price": 10.05},
                {"ratio": 0.5, "price": 10.5},
            ]
        },
        camarilla={"S1": 9.98, "R1": 12.05, "R2": 12.4},
        pivot={"S1": 10.02, "R1": 11.9, "P": 11.0},
        atr_pivot={"S1": 9.9, "R1": 12.1, "atr": 0.4},
        volume_profile={
            "ok": True,
            "poc": 11.0,
            "val": 10.1,
            "vah": 11.8,
            "nearest_support": 10.08,
            "nearest_resistance": 11.85,
        },
    )
    assert len(pts) >= 6
    zones = build_confluence_zones(pts, last_close=11.0, atr=0.4)
    assert zones["ok"] is True
    assert zones["nearest_support_zone"] is not None
    assert zones["nearest_resistance_zone"] is not None
    # 支撑带中心应贴近 10 附近
    assert abs(zones["nearest_support_zone"]["center"] - 10.0) < 0.3


def test_compute_from_reference():
    ref = {
        "ok": True,
        "last_close": 11.0,
        "atr": 0.5,
        "fibonacci": {
            "retracements": [{"ratio": 0.618, "price": 10.0}],
            "nearest_extension": {"ratio": 1.272, "price": 12.2},
        },
        "pivot": {"P": 11.0, "S1": 10.05, "R1": 12.0, "S2": 9.5, "R2": 12.5},
        "camarilla": {
            "S1": 10.02,
            "S2": 9.8,
            "S3": 9.5,
            "R1": 11.95,
            "R2": 12.2,
            "R3": 12.5,
        },
        "atr_pivot": {"P": 11.0, "S1": 10.5, "R1": 11.5, "S2": 10.0, "R2": 12.0, "atr": 0.5},
        "volume_profile": {
            "ok": True,
            "poc": 11.0,
            "val": 10.1,
            "vah": 11.9,
            "nearest_support": 10.1,
            "nearest_resistance": 11.9,
        },
    }
    out = compute_confluence_from_reference(
        ref,
        kde_support=10.0,
        kde_resistance=12.0,
        last_close=11.0,
    )
    assert out["ok"] is True
    assert len(out["supports"]) >= 1 or len(out["resistances"]) >= 1


def test_support_zone_high_clipped_to_last_close():
    """支撑带中心在现价下、原 high 越过现价时，展示 high 应 ≤ 现价。"""
    from backend_core.analysis.confluence_zones import _clip_zone_to_price_side

    z = {
        "center": 138.54,
        "low": 133.10,
        "high": 144.04,
        "strength": 38.2,
        "sources": ["pivot", "fib"],
        "labels": ["S1", "0.618"],
        "n_points": 4,
    }
    px = 140.57
    out = _clip_zone_to_price_side(z, px=px, side="support")
    assert out is not None
    assert out["high"] <= px + 1e-9
    assert out["low"] == 133.10
    assert out.get("clipped_to_price") is True
    assert out["center"] <= out["high"]

    zones = build_confluence_zones(
        [
            {"price": 133.1, "weight": 1.0, "source": "a", "label": "a"},
            {"price": 138.5, "weight": 1.2, "source": "b", "label": "b"},
            {"price": 144.0, "weight": 1.0, "source": "c", "label": "c"},
            {"price": 150.0, "weight": 1.0, "source": "d", "label": "d"},
            {"price": 151.0, "weight": 1.0, "source": "e", "label": "e"},
        ],
        last_close=140.57,
        atr=2.0,
    )
    assert zones["ok"] is True
    for s in zones["supports"]:
        assert s["high"] <= 140.57 + 1e-9
    for r in zones["resistances"]:
        assert r["low"] >= 140.57 - 1e-9
