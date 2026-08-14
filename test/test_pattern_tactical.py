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
    # 各档失效绑定本档下沿（约低 1%），不得共用 Fib 0.382 / 更远档
    inv0 = float(near_hints[0]["invalidation"])
    inv1 = float(near_hints[1]["invalidation"])
    lo0 = float(near_hints[0]["entry_zone"]["low"])
    lo1 = float(near_hints[1]["entry_zone"]["low"])
    assert inv0 < lo0
    assert inv1 < lo1
    assert inv0 > lo1  # 近端主买点失效须高于次档入场区，不共享 ~129.5
    assert abs(inv0 - lo0 * 0.99) < 0.5
    assert abs(inv1 - lo1 * 0.99) < 0.5
    assert all(
        h.get("entry_zone", {}).get("anchor") != "pattern_lower"
        for h in out["buy_hints"]
        if h.get("priority", 99) <= 2
    )


def test_near_support_invalidation_per_tier_not_shared():
    """600206 类：买1 近端强支撑失效贴本档下沿(~46.8)，不得共享次档/Fib 的 42.56。"""
    from backend_core.analysis.pattern_tactical import INVALIDATION_BELOW_ENTRY_PCT

    close = 50.78
    hits = [
        _hit(
            "symmetrical_triangle",
            "forming",
            upper=54.69,
            lower=32.93,  # (50.78-32.93)/50.78 ≈ 35% ≥ 25%
            last_close=close,
            confidence=0.55,
        )
    ]
    confluence = {
        "ok": True,
        "nearest_resistance_zone": {
            "center": 52.83,
            "low": 52.4,
            "high": 53.2,
            "strength": 26.75,
        },
        "resistances": [
            {"center": 52.83, "low": 52.4, "high": 53.2, "strength": 26.75},
        ],
        # 阻力中心距现价 (52.83-50.78)/50.78≈4% > 2%，不触发贴压 break_upper
        "supports": [
            {
                "center": 47.76,
                "low": 47.26,
                "high": 48.04,
                "strength": 21.0,  # A 档近端
            },
            {
                "center": 43.29,
                "low": 42.99,
                "high": 43.65,
                "strength": 6.75,  # watch2
            },
        ],
        "fibonacci": {
            "retracements": [
                {"ratio": 0.382, "price": 53.08},
                {"ratio": 0.618, "price": 42.99},
            ],
        },
    }
    out = build_pattern_tactical(hits, confluence=confluence)
    assert out["short_bias"] == "震荡"
    near_hints = [
        h
        for h in out["buy_hints"]
        if h.get("entry_zone", {}).get("anchor") == "near_support_pref"
    ]
    assert len(near_hints) >= 2
    buy1, buy2 = near_hints[0], near_hints[1]
    assert abs(float(buy1["entry_zone"].get("center") or 0) - 47.76) < 0.2
    assert abs(float(buy1["entry_zone"]["low"]) - 47.26) < 0.05
    assert abs(float(buy2["entry_zone"]["low"]) - 42.99) < 0.05

    inv1 = float(buy1["invalidation"])
    inv2 = float(buy2["invalidation"])
    lo1 = float(buy1["entry_zone"]["low"])
    lo2 = float(buy2["entry_zone"]["low"])
    # 买1：约 46.8 量级，贴本档下沿；不得落到次档 42.56
    assert inv1 < lo1
    assert inv1 >= lo1 * (1.0 - INVALIDATION_BELOW_ENTRY_PCT) - 0.02
    assert abs(inv1 - 46.79) < 0.15
    assert inv1 > 45.0
    assert inv1 != inv2 or inv1 > 45.0  # 明确不共享 42.56
    assert abs(inv1 - 42.56) > 1.0
    # 买2：本档下沿钳制 ≈42.56
    assert inv2 < lo2
    assert abs(inv2 - lo2 * (1.0 - INVALIDATION_BELOW_ENTRY_PCT)) < 0.05
    # 回归：失效不低于买区下沿（须严格低于）
    assert inv1 < lo1 and inv2 < lo2
    # 目标同为形态上沿
    assert abs(float(buy1["target"]) - 54.69) < 0.05
    far = [
        h
        for h in out["buy_hints"]
        if h.get("entry_zone", {}).get("anchor") in ("pattern_lower_far", "range_box_low_far")
    ]
    assert far and far[0]["priority"] >= 4


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


