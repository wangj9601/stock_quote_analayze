# -*- coding: utf-8 -*-
"""短期三态与结构买点（pattern_tactical）单测。"""

from __future__ import annotations

from backend_core.analysis.pattern_tactical import (
    RESONANCE_PRESSURE_MIN_STRENGTH,
    build_buy_hints,
    build_pattern_hierarchy,
    build_pattern_tactical,
    classify_short_bias,
)


def _hit(
    pattern_type,
    status,
    *,
    confidence=0.8,
    neckline=None,
    upper=None,
    lower=None,
    last_close=None,
    formed_at="2026-01-10",
):
    levels = {}
    if neckline is not None:
        levels["neckline"] = neckline
    if upper is not None:
        levels["upper"] = upper
    if lower is not None:
        levels["lower"] = lower
    if last_close is not None:
        levels["last_close"] = last_close
    return {
        "pattern_type": pattern_type,
        "pattern_family": "test",
        "status": status,
        "confidence": confidence,
        "reason": "unit",
        "key_levels": levels,
        "formed_at": formed_at,
        "pivots": [],
    }


def test_bull_confirmed_above_neck():
    hits = [
        _hit(
            "head_shoulders_bottom",
            "confirmed",
            neckline=10.0,
            lower=8.5,
            last_close=10.2,
        )
    ]
    out = build_pattern_tactical(hits)
    assert out["short_bias"] == "看多"
    assert out["grade"] == "base"
    assert out["buy_hints"]
    assert out["buy_hints"][0]["type"] in ("pullback_buy", "watch")
    assert out["disclaimer"]


def test_bear_confirmed_below_neck_no_hints():
    hits = [
        _hit(
            "head_shoulders_top",
            "confirmed",
            neckline=20.0,
            upper=22.0,
            last_close=19.5,
        )
    ]
    out = build_pattern_tactical(hits)
    assert out["short_bias"] == "看空"
    assert out["buy_hints"] == []
    assert out["risk_note"]
    assert "破位" in out["risk_note"] or "不宜" in out["risk_note"]


def test_forming_with_strong_pressure_is_range():
    hits = [
        _hit(
            "ascending_triangle",
            "forming",
            upper=12.0,
            lower=10.0,
            last_close=11.5,
            confidence=0.7,
        )
    ]
    confluence = {
        "ok": True,
        "nearest_resistance_zone": {
            "center": 11.8,
            "low": 11.7,
            "high": 11.9,
            "strength": RESONANCE_PRESSURE_MIN_STRENGTH + 5,
        },
        "resistances": [],
        "supports": [],
    }
    out = build_pattern_tactical(hits, confluence=confluence)
    assert out["short_bias"] == "震荡"
    assert any(e.get("code") == "resonance_pressure" and e.get("ok") for e in out["evidence"])
    assert out["buy_hints"]
    assert out["buy_hints"][0]["type"] == "watch"


def test_vp_rpe_only_lift_grade_not_bias():
    hits = [
        _hit(
            "double_bottom",
            "confirmed",
            neckline=5.0,
            lower=4.2,
            last_close=5.2,
        )
    ]
    base = build_pattern_tactical(hits)
    assert base["short_bias"] == "看多"
    assert base["grade"] == "base"

    vp = {
        "ok": True,
        "vah": 5.0,
        "last_close": 5.2,
        "nearest_resistance": None,
        "resistance_note": "已突破60日VAH(5.00)，上方无60日筹码压制",
    }
    rpe = {"z_score": 2.5, "signal_type": "领涨观察"}
    enh = build_pattern_tactical(hits, vp=vp)
    assert enh["short_bias"] == "看多"
    assert enh["grade"] == "enhanced"

    strong = build_pattern_tactical(hits, vp=vp, rpe=rpe)
    assert strong["short_bias"] == "看多"
    assert strong["grade"] == "strong"
    assert any(e.get("code") == "vp_break_vah" and e.get("ok") for e in strong["evidence"])
    assert any(e.get("code") == "rpe_lead" and e.get("ok") for e in strong["evidence"])


