# -*- coding: utf-8 -*-
"""短期三态与结构买点（pattern_tactical）单测。"""

from __future__ import annotations

from backend_core.analysis.pattern_tactical import (
    RESONANCE_PRESSURE_MIN_STRENGTH,
    build_buy_hints,
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