def test_momentum_r4_breakout_when_no_active_hits():
    """无活跃形态 + RPE 领涨 + 上破 R4 → momentum_breakout 买点。"""
    from backend_core.analysis.pattern_tactical import SUPER_SUPPORT_STRENGTH

    rpe = {"z_score": 2.97, "signal_type": "lead"}
    classic = {"camarilla": {"R4": 34.31, "R3": 33.87}}
    confluence = {
        "ok": True,
        "nearest_resistance_zone": {
            "center": 35.47,
            "low": 35.13,
            "high": 35.96,
            "strength": 19.0,
        },
        "resistances": [
            {"center": 35.47, "low": 35.13, "high": 35.96, "strength": 19.0},
        ],
        "supports": [
            {
                "center": 33.36,
                "low": 33.2,
                "high": 33.5,
                "strength": SUPER_SUPPORT_STRENGTH + 0.75,
            }
        ],
        "nearest_support_zone": {
            "center": 33.36,
            "low": 33.2,
            "high": 33.5,
            "strength": SUPER_SUPPORT_STRENGTH + 0.75,
        },
    }
    out = build_pattern_tactical(
        [],
        confluence=confluence,
        rpe=rpe,
        classic=classic,
        market={"last_close": 34.66},
        invalidated_count=2,
    )
    assert out["short_bias"] == "看多"
    assert out["bias_label"] == "动量突破"
    assert out["buy_hints"]
    mom = out["buy_hints"][0]
    assert mom["type"] == "momentum_breakout"
    assert mom["entry_zone"]["anchor"] == "rpe_r4_retest"
    assert abs(float(mom["entry_zone"]["center"]) - 34.31) < 0.02
    assert abs(float(mom["target"]) - 35.47) < 0.05
    assert mom["invalidation"] < float(mom["entry_zone"]["low"])
    assert any(e.get("code") == "momentum_r4_breakout" and e.get("ok") for e in out["evidence"])
    assert out["structure_note"]
    assert "40.75" in out["structure_note"] or "超强结构垫" in out["structure_note"]
    assert abs(float(out["highlight"]["center"]) - 33.36) < 0.02
    assert float(out["highlight"]["strength"]) >= SUPER_SUPPORT_STRENGTH


def test_momentum_r4_when_forming_far_lower_only():
    """forming 远端下沿无近端可用买点时，RPE+R4 仍补动量买点（605100 类）。"""
    hits = [
        _hit(
            "bear_flag",
            "forming",
            upper=35.2,
            lower=27.5,
            last_close=34.66,
            confidence=0.42,
        )
    ]
    rpe = {"z_score": 2.97, "signal_type": "lead"}
    classic = {"camarilla": {"R4": 34.31}}
    confluence = {
        "ok": True,
        "resistances": [
            {"center": 35.47, "low": 35.13, "high": 35.96, "strength": 19.0},
        ],
        "supports": [],
    }
    out = build_pattern_tactical(
        hits,
        confluence=confluence,
        rpe=rpe,
        classic=classic,
        market={"last_close": 34.66},
    )
    assert out["short_bias"] == "震荡"
    types = [h.get("type") for h in out["buy_hints"]]
    assert "momentum_breakout" in types
    mom = next(h for h in out["buy_hints"] if h["type"] == "momentum_breakout")
    assert mom["entry_zone"]["anchor"] == "rpe_r4_retest"
    assert abs(float(mom["entry_zone"]["center"]) - 34.31) < 0.02


def test_super_support_highlight_threshold():
    """strength≥SUPER_SUPPORT_STRENGTH 才出 structure_note。"""
    from backend_core.analysis.pattern_tactical import SUPER_SUPPORT_STRENGTH

    weak = {
        "ok": True,
        "supports": [{"center": 10.0, "low": 9.9, "high": 10.1, "strength": SUPER_SUPPORT_STRENGTH - 0.1}],
    }
    strong = {
        "ok": True,
        "supports": [{"center": 10.0, "low": 9.9, "high": 10.1, "strength": SUPER_SUPPORT_STRENGTH}],
    }
    out_w = build_pattern_tactical([], confluence=weak, market={"last_close": 11.0})
    out_s = build_pattern_tactical([], confluence=strong, market={"last_close": 11.0})
    assert out_w["structure_note"] is None
    assert out_w["highlight"] is None
    assert out_s["structure_note"] and "10.00" in out_s["structure_note"]
    assert out_s["highlight"]["kind"] == "super_support"


def test_momentum_r4_not_when_bearish():
    """看空时不注入动量买点。"""
    hits = [
        _hit(
            "head_shoulders_top",
            "confirmed",
            neckline=36.0,
            upper=38.0,
            last_close=34.66,
        )
    ]
    out = build_pattern_tactical(
        hits,
        rpe={"z_score": 3.0, "signal_type": "lead"},
        classic={"camarilla": {"R4": 34.31}},
        market={"last_close": 34.66},
    )
    assert out["short_bias"] == "看空"
    assert out["buy_hints"] == []
    assert not any(e.get("code") == "momentum_r4_breakout" and e.get("ok") for e in out["evidence"])


def test_breakout_probe_forming_close_above_upper():
    """688110 类：forming 旗形 close>上沿 → 试探突破（引擎仍 forming）。"""
    from backend_core.analysis.pattern_tactical import annotate_hits_breakout_probe

    hits = [
        _hit(
            "bear_flag",
            "forming",
            upper=116.91,
            lower=96.10,
            last_close=117.09,
            confidence=0.42,
        )
    ]
    out = build_pattern_tactical(hits, market={"last_close": 117.09})
    assert out["display_status"] == "试探突破"
    assert out["breakout_probe"] and out["breakout_probe"]["ok"]
    assert out["breakout_probe"]["upper"] == 116.91
    assert "116.91" in (out.get("status_note") or "")
    assert "微幅上破" in (out.get("rationale") or "")
    assert "微幅上破" in (out.get("risk_note") or "")
    assert any(e.get("code") == "breakout_probe" and e.get("ok") for e in out["evidence"])
    # 引擎 status 不变
    assert str(hits[0]["status"]) == "forming"
    annotated = annotate_hits_breakout_probe(hits, out)
    assert annotated[0].get("display_status") == "试探突破"