def test_zero_hits_with_invalidated_count():
    out = build_pattern_tactical([], invalidated_count=3)
    assert out["short_bias"] == "insufficient"
    assert out["bias_label"] == "信息不足"
    assert out["buy_hints"] == []
    assert any(e.get("code") == "no_active_hits" for e in out["evidence"])


def test_bear_flag_upside_invalidate_is_bull():
    """空头旗形向上脱离失效 → 旁路看多（300534 类场景）。"""
    hits = [
        _hit(
            "double_bottom",
            "archived",
            neckline=7.84,
            lower=7.0,
            last_close=18.92,
            confidence=0.72,
        ),
        {
            **_hit(
                "bear_flag",
                "invalidated",
                upper=17.0,
                lower=15.5,
                last_close=18.92,
                confidence=0.65,
            ),
            "reason": "失效:收盘已向上脱离通道",
        },
    ]
    vp = {
        "ok": True,
        "vah": 15.89,
        "last_close": 18.92,
        "nearest_resistance": None,
        "resistance_note": "已突破60日VAH(15.89)，上方无60日筹码压制",
    }
    rpe = {"z_score": 3.22, "signal_type": "领涨观察"}
    out = build_pattern_tactical(hits, vp=vp, rpe=rpe, invalidated_count=1)
    assert out["short_bias"] == "看多"
    assert out["grade"] == "strong"
    assert any(e.get("code") == "inactive_bypass" and e.get("ok") for e in out["evidence"])
    assert out["buy_hints"]
    assert out["buy_hints"][0]["type"] == "watch"


def test_only_invalidated_count_no_bypass_is_insufficient():
    """有失效计数但无旁路证据（未传入失效 hit）→ 信息不足，不是震荡。"""
    out = build_pattern_tactical(
        [_hit("double_bottom", "archived", neckline=10.0, lower=8.0, last_close=9.5)],
        invalidated_count=1,
    )
    # 归档双底但现价已跌破颈线 → 不构成看多旁路
    assert out["short_bias"] == "insufficient"


def test_consol_confirmed_up_is_bull():
    hits = [
        _hit(
            "falling_wedge",
            "confirmed",
            upper=10.0,
            lower=8.0,
            last_close=10.1,  # > upper * 1.005
            confidence=0.75,
        )
    ]
    c = classify_short_bias(hits)
    assert c["short_bias"] == "看多"


def test_consol_confirmed_down_is_bear():
    hits = [
        _hit(
            "rising_wedge",
            "confirmed",
            upper=10.0,
            lower=8.0,
            last_close=7.9,  # < lower * 0.995
            confidence=0.75,
        )
    ]
    c = classify_short_bias(hits)
    assert c["short_bias"] == "看空"
    hints, risk = build_buy_hints("看空", hits[0], grade="base")
    assert hints == []
    assert risk


def test_forming_without_pressure_is_range():
    hits = [
        _hit(
            "double_bottom",
            "forming",
            neckline=10.0,
            lower=8.0,
            last_close=9.5,
        )
    ]
    out = build_pattern_tactical(hits)
    assert out["short_bias"] == "震荡"
    assert out["grade"] == "base"


def test_archived_double_top_near_neck_is_range_not_bear():
    """600722 类：归档双顶贴颈回攻 → 震荡/逼近压力，不得结构破位看空。"""
    hits = [
        _hit(
            "double_bottom",
            "archived",
            neckline=8.65,
            lower=7.75,
            last_close=12.52,
            confidence=0.72,
            formed_at="2026-07-20",
        ),
        _hit(
            "double_top",
            "archived",
            neckline=12.59,
            upper=14.80,
            last_close=12.52,
            confidence=0.72,
            formed_at="2026-05-13",
        ),
    ]
    vp = {
        "ok": True,
        "vah": 11.49,
        "last_close": 12.52,
        "nearest_resistance": None,
        "resistance_note": "已突破60日VAH(11.49)，上方无60日筹码压制",
    }
    market = {"change_pct": 0.0556, "volume_ratio": 3.2}
    out = build_pattern_tactical(
        hits, vp=vp, market=market, asof="2026-08-13", invalidated_count=0
    )
    assert out["short_bias"] == "震荡"
    assert out["bias_label"] in ("逼近压力", "蓄势夹击")
    assert "破位" not in (out.get("rationale") or "") or "而非结构破位" in (
        out.get("rationale") or ""
    )
    assert out["short_bias"] != "看空"
    assert out["buy_hints"]  # P3 保留观察锚


