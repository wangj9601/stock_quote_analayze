# -*- coding: utf-8 -*-
"""板块入场闸门单元测试（纯逻辑，不连库）。"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_core.board_gates.config import GATE_ALLOC, GATE_AVOID, GATE_WATCH, RAW_ALLOC, RAW_AVOID, RAW_WATCH
from backend_core.board_gates.evaluate import evaluate_midlong_raw, evaluate_short_raw
from backend_core.board_gates.fund_features import classify_fund_stage, compute_streaks_and_sums
from backend_core.board_gates.sticky import apply_sticky, conflict_action


def test_fund_streaks():
    feat = compute_streaks_and_sums([1, 2, -1, 3, 4, 5])
    assert feat["inflow_streak"] == 3
    assert feat["outflow_streak"] == 0
    assert feat["day_net"] == 5
    assert feat["pos_days_5"] == 4
    assert feat["net_sum_5"] == 13


def test_fund_stage_markup():
    feat = {"inflow_streak": 2, "outflow_streak": 0, "net_sum_20": 100}
    assert classify_fund_stage(feat, short_strong=True, mid_weak=False) == "markup"


def test_sticky_needs_confirm():
    state, cnt = apply_sticky(RAW_ALLOC, [], confirm_days=2)
    assert state == GATE_WATCH
    state2, _ = apply_sticky(RAW_ALLOC, [RAW_ALLOC], confirm_days=2)
    assert state2 == GATE_ALLOC
    state3, _ = apply_sticky(RAW_AVOID, [RAW_AVOID], confirm_days=2)
    assert state3 == GATE_AVOID


def test_short_alloc_two_ends():
    raw, ev, _ = evaluate_short_raw(
        board_kind="industry",
        env5="strong",
        slope5=0.003,
        env10="neutral",
        slope10=0.0,
        day_net=1e8,
        net_sum_5=1e8,
        inflow_streak=2,
        pos_days_5=3,
        sentiment_ok=True,
        v2=True,
    )
    assert raw == RAW_ALLOC
    assert ev["price_ok"] and ev["volume_ok"] and ev["sentiment_ok"]


def test_short_no_fund_blocks_alloc():
    raw, _, deg = evaluate_short_raw(
        board_kind="concept",
        env5="strong",
        slope5=0.003,
        env10="strong",
        slope10=0.002,
        day_net=None,
        net_sum_5=None,
        sentiment_ok=True,
        v2=True,
    )
    assert raw == RAW_WATCH
    assert "short_fund_missing" in deg


def test_midlong_needs_rs_v2():
    raw, _, deg = evaluate_midlong_raw(
        env60="strong",
        slope60=0.002,
        env120="strong",
        slope120=0.001,
        slope_source_60="ths_index",
        net_sum_20=1e9,
        board_trend_label="全面走强",
        fund_stage="markup",
        inflow_streak=3,
        pos_days_20=10,
        board_rs=None,
        valuation_unknown=True,
        v2=True,
    )
    assert raw == RAW_WATCH
    assert "midlong_board_rs_missing" in deg


def test_midlong_alloc_full_v2():
    raw, _, _ = evaluate_midlong_raw(
        env60="strong",
        slope60=0.002,
        env120="neutral",
        slope120=0.0005,
        slope_source_60="ths_index",
        net_sum_20=1e9,
        board_trend_label="中强短修",
        fund_stage="markup",
        inflow_streak=3,
        pos_days_20=10,
        board_rs=75,
        pe_pct=0.5,
        pb_pct=0.5,
        valuation_unknown=False,
        v2=True,
    )
    assert raw == RAW_ALLOC


def test_midlong_block_long_weak_short_strong():
    raw, ev, _ = evaluate_midlong_raw(
        env60="strong",
        slope60=0.002,
        env120="strong",
        slope120=0.001,
        slope_source_60="ths_index",
        net_sum_20=1e9,
        board_trend_label="长弱短强",
        fund_stage="markup",
        inflow_streak=3,
        pos_days_20=10,
        board_rs=80,
        valuation_unknown=True,
        v2=True,
    )
    assert raw == RAW_WATCH
    assert ev.get("trend_block") is True


def test_conflict_actions():
    assert conflict_action(GATE_ALLOC, GATE_AVOID) == "hold_no_new"
    assert conflict_action(GATE_AVOID, GATE_ALLOC) == "ultrashort_only"


if __name__ == "__main__":
    test_fund_streaks()
    test_fund_stage_markup()
    test_sticky_needs_confirm()
    test_short_alloc_two_ends()
    test_short_no_fund_blocks_alloc()
    test_midlong_needs_rs_v2()
    test_midlong_alloc_full_v2()
    test_midlong_block_long_weak_short_strong()
    test_conflict_actions()
    print("ok")
