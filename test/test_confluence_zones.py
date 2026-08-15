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


def test_multi_window_kde_sources_in_candidates():
    pts = collect_candidate_points(
        kde_support=10.0,
        kde_resistance=12.0,
        kde_multi_windows={
            "ok": True,
            "windows": {
                "60": {
                    "ok": True,
                    "weight": 0.55,
                    "support_levels": [9.9],
                    "resistance_levels": [12.1],
                },
                "120": {
                    "ok": True,
                    "weight": 0.65,
                    "support_levels": [9.85],
                    "resistance_levels": [12.2],
                },
                "250": {
                    "ok": True,
                    "weight": 0.75,
                    "support_levels": [9.7],
                    "resistance_levels": [12.4],
                },
            },
        },
    )
    sources = {p["source"] for p in pts}
    assert sources >= {"kde", "kde_60", "kde_120", "kde_250"}


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


def test_near_dense_support_becomes_nearest_despite_far_strong_zones():
    """远端高强度支撑占满 Top3 时，近端多源低强度簇仍应成为 nearest_support。"""
    px = 100.0
    # 三个远端高强度簇（约 80 / 70 / 60），各自多点+高权重 → strength 大
    far_pts = []
    for center, src_prefix in ((80.0, "farA"), (70.0, "farB"), (60.0, "farC")):
        for i, src in enumerate(("kde", "vp", "fib", "pivot")):
            far_pts.append(
                {
                    "price": center + i * 0.05,
                    "weight": 3.0,
                    "source": f"{src_prefix}_{src}",
                    "label": f"{src_prefix}_{i}",
                }
            )
    # 近端多源簇（约 98，距现价 2%）：强度较小但 sources≥2
    near_pts = [
        {"price": 97.9, "weight": 0.5, "source": "cam", "label": "cam_s1"},
        {"price": 98.0, "weight": 0.5, "source": "atr", "label": "atr_s1"},
        {"price": 98.1, "weight": 0.5, "source": "piv", "label": "piv_s1"},
    ]
    zones = build_confluence_zones(
        far_pts + near_pts,
        last_close=px,
        atr=1.0,
        max_each=3,
        near_pct=0.03,
        near_min_sources=2,
        near_min_points=3,
    )
    assert zones["ok"] is True
    nearest = zones["nearest_support_zone"]
    assert nearest is not None
    # 近端簇中心应贴近 98，而非远端 80
    assert abs(nearest["center"] - 98.0) < 1.0
    assert nearest["center"] > 90.0
    # 列表仍以 TopN 为主，但近端兜底应出现在 supports 中
    assert any(abs(s["center"] - 98.0) < 1.0 for s in zones["supports"])
    assert "params" in zones
    assert zones["params"]["near_pct"] == 0.03


def test_display_supports_sorted_by_center_desc_after_near_fallback():
    """TopN∪近端兜底合并后，支撑应按 center 降序（近现价=支撑1），价格单调。"""
    px = 100.0
    far_pts = []
    for center, src_prefix in ((80.0, "farA"), (70.0, "farB"), (60.0, "farC")):
        for i, src in enumerate(("kde", "vp", "fib", "pivot")):
            far_pts.append(
                {
                    "price": center + i * 0.05,
                    "weight": 3.0,
                    "source": f"{src_prefix}_{src}",
                    "label": f"{src_prefix}_{i}",
                }
            )
    near_pts = [
        {"price": 97.9, "weight": 0.5, "source": "cam", "label": "cam_s1"},
        {"price": 98.0, "weight": 0.5, "source": "atr", "label": "atr_s1"},
        {"price": 98.1, "weight": 0.5, "source": "piv", "label": "piv_s1"},
    ]
    # 压力侧：远端高强度 + 近端弱带
    far_r = []
    for center, src_prefix in ((120.0, "farRA"), (130.0, "farRB"), (140.0, "farRC")):
        for i, src in enumerate(("kde", "vp", "fib", "pivot")):
            far_r.append(
                {
                    "price": center + i * 0.05,
                    "weight": 3.0,
                    "source": f"{src_prefix}_{src}",
                    "label": f"{src_prefix}_{i}",
                }
            )
    near_r = [
        {"price": 101.9, "weight": 0.5, "source": "camr", "label": "cam_r1"},
        {"price": 102.0, "weight": 0.5, "source": "atrr", "label": "atr_r1"},
        {"price": 102.1, "weight": 0.5, "source": "pivr", "label": "piv_r1"},
    ]
    zones = build_confluence_zones(
        far_pts + near_pts + far_r + near_r,
        last_close=px,
        atr=1.0,
        max_each=3,
        near_pct=0.03,
        near_min_sources=2,
        near_min_points=3,
    )
    assert zones["ok"] is True
    supports = zones["supports"]
    resistances = zones["resistances"]
    assert len(supports) >= 2
    centers_s = [s["center"] for s in supports]
    assert centers_s == sorted(centers_s, reverse=True)
    # 近端弱带应排在支撑1（价最高），而非按强度落到末尾
    assert abs(supports[0]["center"] - 98.0) < 1.0
    assert len(resistances) >= 2
    centers_r = [r["center"] for r in resistances]
    assert centers_r == sorted(centers_r)
    assert abs(resistances[0]["center"] - 102.0) < 1.0