def test_breakout_probe_not_when_still_inside():
    hits = [
        _hit(
            "bull_flag",
            "forming",
            upper=116.91,
            lower=96.10,
            last_close=116.50,
            confidence=0.42,
        )
    ]
    out = build_pattern_tactical(hits)
    assert out.get("display_status") is None
    assert not out.get("breakout_probe")


def test_wedge_breakout_alert_gms_above_60():
    """601991 类：下降楔形微幅上破 + GMS>60 → 楔形蓄势突破预警；站稳位由 Camarilla 推导。"""
    from backend_core.analysis.pattern_tactical import annotate_hits_breakout_probe

    hits = [
        _hit(
            "falling_wedge",
            "forming",
            upper=6.46,
            lower=5.72,
            last_close=6.48,
            confidence=0.45,
        )
    ]
    out = build_pattern_tactical(
        hits,
        market={"last_close": 6.48},
        gms={"score": 70.0},
        classic={"camarilla": {"S4": 6.54, "R1": 6.98}},
    )
    assert out["display_status"] == "楔形蓄势突破预警"
    assert out["breakout_probe"] and out["breakout_probe"]["ok"]
    alert = out["wedge_breakout_alert"]
    assert alert and alert["ok"]
    assert alert["gms_score"] == 70.0
    assert alert["hold_level"] == 6.54
    assert "camarilla" in str(alert.get("hold_source") or "")
    assert "楔形蓄势突破预警" in (out.get("status_note") or "")
    assert "放量" in (out.get("status_note") or "")
    assert "6.54" in (out.get("status_note") or "")
    assert any(e.get("code") == "wedge_breakout_alert" and e.get("ok") for e in out["evidence"])
    annotated = annotate_hits_breakout_probe(hits, out)
    assert annotated[0].get("display_status") == "楔形蓄势突破预警"
    assert annotated[0].get("wedge_breakout_alert") is True


def test_wedge_breakout_alert_maps_next_resistance_target():
    """预警触发 + 上方高强共振阻力 → 写出约 7.12@12.2 预警目标；买点不再挂上沿。"""
    hits = [
        _hit(
            "falling_wedge",
            "forming",
            upper=6.46,
            lower=5.72,
            last_close=6.48,
            confidence=0.45,
        )
    ]
    confluence = {
        "ok": True,
        "resistances": [
            {
                "center": 6.50,
                "low": 6.48,
                "high": 6.54,
                "strength": 4.95,
                "sources": ["camarilla", "fib", "pivot"],
            },
            {
                "center": 6.71,
                "low": 6.69,
                "high": 6.73,
                "strength": 5.1,
                "sources": ["atr_pivot", "camarilla", "pivot"],
            },
            {
                "center": 7.12,
                "low": 7.05,
                "high": 7.17,
                "strength": 12.2,
                "sources": ["atr_pivot", "camarilla", "fib", "pivot"],
            },
            {
                "center": 7.36,
                "low": 7.30,
                "high": 7.40,
                "strength": 5.85,
                "sources": ["camarilla", "kde", "pivot"],
            },
        ],
        "nearest_resistance_zone": {
            "center": 6.50,
            "low": 6.48,
            "high": 6.54,
            "strength": 4.95,
        },
    }
    out = build_pattern_tactical(
        hits,
        market={"last_close": 6.48},
        gms={"score": 70.0},
        classic={"camarilla": {"S4": 6.54, "R1": 6.98}, "atr": 0.48},
        confluence=confluence,
    )
    assert out["display_status"] == "楔形蓄势突破预警"
    alert = out["wedge_breakout_alert"]
    assert alert and alert["ok"]
    assert alert.get("target") == 7.12
    assert alert.get("alert_target") == 7.12
    assert alert.get("target_strength") == 12.2
    assert alert.get("alert_invalidation") == round(6.46 * 0.995, 2)
    note = out.get("status_note") or ""
    assert "预警目标：7.12 附近" in note
    assert "强度 12.2" in note
    assert "共振阻力带" in note
    # 买点目标不应再挂已破上沿 6.46
    for h in out.get("buy_hints") or []:
        if isinstance(h, dict) and h.get("target") is not None:
            assert float(h["target"]) == 7.12
    # 右侧突破跟进买点：站稳 6.54 / 失效≈上沿×0.995 / 目标 7.12
    follow = next(
        (h for h in (out.get("buy_hints") or []) if h.get("type") == "breakout_follow"),
        None,
    )
    assert follow is not None
    assert follow["entry_zone"]["anchor"] == "wedge_hold_level"
    assert abs(float(follow["entry_zone"]["center"]) - 6.54) < 0.02
    assert float(follow["invalidation"]) == round(6.46 * 0.995, 2)
    assert float(follow["target"]) == 7.12
    assert "1.5" in str(follow.get("trigger") or "")
    assert follow.get("trigger_status") == "pending"  # close 6.48 < hold 6.54
    assert follow.get("volume_condition", {}).get("min_ratio") == 1.5
    assert any(e.get("code") == "wedge_breakout_follow" and e.get("ok") for e in out["evidence"])