def test_archived_double_top_deep_break_is_bear():
    """归档双顶且相对颈线深破 ≥3% → 旁路看空。"""
    hits = [
        _hit(
            "double_top",
            "archived",
            neckline=20.0,
            upper=22.0,
            last_close=18.0,  # 深破 10%
            confidence=0.72,
            formed_at="2026-07-01",
        )
    ]
    out = build_pattern_tactical(hits, asof="2026-07-20")
    assert out["short_bias"] == "看空"
    assert out["bias_label"] == "结构破位"
    assert out["buy_hints"] == []
    assert out["risk_note"]


def test_momentum_vetoes_archived_bear_bypass():
    """深破本可看空，但放量长阳否决 → 震荡。"""
    hits = [
        _hit(
            "double_top",
            "archived",
            neckline=20.0,
            upper=22.0,
            last_close=18.0,
            confidence=0.72,
            formed_at="2026-07-01",
        )
    ]
    market = {"change_pct": 0.06, "volume_ratio": 2.5}
    out = build_pattern_tactical(hits, market=market, asof="2026-07-20")
    assert out["short_bias"] == "震荡"
    assert "否决" in (out.get("rationale") or "") or "长阳" in (out.get("rationale") or "")


def test_invalidation_clamped_below_entry_low():
    """震荡 watch：失效位须低于买入下沿，且相对 low 至少约 1%（002286 类死锁）。"""
    from backend_core.analysis.pattern_tactical import (
        INVALIDATION_BELOW_ENTRY_PCT,
        _clamp_invalidation,
        build_buy_hints,
    )

    # 回归：low≈7.91 时 inv 不得为 7.93
    low = 7.91
    bad_inv = 7.93
    clamped = _clamp_invalidation(low, bad_inv)
    assert clamped is not None
    assert clamped < low
    assert clamped <= low * (1.0 - INVALIDATION_BELOW_ENTRY_PCT) + 1e-9

    hits = [
        _hit(
            "ascending_triangle",
            "forming",
            upper=8.5,
            lower=7.91,
            last_close=8.1,
            confidence=0.7,
        )
    ]
    # 人为把 defense/inv 抬到 entry 之上：经 build_buy_hints 仍应钳制
    out = build_pattern_tactical(hits)
    assert out["short_bias"] == "震荡"
    assert out["buy_hints"]
    hint = out["buy_hints"][0]
    ez = hint["entry_zone"]
    inv = float(hint["invalidation"])
    entry_low = float(ez["low"])
    assert inv < entry_low
    assert inv <= entry_low * (1.0 - INVALIDATION_BELOW_ENTRY_PCT) + 0.02  # 浮点/round 容忍

    # 直接构造：entry low=7.91，原始 inv=7.93 → clamp 后不可再高于 low
    hints, _ = build_buy_hints(
        "震荡",
        {
            **_hit(
                "ascending_triangle",
                "forming",
                upper=8.5,
                lower=7.91,
                last_close=8.1,
            ),
            "key_levels": {
                "upper": 8.5,
                "lower": 7.91,
                "last_close": 8.1,
            },
        },
    )
    assert hints
    assert float(hints[0]["invalidation"]) < float(hints[0]["entry_zone"]["low"])
    assert float(hints[0]["invalidation"]) != 7.93
    assert float(hints[0]["invalidation"]) < 7.91