def test_near_fallback_disabled_when_near_pct_zero():
    """near_pct=0 时不做近端兜底，nearest 退回 TopN 内最近。"""
    px = 100.0
    far_pts = []
    for center, src_prefix in ((80.0, "farA"), (70.0, "farB"), (60.0, "farC")):
        for i, src in enumerate(("kde", "vp", "fib", "pivot")):
            far_pts.append(
                {
                    "price": center + i * 0.05,
                    "weight": 3.0,
                    "source": f"{src_prefix}_{src}",
                    "label": f"{src_prefix}_{i}",
                }
            )
    near_pts = [
        {"price": 97.9, "weight": 0.5, "source": "cam", "label": "cam_s1"},
        {"price": 98.0, "weight": 0.5, "source": "atr", "label": "atr_s1"},
        {"price": 98.1, "weight": 0.5, "source": "piv", "label": "piv_s1"},
    ]
    zones = build_confluence_zones(
        far_pts + near_pts,
        last_close=px,
        atr=1.0,
        max_each=3,
        near_pct=0.0,
        near_min_sources=2,
        near_min_points=3,
    )
    assert zones["ok"] is True
    nearest = zones["nearest_support_zone"]
    assert nearest is not None
    # 无兜底时 Top3 全是远端，nearest 约在 80
    assert nearest["center"] < 90.0


def test_wide_cluster_split_by_max_zone_width():
    """链式 eps 合并出约 10% 宽簇时，应按 max_zone_width_pct 拆带，禁止单条宽支撑顶到现价。"""
    px = 100.0
    # 90→99 每隔约 1 元，eps≈max(0.35, 1.2)=1.2 → 链式并成一簇，跨度约 10%
    pts = [
        {
            "price": float(90 + i),
            "weight": 1.0,
            "source": f"src{i % 4}",
            "label": f"lv{i}",
        }
        for i in range(10)
    ]
    fat = build_confluence_zones(
        pts, last_close=px, atr=1.0, max_zone_width_pct=0.0, max_each=5
    )
    assert fat["ok"] is True
    # 关闭带宽上限时应出现跨度很大的支撑（约 90→99，相对中心 ~10%）
    wide = [
        s
        for s in fat["supports"]
        if s["low"] <= 91.0
        and (s["high"] - s["low"]) / max(abs(s["center"]), 1e-9) >= 0.08
    ]
    assert len(wide) >= 1
    assert any(s["high"] >= 98.5 for s in wide)

    out = build_confluence_zones(
        pts, last_close=px, atr=1.0, max_zone_width_pct=0.025, max_each=5
    )
    assert out["ok"] is True
    assert out["params"]["max_zone_width_pct"] == 0.025
    # 不得再出现「上沿≈现价且跨度约 10%」的单条宽支撑
    for s in out["supports"]:
        width_pct = (s["high"] - s["low"]) / max(abs(s["center"]), 1e-9)
        assert not (
            s["low"] <= 91.0 and s["high"] >= px - 0.5 and width_pct >= 0.08
        )
        assert width_pct <= 0.025 + 1e-3
    assert any(z.get("split_from_wide_cluster") for z in out["supports"])
    nearest = out["nearest_support_zone"]
    assert nearest is not None
    assert nearest["center"] > 90.0