def test_wedge_breakout_follow_triggered_when_close_and_volume():
    """Close>hold 且量比>1.5 → trigger_status=triggered（hint 构建层）。"""
    from backend_core.analysis.pattern_tactical import _build_wedge_breakout_follow_hint

    alert = {
        "ok": True,
        "hold_level": 6.54,
        "upper": 6.46,
        "alert_invalidation": round(6.46 * 0.995, 2),
        "alert_target": 7.12,
        "target": 7.12,
    }
    follow = _build_wedge_breakout_follow_hint(
        alert,
        close=6.60,
        market={"last_close": 6.60, "volume_ratio": 1.8},
        grade="base",
        atr=0.48,
    )
    assert follow is not None
    assert follow["type"] == "breakout_follow"
    assert follow["trigger_status"] == "triggered"
    assert follow["conditions_met"]["close_above_hold"] is True
    assert follow["conditions_met"]["volume_above_ma20"] is True
    assert float(follow["target"]) == 7.12
    assert abs(float(follow["entry_zone"]["center"]) - 6.54) < 0.02
    assert float(follow["invalidation"]) == round(6.46 * 0.995, 2)


def test_wedge_breakout_follow_coexists_with_left_watch():
    """预警注入右侧跟进后，左侧 watch 仍保留且优先级更低。"""
    hits = [
        _hit(
            "falling_wedge",
            "forming",
            upper=6.46,
            lower=5.72,
            last_close=6.48,
            confidence=0.45,
        )
    ]
    confluence = {
        "ok": True,
        "resistances": [
            {"center": 7.12, "low": 7.05, "high": 7.17, "strength": 12.2},
        ],
        "supports": [
            {"center": 5.72, "low": 5.67, "high": 5.77, "strength": 6.0},
        ],
    }
    out = build_pattern_tactical(
        hits,
        market={"last_close": 6.48, "volume_ratio": 0.9},
        gms={"score": 70.0},
        classic={"camarilla": {"S4": 6.54}, "atr": 0.48},
        confluence=confluence,
    )
    hints = out.get("buy_hints") or []
    follow = next((h for h in hints if h.get("type") == "breakout_follow"), None)
    left = [h for h in hints if h.get("type") in ("watch", "pullback_buy")]
    assert follow is not None
    assert left
    assert hints[0]["type"] == "breakout_follow"
    assert int(follow.get("priority") or 99) <= min(int(h.get("priority") or 99) for h in left)
    assert follow.get("trigger_status") == "pending"


def test_wedge_breakout_follow_not_when_gms_le_60():
    """无楔形预警时不注入右侧跟进买点。"""
    hits = [
        _hit(
            "falling_wedge",
            "forming",
            upper=6.46,
            lower=5.72,
            last_close=6.48,
            confidence=0.45,
        )
    ]
    out = build_pattern_tactical(
        hits,
        market={"last_close": 6.48, "volume_ratio": 2.0},
        gms={"score": 60.0},
        classic={"camarilla": {"S4": 6.54}},
    )
    assert not out.get("wedge_breakout_alert")
    assert not any(h.get("type") == "breakout_follow" for h in (out.get("buy_hints") or []))


def test_wedge_breakout_alert_no_resistance_allows_empty_target():
    """预警触发但上方无有效阻力 → target 可空（允许真空占位）。"""
    hits = [
        _hit(
            "falling_wedge",
            "forming",
            upper=6.46,
            lower=5.72,
            last_close=6.48,
            confidence=0.45,
        )
    ]
    out = build_pattern_tactical(
        hits,
        market={"last_close": 6.48},
        gms={"score": 70.0},
        classic={"camarilla": {"S4": 6.54}},
        confluence={"ok": True, "resistances": []},
    )
    alert = out["wedge_breakout_alert"]
    assert alert and alert["ok"]
    assert alert.get("target") is None
    assert alert.get("alert_target") is None
    assert "预警目标" not in (out.get("status_note") or "")


def test_wedge_breakout_alert_not_when_gms_le_60():
    """GMS≤60：仍保留普通试探突破，不升为蓄势预警。"""
    hits = [
        _hit(
            "falling_wedge",
            "forming",
            upper=6.46,
            lower=5.72,
            last_close=6.48,
            confidence=0.45,
        )
    ]
    out = build_pattern_tactical(
        hits,
        market={"last_close": 6.48},
        gms={"score": 60.0},
        classic={"camarilla": {"S4": 6.54}},
    )
    assert out["display_status"] == "试探突破"
    assert out["breakout_probe"] and out["breakout_probe"]["ok"]
    assert not out.get("wedge_breakout_alert")
    assert "微幅上破" in (out.get("status_note") or "")