def test_near_support_pref_over_far_pattern_lower():
    """603989 类：下降楔下沿过远(≥25%) + 近端强共振 → 主锚近端，不得主锚远端下沿。"""
    hits = [
        _hit(
            "falling_wedge",
            "forming",
            upper=30.11,
            lower=20.0,  # (29.99-20)/29.99 ≈ 33% ≥ 25%
            last_close=29.99,
            confidence=0.75,
        )
    ]
    confluence = {
        "ok": True,
        "nearest_support_zone": {
            "center": 29.26,
            "low": 29.10,
            "high": 29.40,
            "strength": 33.5,
        },
        "supports": [
            {
                "center": 29.26,
                "low": 29.10,
                "high": 29.40,
                "strength": 33.5,
            }
        ],
        "nearest_resistance_zone": {
            "center": 31.50,
            "low": 31.20,
            "high": 31.80,
            "strength": 20.0,
        },
        "resistances": [],
    }
    out = build_pattern_tactical(hits, confluence=confluence)
    assert out["short_bias"] == "震荡"
    assert out["buy_hints"]
    main = out["buy_hints"][0]
    ez = main["entry_zone"]
    assert ez["anchor"] == "near_support_pref"
    # entry 在 ~29 附近，不得落到远端下沿一带
    assert float(ez["low"]) >= 28.0
    assert float(ez["high"]) <= 30.0
    assert abs(float(ez.get("center") or ez["low"]) - 29.26) < 0.5
    inv = float(main["invalidation"])
    assert inv < float(ez["low"])
    # 不得主锚远端下沿
    assert float(ez["low"]) > 25.0
    codes = {e.get("code") for e in (out.get("evidence") or []) if isinstance(e, dict)}
    assert "near_support_pref" in codes
    # 可附带远端极限参考
    if len(out["buy_hints"]) > 1:
        far = [h for h in out["buy_hints"] if h["entry_zone"]["anchor"] in (
            "pattern_lower_far",
            "range_box_low_far",
        )]
        assert far
        assert far[0]["priority"] >= 4
        assert far[0]["priority"] > main["priority"]


def test_pattern_lower_when_near_support_absent_or_not_far():
    """无强近端或下沿不远时：仍可用 pattern_lower；floor_far 无近端则改 break_upper。"""
    # 下沿不远（约 3%）
    hits_near = [
        _hit(
            "falling_wedge",
            "forming",
            upper=31.0,
            lower=29.0,
            last_close=29.99,
            confidence=0.7,
        )
    ]
    confluence_strong = {
        "ok": True,
        "nearest_support_zone": {
            "center": 29.26,
            "low": 29.10,
            "high": 29.40,
            "strength": 33.5,
        },
        "supports": [],
    }
    out1 = build_pattern_tactical(hits_near, confluence=confluence_strong)
    assert out1["short_bias"] == "震荡"
    assert out1["buy_hints"]
    assert out1["buy_hints"][0]["entry_zone"]["anchor"] == "pattern_lower"
    assert abs(float(out1["buy_hints"][0]["entry_zone"]["low"]) - 29.0) < 1.0

    # 下沿很远(≥25%)但无强近端 → 不得主锚 pattern_lower，改 break_upper + 远端 p4
    hits_far = [
        _hit(
            "falling_wedge",
            "forming",
            upper=35.0,
            lower=20.0,
            last_close=29.99,
            confidence=0.7,
        )
    ]
    out2 = build_pattern_tactical(hits_far, confluence={"ok": True, "supports": []})
    assert out2["short_bias"] == "震荡"
    assert out2["buy_hints"]
    main = out2["buy_hints"][0]
    assert main["entry_zone"]["anchor"] == "break_upper"
    assert main["priority"] <= 2
    far_anchors = {
        h["entry_zone"]["anchor"]
        for h in out2["buy_hints"]
        if isinstance(h.get("entry_zone"), dict)
    }
    assert "pattern_lower" not in far_anchors
    assert "pattern_lower_far" in far_anchors or "range_box_low_far" in far_anchors