def test_support_below_val_gets_chips_void_discount():
    """支撑 center < VAL → 保留 strength，写出 strength_adjusted / chips_void / void_note。"""
    from backend_core.analysis.confluence_zones import (
        CHIPS_VOID_STRENGTH_FACTOR,
        annotate_support_chips_void,
    )

    z = {
        "center": 26.27,
        "low": 26.03,
        "high": 26.49,
        "strength": 24.6,
        "sources": ["atr_pivot", "camarilla", "fib", "pivot"],
        "labels": ["a"],
        "n_points": 4,
    }
    out = annotate_support_chips_void(
        z,
        vp_val=27.81,
        vp_lookback=60,
        atr=1.20,
        last_close=26.49,
    )
    assert out["strength"] == 24.6
    assert out["chips_void"] is True
    assert out["void_val"] == 27.81
    assert out["strength_adjusted"] == round(24.6 * CHIPS_VOID_STRENGTH_FACTOR, 3)
    assert "真空区" in out["void_note"]
    assert "VAL=27.81" in out["void_note"]
    assert "ATR" in out["void_note"]

    # VAL 上方：不折减
    above = annotate_support_chips_void(
        {**z, "center": 28.5, "low": 28.2, "high": 28.8},
        vp_val=27.81,
        vp_lookback=60,
        atr=1.20,
        last_close=29.0,
    )
    assert above.get("chips_void") is not True
    assert "strength_adjusted" not in above
    assert above["strength"] == 24.6

    # 无 VAL：原路径
    no_vp = annotate_support_chips_void(z, vp_val=None)
    assert no_vp.get("chips_void") is not True
    assert "strength_adjusted" not in no_vp


def test_build_confluence_annotates_void_via_vp_val():
    """build_confluence_zones 传入 vp_val 时，VAL 下方支撑带带折减字段。"""
    pts = [
        {"price": 26.2, "weight": 1.0, "source": "fib", "label": "f1"},
        {"price": 26.3, "weight": 1.0, "source": "pivot", "label": "p1"},
        {"price": 26.25, "weight": 0.65, "source": "camarilla", "label": "c1"},
        {"price": 26.28, "weight": 0.55, "source": "atr_pivot", "label": "a1"},
        {"price": 28.0, "weight": 1.0, "source": "kde", "label": "kr"},
        {"price": 28.1, "weight": 0.85, "source": "vp", "label": "vp"},
    ]
    out = build_confluence_zones(
        pts,
        last_close=26.49,
        atr=1.2,
        vp_val=27.81,
        vp_lookback=60,
    )
    assert out["ok"] is True
    void_zones = [z for z in out["supports"] if z.get("chips_void")]
    assert len(void_zones) >= 1
    z0 = void_zones[0]
    assert z0["strength_adjusted"] < z0["strength"]
    assert "真空" in (z0.get("void_note") or "")
    # 压力侧不应打 chips_void
    assert all(not z.get("chips_void") for z in out["resistances"])


def test_resistance_near_val_gets_chips_hvz_gain():
    """阻力叠 VAL（601698：27.59≈VAL 27.81）→ strength×1.25，hvz_source=val。"""
    from backend_core.analysis.confluence_zones import (
        CHIPS_HVZ_GAIN,
        annotate_resistance_chips_hvz,
    )

    z = {
        "center": 27.59,
        "low": 27.50,
        "high": 27.70,
        "strength": 15.6,
        "sources": ["atr_pivot", "kde", "pivot", "vp"],
        "labels": ["a"],
        "n_points": 4,
    }
    out = annotate_resistance_chips_hvz(
        z,
        vp_poc=30.40,
        vp_vah=33.47,
        vp_val=27.81,
        vp_lookback=60,
    )
    assert out["strength"] == 15.6
    assert out["chips_hvz"] is True
    assert out["hvz_source"] == "val"
    assert out["hvz_level"] == 27.81
    assert out["strength_adjusted"] == round(15.6 * CHIPS_HVZ_GAIN, 3)
    assert abs(out["strength_adjusted"] - 19.5) < 1e-9
    assert "VAL" in out["hvz_note"]
    assert "密集抛压" in out["hvz_note"]
    assert "19.5" in out["hvz_note"]