def test_wedge_breakout_alert_not_without_gms():
    """无 GMS 字段：仅试探突破，预警字段可选为空。"""
    hits = [
        _hit(
            "falling_wedge",
            "forming",
            upper=6.46,
            lower=5.72,
            last_close=6.48,
            confidence=0.45,
        )
    ]
    out = build_pattern_tactical(hits, market={"last_close": 6.48})
    assert out["display_status"] == "试探突破"
    assert not out.get("wedge_breakout_alert")
    assert out.get("gms_score") is None


def test_clamp_invalidation_atr_high_vol_near_1138():
    """高 ATR%：相对支撑锚用 k×ATR 缓冲 → 约 113.80（688110）。"""
    from backend_core.analysis.pattern_tactical import (
        INVALIDATION_ATR_K,
        _clamp_invalidation,
    )

    low = 114.16
    atr = 9.40
    close = 117.09
    # 无 ATR：约 1%
    low_vol = _clamp_invalidation(low, low)
    assert low_vol == round(low * 0.99, 2)
    # 高 ATR：0.04×ATR ≈ 0.376 → 113.78
    high = _clamp_invalidation(low, low, atr=atr, close=close)
    expect = round(low - INVALIDATION_ATR_K * atr, 2)
    assert high == expect
    assert abs(high - 113.80) < 0.05
    assert high < low


def test_near_support_invalidation_atr_adaptive():
    """近端共振 + 高 ATR：失效低于买区下沿，缓冲随 ATR 自适应。"""
    hits = [
        _hit(
            "falling_wedge",
            "forming",
            upper=130.0,
            lower=80.0,  # floor_far
            last_close=117.09,
            confidence=0.5,
        )
    ]
    confluence = {
        "ok": True,
        "supports": [
            {
                "center": 114.16,
                "low": 113.05,
                "high": 114.96,
                "strength": 28.5,
            }
        ],
        "nearest_support_zone": {
            "center": 114.16,
            "low": 113.05,
            "high": 114.96,
            "strength": 28.5,
        },
    }
    out = build_pattern_tactical(
        hits,
        confluence=confluence,
        market={"last_close": 117.09},
        classic={"atr": 9.40},
    )
    assert out["buy_hints"]
    main = next(
        h
        for h in out["buy_hints"]
        if (h.get("entry_zone") or {}).get("anchor") == "near_support_pref"
    )
    ez = main["entry_zone"]
    inv = float(main["invalidation"])
    assert inv < float(ez["low"])
    # 相对买区下沿的缓冲应体现 ATR 自适应（不超过约 4%）
    assert inv >= float(ez["low"]) * 0.96 - 0.02


def test_near_support_pref_uses_strength_adjusted_for_void():
    """VAL 下方真空支撑用折减强度门槛；虚高原始强度不得单独过门槛。"""
    from backend_core.analysis.pattern_tactical import _pick_near_strong_support

    close = 26.49
    # 原始 9.5 < 10，折减后更低 → 不过 A 档
    void_weak = {
        "center": 26.27,
        "low": 26.03,
        "high": 26.49,
        "strength": 9.5,
        "strength_adjusted": 8.075,
        "chips_void": True,
        "void_note": "位于60日筹码真空区",
    }
    assert _pick_near_strong_support({"supports": [void_weak]}, close) is None

    # 原始 24.6 过门槛，折减后 20.91 仍过 → 可选中，且 entry 带 void 字段
    void_strong = {
        "center": 26.27,
        "low": 26.03,
        "high": 26.40,
        "strength": 24.6,
        "strength_adjusted": 20.91,
        "chips_void": True,
        "void_note": "位于60日筹码真空区（VAL=27.81），需防范高ATR击穿效应",
    }
    picked = _pick_near_strong_support({"supports": [void_strong]}, close)
    assert picked is not None
    assert picked["center"] == 26.27

    # 真空折减后 9.35 < 10，非真空 12 应优先（按折减后排序）
    void_inflated = {
        "center": 26.10,
        "low": 25.90,
        "high": 26.20,
        "strength": 11.0,
        "strength_adjusted": 9.35,
        "chips_void": True,
    }
    solid = {
        "center": 25.80,
        "low": 25.60,
        "high": 25.95,
        "strength": 12.0,
    }
    picked2 = _pick_near_strong_support(
        {"supports": [void_inflated, solid]}, close
    )
    assert picked2 is not None
    assert picked2["center"] == 25.80


def _conf_ultra(
    *,
    close=13.92,
    s_center=13.77,
    s_str=29.25,
    r_center=13.96,
    r_str=43.25,
    s_low=13.71,
    s_high=13.80,
    r_low=13.92,
    r_high=14.08,
):
    return {
        "ok": True,
        "nearest_support_zone": {
            "center": s_center,
            "low": s_low,
            "high": s_high,
            "strength": s_str,
        },
        "nearest_resistance_zone": {
            "center": r_center,
            "low": r_low,
            "high": r_high,
            "strength": r_str,
        },
        "supports": [],
        "resistances": [],
    }