def test_floor_far_pressing_resistance_forces_break_upper():
    """603186 类：宽通道 floor 远 + 贴身阻力≥10 → 主锚 break_upper，不下主锚远端 ~97。"""
    close = 152.0
    hits = [
        _hit(
            "symmetrical_triangle",
            "forming",
            upper=188.0,
            lower=97.0,  # (152-97)/152 ≈ 36% ≥ 25%
            last_close=close,
            confidence=0.72,
        )
    ]
    confluence = {
        "ok": True,
        "nearest_resistance_zone": {
            "center": 154.5,
            "low": 153.8,
            "high": 154.98,
            "strength": 12.0,
        },
        "resistances": [
            {
                "center": 154.5,
                "low": 153.8,
                "high": 154.98,
                "strength": 12.0,
            },
            {
                "center": 185.0,
                "low": 183.0,
                "high": 190.0,
                "strength": 8.0,
            },
        ],
        "nearest_support_zone": {
            "center": 142.58,
            "low": 141.5,
            "high": 143.2,
            "strength": 6.0,
        },
        "supports": [
            {
                "center": 142.58,
                "low": 141.5,
                "high": 143.2,
                "strength": 6.0,
            },
            {
                "center": 132.57,
                "low": 131.5,
                "high": 133.2,
                "strength": 5.5,
            },
        ],
        "fibonacci": {
            "retracements": [{"ratio": 0.382, "price": 129.5}],
        },
    }
    out = build_pattern_tactical(hits, confluence=confluence)
    assert out["short_bias"] == "震荡"
    assert out["buy_hints"]
    main = out["buy_hints"][0]
    assert main["entry_zone"]["anchor"] == "break_upper"
    assert abs(float(main["entry_zone"]["high"]) - 154.98) < 1.5
    # 目标指向更远阻力 / 形态上沿一带
    assert main.get("target") is not None
    assert float(main["target"]) >= 180.0  # 优先形态上沿 ~188
    assert out.get("risk_note")
    assert "不" in (out.get("risk_note") or "") and (
        "追" in (out.get("risk_note") or "") or "新开" in (out.get("risk_note") or "")
    )
    # 不得把远端 97 当主锚
    assert float(main["entry_zone"]["low"]) > 140.0
    far = [
        h
        for h in out["buy_hints"]
        if h.get("entry_zone", {}).get("anchor") in ("pattern_lower_far", "range_box_low_far")
    ]
    assert far
    assert far[0]["priority"] >= 4
    assert float(far[0]["entry_zone"]["low"]) < 110.0


def test_break_upper_target_prefers_next_resistance_not_thin_upper():
    """002971 类：贴压 break_upper；形态上沿 upside/RR 过薄 → 目标取上沿之上下一档有效阻力。"""
    close = 44.66
    hits = [
        _hit(
            "falling_wedge",
            "forming",
            upper=46.25,
            lower=31.50,  # (44.66-31.5)/44.66 ≈ 29% ≥ 25%
            last_close=close,
            confidence=0.45,
        )
    ]
    confluence = {
        "ok": True,
        "nearest_resistance_zone": {
            "center": 44.88,
            "low": 44.66,
            "high": 45.10,
            "strength": 14.8,
            "sources": ["atr_pivot", "camarilla", "fib", "pivot"],
        },
        "resistances": [
            {
                "center": 44.88,
                "low": 44.66,
                "high": 45.10,
                "strength": 14.8,
            },
            {
                "center": 45.61,
                "low": 45.42,
                "high": 45.79,
                "strength": 1.95,  # 弱，不应抢主目标
            },
            {
                "center": 52.95,
                "low": 52.5,
                "high": 53.4,
                "strength": 5.1,  # atr_pivot+kde
            },
            {
                "center": 61.14,
                "low": 60.5,
                "high": 61.8,
                "strength": 4.8,
            },
        ],
        "supports": [
            {
                "center": 43.75,
                "low": 43.05,
                "high": 44.14,
                "strength": 2.9,  # 弱近端，不得 near_support_pref
            },
        ],
    }
    out = build_pattern_tactical(hits, confluence=confluence)
    assert out["short_bias"] == "震荡"
    assert out["buy_hints"]
    main = out["buy_hints"][0]
    assert main["entry_zone"]["anchor"] == "break_upper"
    # 主目标须抬到下一档有效阻力，不得停在薄 upside 形态上沿 46.25
    assert abs(float(main["target"]) - 52.95) < 0.05
    assert float(main["invalidation"]) < float(main["entry_zone"]["low"])
    # 弱近端 43.75 不买；远端 31.5 仅 p4
    assert all(
        h.get("entry_zone", {}).get("anchor") != "near_support_pref"
        for h in out["buy_hints"]
        if h.get("priority", 99) <= 2
    )
    far = [
        h
        for h in out["buy_hints"]
        if h.get("entry_zone", {}).get("anchor") == "pattern_lower_far"
    ]
    assert far and far[0]["priority"] >= 4


