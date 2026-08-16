# -*- coding: utf-8 -*-
"""URT 均线多头前缀链分档计分单测。"""

from __future__ import annotations

from backend_core.strategies.urt.config import URTConfigManager
from backend_core.strategies.urt.indicators import (
    build_indicators,
    hard_filter_pass,
    ma_bull_prefix_depth,
    min_bars_needed,
    normalize_ma_bull_periods,
    normalize_ma_bull_score_periods,
    recommended_bars_for_ma_score,
)
from backend_core.strategies.urt.scoring import _ma_bull_tier_score, compute_score_breakdown


def _base_ind(**overrides):
    ind = {
        "above_ma20": True,
        "yang_count_4": 3,
        "yang_count_5": 4,
        "volume_multiple": 3.0,
        "yang_medium_ok": True,
        "yang_medium_detail": [
            {"window": 10, "min_up_days": 6, "count": 6},
            {"window": 15, "min_up_days": 8, "count": 8},
            {"window": 20, "min_up_days": 10, "count": 10},
        ],
        "ma_bull_ok": True,
        "ma_bear_ok": False,
        "ma_bull_periods": [5, 10, 20],
        "ma_bull_values": [12.0, 11.0, 10.0],
        "ma_bull_score_periods": [5, 10, 20, 30, 60, 120, 250],
        "ma_bull_score_values": [12.0, 11.0, 10.0, 9.5, 9.0, 8.5, 8.0],
        "ma_bull_depth": 6,
        "ma5": 12.0,
        "ma10": 11.0,
        "ma20_stack": 10.0,
        "turnover_rate": None,
        "volume_ratio": None,
    }
    ind.update(overrides)
    return ind


def test_normalize_score_periods_default():
    cfg = URTConfigManager().get_default_config()
    assert normalize_ma_bull_periods(cfg) == [5, 10, 20]
    assert normalize_ma_bull_score_periods(cfg) == [5, 10, 20, 30, 60, 120, 250]
    assert recommended_bars_for_ma_score(cfg) >= 250
    # 硬筛门槛不因 250 抬高
    assert min_bars_needed(cfg) < 250


def test_prefix_depth_helpers():
    assert ma_bull_prefix_depth([12, 11, 10, 9, 8, 7, 6]) == 6
    assert ma_bull_prefix_depth([12, 11, 10, 10.5, 8, 7, 6]) == 2
    assert ma_bull_prefix_depth([12, 11, None, 9]) == 1
    assert ma_bull_prefix_depth([10, 11, 12]) == 0


def test_tier_score_depth_2_and_6():
    cfg = URTConfigManager().get_default_config()
    # 深度 2：短多基线 → +4
    part, meta = _ma_bull_tier_score(
        _base_ind(
            ma_bull_depth=2,
            ma_bull_score_values=[12, 11, 10, 10.5, 11, 12, 13],
        ),
        cfg,
    )
    assert part == 4.0
    assert meta["max"] == 10
    assert meta["depth"] == 2
    assert meta["tip_period"] == 20

    part6, meta6 = _ma_bull_tier_score(_base_ind(ma_bull_depth=6), cfg)
    assert part6 == 10.0
    assert meta6["depth"] == 6
    assert meta6["tip_period"] == 250


def test_tier_score_bear_minus_8():
    cfg = URTConfigManager().get_default_config()
    part, meta = _ma_bull_tier_score(
        _base_ind(
            ma_bull_ok=False,
            ma_bear_ok=True,
            ma_bull_depth=0,
            ma_bull_score_values=[8, 9, 10, 11, 12, 13, 14],
        ),
        cfg,
    )
    assert part == -8.0
    assert meta["bear_ok"] is True


def test_hard_filter_still_only_5_10_20():
    """长均线空头不影响硬筛：仅看 ma_bull_periods。"""
    cfg = URTConfigManager().merge_overrides(
        None,
        use_yang_medium=False,
        require_ma_bull=True,
        volume_multiple=1.0,
        use_turnover=False,
        turnover_hard_filter=False,
        structure_rr_hard_gate_enabled=False,
        overheat_hard_gate_enabled=False,
    )
    # 构造严格升序收盘 → 短多；用足够根数算出长均线
    n = 260
    bars = []
    for i in range(n):
        # i=0 最新；价格随时间上升 → 短均 > 长均
        c = 10.0 + (n - 1 - i) * 0.05
        bars.append(
            {
                "date": f"2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
                "open": c - 0.1,
                "close": c,
                "high": c + 0.2,
                "low": c - 0.2,
                "volume": 3000.0 if i == 0 else 1000.0,
                "turnover_rate": 5.0,
            }
        )
    ind = build_indicators(bars, cfg)
    assert ind is not None
    assert ind["ma_bull_periods"] == [5, 10, 20]
    assert ind["ma_bull_ok"] is True
    assert ind.get("ma_bull_depth", 0) >= 2
    ok, reason = hard_filter_pass(ind, cfg)
    assert ok is True, reason

    total, detail = compute_score_breakdown(ind, cfg)
    assert detail["parts"]["ma_bull"]["max"] == 10
    assert detail["parts"]["ma_bull"]["score"] >= 4.0
    assert total <= 100.0


def test_short_history_depth_truncates_not_fail():
    cfg = URTConfigManager().merge_overrides(
        None,
        use_yang_medium=False,
        require_ma_bull=False,
        volume_multiple=1.0,
        use_turnover=False,
        turnover_hard_filter=False,
    )
    n = 40
    bars = []
    for i in range(n):
        c = 10.0 + (n - 1 - i) * 0.08
        bars.append(
            {
                "date": f"2024-01-{(i % 28) + 1:02d}",
                "open": c - 0.05,
                "close": c,
                "high": c + 0.1,
                "low": c - 0.1,
                "volume": 2000.0 if i == 0 else 800.0,
                "turnover_rate": 4.0,
            }
        )
    ind = build_indicators(bars, cfg)
    assert ind is not None
    vals = ind.get("ma_bull_score_values") or []
    assert vals[-1] is None  # MA250 算不出
    assert ind["ma_bull_depth"] < 6
    _, detail = compute_score_breakdown(ind, cfg)
    assert detail["parts"]["ma_bull"]["max"] == 10