def test_ultra_squeeze_triggers_when_narrow_and_strong():
    """宽度<2.5% 且双侧强度>20 → 极窄箱体变盘临界（002414 口径）。"""
    from backend_core.analysis.pattern_tactical import (
        ULTRA_SQUEEZE_DISPLAY_STATUS,
        ULTRA_SQUEEZE_MIN_STRENGTH,
        ULTRA_SQUEEZE_WIDTH_PCT,
        annotate_hits_breakout_probe,
    )

    close = 13.92
    conf = _conf_ultra()
    hits = [
        _hit(
            "head_shoulders_top",
            "forming",
            neckline=8.40,
            upper=14.02,
            last_close=close,
            confidence=0.55,
        )
    ]
    out = build_pattern_tactical(
        hits, confluence=conf, market={"last_close": close}
    )
    assert out["display_status"] == ULTRA_SQUEEZE_DISPLAY_STATUS
    ultra = out["ultra_squeeze"]
    assert ultra and ultra["ok"]
    assert ultra["support"] == 13.77
    assert ultra["resistance"] == 13.96
    assert ultra["width_pct"] < ULTRA_SQUEEZE_WIDTH_PCT
    assert ultra["support_strength"] > ULTRA_SQUEEZE_MIN_STRENGTH
    assert ultra["resistance_strength"] > ULTRA_SQUEEZE_MIN_STRENGTH
    assert ultra["break_observe"] == 14.08  # 阻力上沿
    assert ultra["pullback"] == 13.77
    note = out.get("status_note") or ""
    assert "极窄空间夹击" in note
    assert "13.77" in note
    assert "14.08" in note
    assert "盈亏比不足" in (out.get("risk_note") or "")
    assert any(e.get("code") == "ultra_squeeze" and e.get("ok") for e in out["evidence"])
    annotated = annotate_hits_breakout_probe(hits, out)
    assert annotated[0].get("display_status") == ULTRA_SQUEEZE_DISPLAY_STATUS
    assert annotated[0].get("ultra_squeeze") is True


def test_ultra_squeeze_not_when_width_too_wide():
    """带宽过大不触发。"""
    close = 13.92
    conf = _conf_ultra(s_center=13.20, r_center=14.50, s_high=13.30, r_low=14.40, r_high=14.60)
    # (14.50-13.20)/13.92 ≈ 9.3% > 2.5%
    out = build_pattern_tactical(
        [_hit("double_top", "forming", neckline=12.0, last_close=close)],
        confluence=conf,
        market={"last_close": close},
    )
    assert out.get("display_status") != "极窄箱体变盘临界"
    assert not (out.get("ultra_squeeze") or {}).get("ok")


def test_ultra_squeeze_not_when_strength_insufficient():
    """任一侧强度不足不触发。"""
    close = 13.92
    conf = _conf_ultra(s_str=19.0, r_str=43.25)
    out = build_pattern_tactical(
        [_hit("double_top", "forming", neckline=12.0, last_close=close)],
        confluence=conf,
        market={"last_close": close},
    )
    assert not (out.get("ultra_squeeze") or {}).get("ok")

    conf2 = _conf_ultra(s_str=29.0, r_str=20.0)  # 须 >20，等于 20 不触发
    out2 = build_pattern_tactical(
        [_hit("double_top", "forming", neckline=12.0, last_close=close)],
        confluence=conf2,
        market={"last_close": close},
    )
    assert not (out2.get("ultra_squeeze") or {}).get("ok")


def test_ultra_squeeze_yields_to_wedge_breakout_alert():
    """更强楔形蓄势突破预警优先，极窄箱体仅记证据不覆盖盘口态。"""
    close = 6.48
    hits = [
        _hit(
            "falling_wedge",
            "forming",
            upper=6.46,
            lower=5.72,
            last_close=close,
            confidence=0.45,
        )
    ]
    # 围绕现价构造极窄强共振
    conf = {
        "ok": True,
        "nearest_support_zone": {
            "center": 6.40,
            "low": 6.35,
            "high": 6.42,
            "strength": 25.0,
        },
        "nearest_resistance_zone": {
            "center": 6.50,
            "low": 6.48,
            "high": 6.55,
            "strength": 30.0,
        },
        "supports": [],
        "resistances": [
            {
                "center": 6.80,
                "low": 6.75,
                "high": 6.85,
                "strength": 12.0,
            }
        ],
    }
    out = build_pattern_tactical(
        hits,
        confluence=conf,
        market={"last_close": close},
        gms={"score": 70.0},
    )
    assert out["display_status"] == "楔形蓄势突破预警"
    assert out["ultra_squeeze"] and out["ultra_squeeze"]["ok"]
    ev = [e for e in out["evidence"] if e.get("code") == "ultra_squeeze"]
    assert ev and ev[0].get("suppressed_by") == "wedge_breakout_alert"