def test_break_upper_thin_upper_without_far_res_falls_back():
    """无更远有效阻力时：薄形态上沿仍可回退到 farther/upper，但不强行虚构远目标。"""
    close = 44.66
    hits = [
        _hit(
            "falling_wedge",
            "forming",
            upper=46.25,
            lower=31.50,
            last_close=close,
            confidence=0.45,
        )
    ]
    confluence = {
        "ok": True,
        "nearest_resistance_zone": {
            "center": 44.88,
            "low": 44.66,
            "high": 45.10,
            "strength": 14.8,
        },
        "resistances": [
            {"center": 44.88, "low": 44.66, "high": 45.10, "strength": 14.8},
            {"center": 45.61, "low": 45.42, "high": 45.79, "strength": 1.95},
        ],
    }
    out = build_pattern_tactical(hits, confluence=confluence)
    main = out["buy_hints"][0]
    assert main["entry_zone"]["anchor"] == "break_upper"
    # 无可合格下一档：回退 farther（可能仍接近上沿一带），但不应等于「强行」52.xx
    tgt = float(main["target"])
    assert tgt >= 45.10
    assert tgt < 50.0


def test_floor_far_b_tier_near_support_pref():
    """floor 远 + 无贴压 + B 档支撑(~6–8%/strength≥5) → near_support_pref。"""
    close = 152.0
    hits = [
        _hit(
            "symmetrical_triangle",
            "forming",
            upper=188.0,
            lower=97.0,
            last_close=close,
            confidence=0.7,
        )
    ]
    # 阻力远离现价（>2%），不触发贴压
    confluence = {
        "ok": True,
        "nearest_resistance_zone": {
            "center": 170.0,
            "low": 168.0,
            "high": 172.0,
            "strength": 15.0,
        },
        "resistances": [
            {"center": 170.0, "low": 168.0, "high": 172.0, "strength": 15.0},
        ],
        "supports": [
            {
                "center": 142.58,
                "low": 141.5,
                "high": 143.2,
                "strength": 6.0,  # B 档：≥5 且距离 (152-142.58)/152≈6.2% ≤8%
            },
            {
                "center": 132.57,
                "low": 131.5,
                "high": 133.2,
                "strength": 5.5,
            },
        ],
        "fibonacci": {"retracements": [{"ratio": 0.382, "price": 129.5}]},
    }
    out = build_pattern_tactical(hits, confluence=confluence)
    assert out["buy_hints"]
    main = out["buy_hints"][0]
    assert main["entry_zone"]["anchor"] == "near_support_pref"
    assert abs(float(main["entry_zone"].get("center") or 0) - 142.58) < 0.5
    assert main["priority"] <= 2
    # 第二档更远近端
    near_hints = [
        h
        for h in out["buy_hints"]
        if h.get("entry_zone", {}).get("anchor") == "near_support_pref"
    ]
    assert len(near_hints) >= 2
    assert near_hints[1]["priority"] > near_hints[0]["priority"]
    assert abs(float(near_hints[1]["entry_zone"].get("center") or 0) - 132.57) < 0.5
    # 共用更紧失效（对齐 Fib 0.382），不得用远端 97
    for h in near_hints:
        inv = float(h["invalidation"])
        assert inv < float(h["entry_zone"]["low"])
        assert inv > 100.0
        assert abs(inv - 129.5) < 2.0 or inv <= 129.5 + 0.5
    assert all(
        h.get("entry_zone", {}).get("anchor") != "pattern_lower"
        for h in out["buy_hints"]
        if h.get("priority", 99) <= 2
    )


