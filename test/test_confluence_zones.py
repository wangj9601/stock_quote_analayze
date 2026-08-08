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
