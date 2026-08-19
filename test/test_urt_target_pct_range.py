"""URT 回测目标涨幅区间：解析、命中判定与文案。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_core.strategies.urt.backtest_pdf import _format_target_pct_range, _target_range_open
from backend_core.strategies.urt.backtest_runner import (
    build_urt_trade_meta,
    classify_target_hits,
    format_target_pct_range_label,
    resolve_target_pct_range,
)
from backend_core.strategies.urt.backtest_storage import _build_urt_details_csv_bytes


def test_resolve_defaults_equal_10_percent():
    assert resolve_target_pct_range() == (0.10, 0.10)
    assert resolve_target_pct_range(0.10, None) == (0.10, 0.10)


def test_resolve_range_and_swap():
    assert resolve_target_pct_range(0.05, 0.08) == (0.05, 0.08)
    lo, hi = resolve_target_pct_range(0.08, 0.05)
    assert lo == 0.05 and hi == 0.08


def test_format_target_pct_range_label():
    assert format_target_pct_range_label(0.10, 0.10) == "10.0%"
    assert format_target_pct_range_label(0.05, 0.08) == "5.0%～8.0%"


def test_classify_point_target_10():
    hit = classify_target_hits(entry_price=10, max_high=11.0, target_lo=0.10, target_hi=0.10)
    assert hit == {"hit_target": True, "hit_target_upper": True, "hit_in_band": True}
    miss = classify_target_hits(entry_price=10, max_high=10.9, target_lo=0.10, target_hi=0.10)
    assert miss["hit_target"] is False
    assert miss["hit_in_band"] is False


def test_classify_range_5_to_8():
    in_band = classify_target_hits(entry_price=100, max_high=106, target_lo=0.05, target_hi=0.08)
    assert in_band["hit_target"] is True
    assert in_band["hit_target_upper"] is False
    assert in_band["hit_in_band"] is True

    overshoot = classify_target_hits(entry_price=100, max_high=110, target_lo=0.05, target_hi=0.08)
    assert overshoot["hit_target"] is False
    assert overshoot["hit_target_upper"] is True
    assert overshoot["hit_in_band"] is False

    miss = classify_target_hits(entry_price=100, max_high=104, target_lo=0.05, target_hi=0.08)
    assert miss["hit_target"] is False
    assert miss["hit_target_upper"] is False
    assert miss["hit_in_band"] is False


def test_trade_meta_range_text():
    meta = build_urt_trade_meta(target_pct=0.05, target_pct_max=0.08)
    assert "5.0%～8.0%" in meta["trade_logic"]["summary"]
    assert any("区间内" in r or "落在" in r for r in meta["trade_logic"]["rules"])


def test_pdf_target_range_label():
    assert _format_target_pct_range({"target_pct": 0.1}) == "10.0%"
    assert _format_target_pct_range({"target_pct": 0.05, "target_pct_max": 0.08}) == "5.0%～8.0%"
    assert _target_range_open({"target_pct": 0.1}) is False
    assert _target_range_open({"target_pct": 0.05, "target_pct_max": 0.08}) is True


def test_export_includes_range_hit_columns():
    rows = [
        {
            "code": "000001",
            "hit_target": True,
            "hit_target_upper": False,
            "hit_in_band": True,
        }
    ]
    text = _build_urt_details_csv_bytes(rows).decode("utf-8-sig")
    header = text.splitlines()[0]
    assert "是否命中目标" in header
    assert "是否触及上限" in header
    assert "涨幅落在区间内" in header
    body = text.splitlines()[1]
    assert "是" in body
    assert "否" in body