def test_resistance_near_poc_or_vah_gets_hvz_gain():
    """阻力叠 POC / VAH 同样增益；优先最近源。"""
    from backend_core.analysis.confluence_zones import (
        CHIPS_HVZ_GAIN,
        annotate_resistance_chips_hvz,
    )

    poc_z = annotate_resistance_chips_hvz(
        {
            "center": 30.35,
            "low": 30.20,
            "high": 30.50,
            "strength": 8.0,
            "sources": ["kde", "vp"],
            "n_points": 2,
        },
        vp_poc=30.40,
        vp_vah=33.47,
        vp_val=27.81,
        vp_lookback=60,
    )
    assert poc_z["chips_hvz"] is True
    assert poc_z["hvz_source"] == "poc"
    assert poc_z["strength_adjusted"] == round(8.0 * CHIPS_HVZ_GAIN, 3)

    vah_z = annotate_resistance_chips_hvz(
        {
            "center": 33.40,
            "low": 33.20,
            "high": 33.55,
            "strength": 6.0,
            "sources": ["kde", "vp"],
            "n_points": 2,
        },
        vp_poc=30.40,
        vp_vah=33.47,
        vp_val=27.81,
        vp_lookback=60,
    )
    assert vah_z["chips_hvz"] is True
    assert vah_z["hvz_source"] == "vah"
    assert vah_z["strength_adjusted"] == round(6.0 * CHIPS_HVZ_GAIN, 3)


def test_resistance_far_from_vp_no_hvz_gain():
    """不重叠关键 VP 水平 → 不增益。"""
    from backend_core.analysis.confluence_zones import annotate_resistance_chips_hvz

    z = {
        "center": 26.72,
        "low": 26.66,
        "high": 26.74,
        "strength": 4.95,
        "sources": ["camarilla", "fib", "pivot"],
        "n_points": 3,
    }
    out = annotate_resistance_chips_hvz(
        z,
        vp_poc=30.40,
        vp_vah=33.47,
        vp_val=27.81,
        vp_lookback=60,
    )
    assert out.get("chips_hvz") is not True
    assert "strength_adjusted" not in out
    assert out["strength"] == 4.95


def test_build_confluence_annotates_hvz_and_keeps_void_side_split():
    """阻力 HVZ 与支撑 void 分边；支撑不打 hvz，阻力不打 void。"""
    pts = [
        {"price": 26.2, "weight": 1.0, "source": "fib", "label": "f1"},
        {"price": 26.3, "weight": 1.0, "source": "pivot", "label": "p1"},
        {"price": 26.25, "weight": 0.65, "source": "camarilla", "label": "c1"},
        {"price": 27.55, "weight": 1.0, "source": "kde", "label": "kr"},
        {"price": 27.60, "weight": 0.85, "source": "vp", "label": "vp"},
        {"price": 27.62, "weight": 0.7, "source": "pivot", "label": "pr"},
        {"price": 27.58, "weight": 0.55, "source": "atr_pivot", "label": "ar"},
    ]
    out = build_confluence_zones(
        pts,
        last_close=26.49,
        atr=1.2,
        vp_val=27.81,
        vp_poc=30.40,
        vp_vah=33.47,
        vp_lookback=60,
    )
    assert out["ok"] is True
    assert any(z.get("chips_void") for z in out["supports"])
    assert all(not z.get("chips_hvz") for z in out["supports"])
    hvz = [z for z in out["resistances"] if z.get("chips_hvz")]
    assert len(hvz) >= 1
    assert all(not z.get("chips_void") for z in out["resistances"])
    z0 = hvz[0]
    assert z0["strength_adjusted"] > z0["strength"]
    assert z0["hvz_source"] in ("poc", "vah", "val")