def test_ultra_squeeze_covers_plain_breakout_probe():
    """无楔形预警时，极窄箱体可覆盖普通试探突破盘口态。"""
    close = 11.55
    hits = [
        _hit(
            "ascending_triangle",
            "forming",
            upper=11.50,
            lower=10.80,
            last_close=close,
            confidence=0.6,
        )
    ]
    conf = {
        "ok": True,
        "nearest_support_zone": {
            "center": 11.40,
            "low": 11.35,
            "high": 11.42,
            "strength": 22.0,
        },
        "nearest_resistance_zone": {
            "center": 11.60,
            "low": 11.55,
            "high": 11.68,
            "strength": 28.0,
        },
        "supports": [],
        "resistances": [],
    }
    out = build_pattern_tactical(
        hits, confluence=conf, market={"last_close": close}
    )
    assert out["breakout_probe"] and out["breakout_probe"]["ok"]
    assert not out.get("wedge_breakout_alert")
    assert out["display_status"] == "极窄箱体变盘临界"
    assert "极窄空间夹击" in (out.get("status_note") or "")


def test_ultra_squeeze_narrows_pullback_entry_to_support_low():
    """极窄箱体：回踩 entry 收窄到支撑下沿附近，不含现价（002414 口径 13.66–13.71）。"""
    close = 13.92
    conf = _conf_ultra()
    hits = [
        _hit(
            "head_shoulders_top",
            "forming",
            neckline=8.40,
            upper=14.02,
            last_close=close,
            confidence=0.55,
        )
    ]
    out = build_pattern_tactical(
        hits, confluence=conf, market={"last_close": close}
    )
    assert out["display_status"] == "极窄箱体变盘临界"
    hints = out.get("buy_hints") or []
    assert hints, "应保留回踩挂单买点"
    pullbacks = [
        h
        for h in hints
        if isinstance(h, dict)
        and isinstance(h.get("entry_zone"), dict)
        and (
            "support" in str(h["entry_zone"].get("anchor") or "").lower()
            or h["entry_zone"].get("ultra_squeeze_narrowed")
            or "回踩" in str(h.get("trigger") or "")
        )
    ]
    assert pullbacks
    ez = pullbacks[0]["entry_zone"]
    assert ez.get("ultra_squeeze_narrowed") is True
    # 支撑带下沿 13.71 → 挂单约 13.66–13.71
    assert abs(float(ez["high"]) - 13.71) < 0.02
    assert abs(float(ez["low"]) - 13.66) < 0.03
    assert float(ez["high"]) <= 13.71 + 0.01
    # 禁止覆盖现价附近
    assert float(ez["high"]) < close - 0.15
    assert not (float(ez["low"]) <= close <= float(ez["high"]))
    assert float(pullbacks[0]["invalidation"]) < float(ez["low"])
    note = (pullbacks[0].get("space_note") or "") + (pullbacks[0].get("risk_note") or "")
    assert "仅支撑下沿挂单" in note or "盈亏比不足" in note
    top = out.get("risk_note") or ""
    assert "盈亏比不足" in top


def test_ultra_squeeze_demotes_break_upper_no_chase():
    """极窄箱体：贴压 break_upper 降为观察，注明变盘前不追。"""
    close = 13.92
    conf = _conf_ultra()
    # 人为注入突破类买点，验证夹缝硬约束
    from backend_core.analysis.pattern_tactical import (
        _apply_ultra_squeeze_to_hints,
        _ultra_squeeze_payload,
    )

    ultra = _ultra_squeeze_payload(conf, close)
    assert ultra and ultra["ok"]
    raw_hints = [
        {
            "type": "break_upper",
            "entry_zone": {"low": 13.90, "high": 14.00, "anchor": "break_upper"},
            "trigger": "观察上破 14.08 再跟",
            "invalidation": 13.70,
            "target": 14.41,
            "priority": 2,
        },
        {
            "type": "watch",
            "entry_zone": {"low": 13.66, "high": 13.88, "anchor": "nearest_support"},
            "trigger": "回踩形态下沿/近端支撑企稳",
            "invalidation": 13.52,
            "target": 13.96,
            "priority": 2,
        },
    ]
    narrowed, risk = _apply_ultra_squeeze_to_hints(raw_hints, ultra, None)
    assert risk and "盈亏比不足" in risk
    bu = [h for h in narrowed if "break_upper" in str((h.get("entry_zone") or {}).get("anchor"))]
    assert bu
    assert bu[0]["type"] == "watch"
    assert "变盘前不追" in str(bu[0].get("trigger") or "")
    pb = [h for h in narrowed if h.get("entry_zone", {}).get("ultra_squeeze_narrowed")]
    assert pb
    assert abs(float(pb[0]["entry_zone"]["high"]) - 13.71) < 0.02
    assert float(pb[0]["entry_zone"]["high"]) < close - 0.1


def test_non_ultra_squeeze_keeps_wide_entry_zone():
    """非极窄（带宽过大）不强制收窄 entry。"""
    close = 13.92
    conf = _conf_ultra(
        s_center=13.20, r_center=14.50, s_high=13.30, r_low=14.40, r_high=14.60, s_low=13.10
    )
    hits = [
        _hit("double_top", "forming", neckline=12.0, last_close=close, confidence=0.5)
    ]
    out = build_pattern_tactical(
        hits, confluence=conf, market={"last_close": close}
    )
    assert not (out.get("ultra_squeeze") or {}).get("ok")
    hints = out.get("buy_hints") or []
    for h in hints:
        ez = h.get("entry_zone") if isinstance(h.get("entry_zone"), dict) else {}
        assert not ez.get("ultra_squeeze_narrowed")