def test_non_floor_far_b_tier_not_global():
    """非 floor_far：B 档(5/8%)不得全局生效，仍锚 pattern_lower。"""
    hits = [
        _hit(
            "falling_wedge",
            "forming",
            upper=31.0,
            lower=28.5,  # 距现价约 5% < 25%
            last_close=29.99,
            confidence=0.7,
        )
    ]
    confluence = {
        "ok": True,
        "supports": [
            {
                "center": 28.0,
                "low": 27.8,
                "high": 28.2,
                "strength": 6.0,  # 仅 B 档，非 A
            }
        ],
    }
    out = build_pattern_tactical(hits, confluence=confluence)
    assert out["buy_hints"]
    assert out["buy_hints"][0]["entry_zone"]["anchor"] == "pattern_lower"


def _hs_hit(
    pattern_type,
    status,
    *,
    confidence,
    neckline,
    last_close,
    formed_at,
    pivots,
):
    h = _hit(
        pattern_type,
        status,
        confidence=confidence,
        neckline=neckline,
        last_close=last_close,
        formed_at=formed_at,
    )
    h["pivots"] = pivots
    return h


def test_pattern_hierarchy_hs_nesting_002300_like():
    """大头肩顶 + 小头肩底 → nesting_note 表达时序嵌套主导/从属。"""
    hits = [
        _hs_hit(
            "head_shoulders_top",
            "confirmed",
            confidence=0.75,
            neckline=8.10,
            last_close=7.44,
            formed_at="2026-06-08",
            pivots=[
                {"role": "LS", "date": "2026-03-02", "price": 9.92},
                {"role": "H", "date": "2026-03-10", "price": 12.31},
                {"role": "RS", "date": "2026-03-25", "price": 9.85},
            ],
        ),
        _hs_hit(
            "head_shoulders_bottom",
            "confirmed",
            confidence=0.70,
            neckline=7.83,
            last_close=7.44,
            formed_at="2026-08-10",
            pivots=[
                {"role": "LS", "date": "2026-06-12", "price": 7.14},
                {"role": "H", "date": "2026-07-21", "price": 5.59},
                {"role": "RS", "date": "2026-08-07", "price": 7.08},
            ],
        ),
    ]
    hier = build_pattern_hierarchy(hits)
    assert hier is not None
    assert hier["dominant"]["pattern_type"] == "head_shoulders_top"
    assert hier["subordinate"]["pattern_type"] == "head_shoulders_bottom"
    note = hier["nesting_note"]
    assert "大周期头肩顶" in note
    assert "8.10" in note
    assert "小周期头肩底" in note
    assert "7.83" in note
    assert "下压" in note and "受阻" in note

    out = build_pattern_tactical(hits)
    assert out["nesting_note"] == note
    assert out["pattern_hierarchy"]["relation"] == "nested_opposite"
    assert any(e.get("code") == "pattern_hierarchy" for e in out["evidence"])


def test_pattern_hierarchy_archived_macro_still_nests():
    """归档大周期 + 形成中小周期仍可出嵌套句（不改 short_bias 主逻辑）。"""
    hits = [
        _hs_hit(
            "head_shoulders_top",
            "archived",
            confidence=0.75,
            neckline=8.83,
            last_close=7.44,
            formed_at="2026-01-27",
            pivots=[
                {"role": "LS", "date": "2026-03-02", "price": 9.92},
                {"role": "H", "date": "2026-03-10", "price": 12.31},
                {"role": "RS", "date": "2026-03-25", "price": 9.85},
            ],
        ),
        _hs_hit(
            "head_shoulders_bottom",
            "forming",
            confidence=0.5,
            neckline=7.94,
            last_close=7.44,
            formed_at="2026-08-07",
            pivots=[
                {"role": "LS", "date": "2026-06-12", "price": 7.14},
                {"role": "H", "date": "2026-07-21", "price": 5.59},
                {"role": "RS", "date": "2026-08-07", "price": 7.08},
            ],
        ),
    ]
    hier = build_pattern_hierarchy(hits)
    assert hier is not None
    assert hier["dominant"]["pattern_type"] == "head_shoulders_top"
    assert hier["subordinate"]["pattern_type"] == "head_shoulders_bottom"
    assert "大周期头肩顶" in hier["nesting_note"]
