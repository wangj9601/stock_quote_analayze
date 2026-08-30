# -*- coding: utf-8 -*-
"""RS Rating 计算器单测（不依赖数据库）。"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend_core.indicators.rs_rating.calculator import (
    compute_rs_raw,
    percentile_to_rating,
    rank_cross_section,
    roc,
)
from backend_core.indicators.rs_rating.config import PRICE_ADJUST, strength_label
from backend_core.indicators.rs_rating.qfq_closes import apply_qfq_closes


def test_price_adjust_is_qfq():
    assert PRICE_ADJUST == "qfq"


def test_apply_qfq_closes_scale():
    bars = [
        {"date": dt.date(2024, 1, 2), "close": 10.0},
        {"date": dt.date(2024, 1, 3), "close": 12.0},
    ]
    factors = [
        (dt.date(2024, 1, 2), 1.0),
        (dt.date(2024, 1, 3), 2.0),
    ]
    out = apply_qfq_closes(bars, factors)
    assert out is not None
    assert abs(out[0] - 5.0) < 1e-9
    assert abs(out[1] - 12.0) < 1e-9


def test_apply_qfq_closes_no_factor():
    assert apply_qfq_closes([{"date": dt.date(2024, 1, 2), "close": 10.0}], []) is None


def test_roc_basic():
    closes = [100.0] + [100.0] * 62 + [110.0]
    assert len(closes) == 64
    r = roc(closes, 63)
    assert r is not None
    assert abs(r - 0.1) < 1e-9


def test_roc_insufficient():
    assert roc([1.0, 2.0], 63) is None


def test_compute_rs_raw_weights():
    n = 253
    closes = [1.0] * n
    closes[-(63 + 1)] = 0.5
    out = compute_rs_raw(closes)
    assert out is not None
    assert abs(out["roc_63"] - 1.0) < 1e-9
    assert abs(out["roc_126"]) < 1e-9
    assert abs(out["rs_raw"] - 0.4) < 1e-9


def test_percentile_to_rating_bounds():
    assert percentile_to_rating(0.0) == 1
    assert percentile_to_rating(1.0) == 99
    assert percentile_to_rating(0.5) == 50
    assert percentile_to_rating(None) is None


def test_rank_cross_section_and_ties():
    rows = [
        {"code": "a", "rs_raw": 0.1},
        {"code": "b", "rs_raw": 0.3},
        {"code": "c", "rs_raw": 0.3},
        {"code": "d", "rs_raw": 0.9},
    ]
    ranked = rank_cross_section(rows, publish_ratings=True)
    by_code = {r["code"]: r for r in ranked}
    assert by_code["a"]["rs_rating"] == 1
    assert by_code["d"]["rs_rating"] == 99
    assert by_code["b"]["rs_rating"] == by_code["c"]["rs_rating"]
    assert by_code["b"]["percentile"] == by_code["c"]["percentile"]


def test_rank_unpublished():
    rows = [{"code": "a", "rs_raw": 1.0}, {"code": "b", "rs_raw": 2.0}]
    ranked = rank_cross_section(rows, publish_ratings=False)
    assert all(r["rs_rating"] is None for r in ranked)
    assert ranked[0]["percentile"] is not None


def test_strength_label():
    assert strength_label(95) == "很强"
    assert strength_label(75) == "偏强"
    assert strength_label(55) == "中性"
    assert strength_label(40) == "偏弱"
    assert strength_label(10) == "很弱"
    assert strength_label(None) is None


if __name__ == "__main__":
    test_price_adjust_is_qfq()
    test_apply_qfq_closes_scale()
    test_apply_qfq_closes_no_factor()
    test_roc_basic()
    test_roc_insufficient()
    test_compute_rs_raw_weights()
    test_percentile_to_rating_bounds()
    test_rank_cross_section_and_ties()
    test_rank_unpublished()
    test_strength_label()
    print("ok")
