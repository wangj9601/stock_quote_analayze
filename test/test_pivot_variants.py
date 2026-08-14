# -*- coding: utf-8 -*-
from datetime import date, timedelta

from backend_core.analysis.pivot_variants import (
    atr_pivot_bands,
    attach_nearest,
    camarilla_from_hlc,
    compute_vol_pivots_from_parsed,
    extreme_role_flip_note,
)


def test_camarilla_formula():
    cam = camarilla_from_hlc(12.0, 10.0, 11.0)
    rng = 2.0
    # 对外两位小数
    assert cam["R4"] == round(11.0 + rng * 1.1 / 2, 2)
    assert cam["R3"] == round(11.0 + rng * 1.1 / 4, 2)
    assert cam["R1"] == round(11.0 + rng * 1.1 / 12, 2)
    assert cam["S1"] == round(11.0 - rng * 1.1 / 12, 2)
    assert cam["S4"] == round(11.0 - rng * 1.1 / 2, 2)


def test_atr_pivot_bands():
    ap = atr_pivot_bands(10.0, 0.5)
    assert ap["R1"] == 10.5
    assert ap["S1"] == 9.5
    assert ap["R2"] == 11.0
    assert ap["S2"] == 9.0


def test_compute_vol_pivots_from_parsed():
    parsed = []
    base = date(2025, 1, 1)
    for i in range(20):
        c = 10.0 + i * 0.1
        parsed.append((base + timedelta(days=i), c + 0.5, c - 0.5, c))
    out = compute_vol_pivots_from_parsed(parsed, last_close=11.5, classic_p=11.0)
    assert out["camarilla"] is not None
    assert out["camarilla"]["R1"] is not None
    assert out["atr"] is not None and out["atr"] > 0
    assert out["atr_pivot"] is not None
    assert out["atr_pivot"]["R1"] > out["atr_pivot"]["P"]


def test_extreme_role_flip_note_template():
    assert (
        extreme_role_flip_note(side="below_support", level_key="S4", price=7.51)
        == "已跌破Camarilla最低档S4(7.51)并转为阻力"
    )
    assert (
        extreme_role_flip_note(side="above_resistance", level_key="R4", price=9.2)
        == "已突破Camarilla最高档R4(9.20)并转为支撑"
    )


def test_camarilla_s4_breach_role_flip():
    cam = camarilla_from_hlc(7.67, 7.5, 7.6)
    # S4≈7.51；现价跌破全部 Cam 档
    out = attach_nearest(
        cam,
        7.44,
        ("S4", "S3", "S2", "S1", "R1", "R2", "R3", "R4"),
        label="Camarilla",
        role_flip_extremes=("S4", "R4"),
    )
    assert out["nearest_support"] is None
    assert out["nearest_resistance"] == cam["S4"]
    assert out["support_note"] == extreme_role_flip_note(
        side="below_support", level_key="S4", price=cam["S4"]
    )
    assert "并转为阻力" in out["support_note"]
    assert "暂无同窗支撑" not in out["support_note"]
    assert out["extreme_role_flip"]["level"] == "S4"
    assert out["extreme_role_flip"]["to_role"] == "resistance"


def test_camarilla_r4_breach_role_flip():
    cam = camarilla_from_hlc(7.67, 7.5, 7.6)
    out = attach_nearest(
        cam,
        8.0,
        ("S4", "S3", "S2", "S1", "R1", "R2", "R3", "R4"),
        label="Camarilla",
        role_flip_extremes=("S4", "R4"),
    )
    assert out["nearest_resistance"] is None
    assert out["nearest_support"] == cam["R4"]
    assert "并转为支撑" in (out["resistance_note"] or "")
    assert out["extreme_role_flip"]["level"] == "R4"


def test_atr_pivot_keeps_vacuum_wording():
    """非 Camarilla 极端档仍用真空口径，不写角色反转。"""
    levels = {"S2": 9.0, "S1": 9.5, "P": 10.0, "R1": 10.5, "R2": 11.0}
    out = attach_nearest(levels, 8.5, ("S2", "S1", "P", "R1", "R2"), label="ATR-Pivot")
    assert out["support_note"] and "暂无同窗支撑" in out["support_note"]
    assert out["extreme_role_flip"] is None


def test_compute_vol_pivots_camarilla_s4_flip_integrated():
    """端到端：现价跌破 S4 时 Camarilla 走角色反转文案。"""
    parsed = []
    base = date(2025, 1, 1)
    for i in range(18):
        c = 10.0
        parsed.append((base + timedelta(days=i), c + 0.2, c - 0.2, c))
    parsed.append((base + timedelta(days=18), 7.67, 7.5, 7.6))
    parsed.append((base + timedelta(days=19), 7.5, 7.3, 7.44))
    out = compute_vol_pivots_from_parsed(parsed, last_close=7.44, classic_p=7.59)
    cam = out["camarilla"]
    assert cam is not None
    assert cam["nearest_support"] is None
    assert cam["nearest_resistance"] == cam["S4"]
    assert "并转为阻力" in (cam.get("support_note") or "")
