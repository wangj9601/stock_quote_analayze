# -*- coding: utf-8 -*-
from datetime import date, timedelta

from backend_core.analysis.pivot_variants import (
    atr_pivot_bands,
    camarilla_from_hlc,
    compute_vol_pivots_from_parsed,
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
