# -*- coding: utf-8 -*-
"""GMS 已收盘周判定（Q20=A，覆盖周五休市）。"""

from backend_core.strategies.gms.week_calendar import (
    friday_label_for_date,
    is_week_closed,
    resolve_closed_week_friday,
)


def test_friday_label_midweek():
    assert friday_label_for_date("2024-05-08") == "2024-05-10"  # Wed -> Fri
    assert friday_label_for_date("2024-05-10") == "2024-05-10"


def test_week_closed_normal_friday():
    # 本周有 Fri 交易
    trade = {"2024-05-06", "2024-05-07", "2024-05-08", "2024-05-09", "2024-05-10"}
    f = "2024-05-10"
    assert is_week_closed(f, "2024-05-09", trade) is False  # 周四，周五还有交易
    assert is_week_closed(f, "2024-05-10", trade) is True


def test_week_closed_friday_holiday():
    # 周五休市：最后交易日周四
    trade = {"2024-05-06", "2024-05-07", "2024-05-08", "2024-05-09"}
    f = "2024-05-10"
    assert is_week_closed(f, "2024-05-08", trade) is False  # 周三后还有周四
    assert is_week_closed(f, "2024-05-09", trade) is True  # 周四 EOD 已完备


def test_resolve_closed_week_friday_holiday():
    trade = [
        "2024-04-29",
        "2024-04-30",
        "2024-05-06",
        "2024-05-07",
        "2024-05-08",
        "2024-05-09",
    ]
    candidates = ["2024-05-03", "2024-05-10"]
    # 周四 as_of：本周 F=05-10 已收盘
    assert (
        resolve_closed_week_friday(
            "2024-05-09", trade, candidate_fridays=candidates
        )
        == "2024-05-10"
    )


def test_trace_floor_default_is_30():
    from backend_core.strategies.gms.frontend_interface import (
        _DEFAULT_TRACE_STORAGE_MIN_SCORE,
        _passes_gms_trace_storage_floor,
        resolve_gms_trace_storage_min_score,
    )

    assert _DEFAULT_TRACE_STORAGE_MIN_SCORE == 30.0
    assert resolve_gms_trace_storage_min_score() == 30.0
    assert _passes_gms_trace_storage_floor({"score_total": 30}) is True
    assert _passes_gms_trace_storage_floor({"score_total": 29.9}) is False
    assert _passes_gms_trace_storage_floor({"score_total": None}) is False