def _conf_asymmetry(
    *,
    close=35.05,
    s_center=34.42,
    s_str=1.9,
    r_center=35.21,
    r_str=65.5,
    s_low=34.34,
    s_high=34.50,
    r_low=35.05,
    r_high=35.89,
):
    """000063 口径：强压弱撑 + 贴阻。"""
    return {
        "ok": True,
        "nearest_support_zone": {
            "center": s_center,
            "low": s_low,
            "high": s_high,
            "strength": s_str,
        },
        "nearest_resistance_zone": {
            "center": r_center,
            "low": r_low,
            "high": r_high,
            "strength": r_str,
        },
        "supports": [],
        "resistances": [],
    }


def test_asymmetry_storm_triggers_when_ratio_and_near():
    """比率>5 且距阻<1.5% → 高倾角风暴预警（000063 口径）。"""
    from backend_core.analysis.pattern_tactical import (
        ASYMMETRY_NEAR_RESIST_PCT,
        ASYMMETRY_STORM_DISPLAY_STATUS,
        ASYMMETRY_STRENGTH_RATIO,
        annotate_hits_breakout_probe,
    )

    close = 35.05
    conf = _conf_asymmetry()
    hits = [
        _hit(
            "falling_wedge",
            "forming",
            upper=35.38,
            lower=33.06,
            last_close=close,
            confidence=0.45,
        )
    ]
    out = build_pattern_tactical(
        hits, confluence=conf, market={"last_close": close}
    )
    assert out["display_status"] == ASYMMETRY_STORM_DISPLAY_STATUS
    storm = out["asymmetry_storm"]
    assert storm and storm["ok"]
    assert storm["resistance_strength"] == 65.5
    assert storm["support_strength"] == 1.9
    assert storm["strength_ratio"] > ASYMMETRY_STRENGTH_RATIO
    assert storm["dist_to_resist_pct"] < ASYMMETRY_NEAR_RESIST_PCT
    note = out.get("status_note") or ""
    assert "65.5" in note and "1.9" in note
    assert "极度碾压" in note
    assert "不宜追涨" in (out.get("risk_note") or "")
    assert any(e.get("code") == "asymmetry_storm" and e.get("ok") for e in out["evidence"])
    annotated = annotate_hits_breakout_probe(hits, out)
    assert annotated[0].get("display_status") == ASYMMETRY_STORM_DISPLAY_STATUS
    assert annotated[0].get("asymmetry_storm") is True


def test_asymmetry_storm_not_when_ratio_insufficient():
    """强度比不足不触发。"""
    close = 35.05
    conf = _conf_asymmetry(s_str=20.0, r_str=65.5)  # 65.5/20 ≈ 3.3 < 5
    out = build_pattern_tactical(
        [_hit("double_top", "forming", neckline=30.0, last_close=close)],
        confluence=conf,
        market={"last_close": close},
    )
    assert out.get("display_status") != "高倾角风暴预警"
    assert not (out.get("asymmetry_storm") or {}).get("ok")


def test_asymmetry_storm_not_when_far_from_resistance():
    """距阻过远不触发。"""
    close = 33.50
    # 阻力 35.21，距约 5.1% > 1.5%
    conf = _conf_asymmetry(close=close, r_low=35.05, r_high=35.89, r_center=35.21)
    out = build_pattern_tactical(
        [_hit("double_top", "forming", neckline=30.0, last_close=close)],
        confluence=conf,
        market={"last_close": close},
    )
    assert not (out.get("asymmetry_storm") or {}).get("ok")


def test_asymmetry_storm_overrides_wedge_breakout_alert():
    """头重脚轻贴强压时，风暴预警优先于楔形蓄势突破预警。"""
    close = 35.10
    hits = [
        _hit(
            "falling_wedge",
            "forming",
            upper=35.00,
            lower=33.06,
            last_close=close,
            confidence=0.45,
        )
    ]
    conf = _conf_asymmetry(close=close, r_low=35.05, r_center=35.21, r_high=35.89)
    out = build_pattern_tactical(
        hits,
        confluence=conf,
        market={"last_close": close},
        gms={"score": 70.0},
    )
    assert out.get("wedge_breakout_alert") and out["wedge_breakout_alert"]["ok"]
    assert out["display_status"] == "高倾角风暴预警"
    assert out["asymmetry_storm"] and out["asymmetry_storm"]["ok"]
    ev = [e for e in out["evidence"] if e.get("code") == "wedge_breakout_alert"]
    assert ev and ev[0].get("suppressed_by") == "asymmetry_storm"
    # 买点侧避免激进追涨
    for h in out.get("buy_hints") or []:
        assert h.get("type") == "watch"
        assert "不追" in str(h.get("trigger") or "") or "观察" in str(h.get("trigger") or "")
