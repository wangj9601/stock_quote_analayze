"""
3倍量缩量突破 — 信号落库字段映射（无 DB）
"""

from datetime import date, datetime

import pytest

from backend_core.strategies.volume_shrink_breakout.signal_storage import (
    parse_vsb_signal_date,
    screen_row_to_signal_fields,
)


def test_parse_vsb_signal_date():
    assert parse_vsb_signal_date("2024-06-01") == date(2024, 6, 1)
    assert parse_vsb_signal_date(date(2024, 1, 2)) == date(2024, 1, 2)
    assert parse_vsb_signal_date(datetime(2024, 1, 2, 15, 0, 0)) == date(2024, 1, 2)
    assert parse_vsb_signal_date("") is None
    assert parse_vsb_signal_date("bad") is None


def test_screen_row_to_signal_fields_minimal():
    row = {
        "code": "600000",
        "name": "浦发银行",
        "breakout_date": "2024-05-10",
        "boom_date": "2024-04-01",
        "boom_close": 10.5,
        "boom_volume": 1000,
        "boom_volume_ratio_vs_prev": 3.2,
        "ma5_at_boom": 10,
        "ma10_at_boom": 9.9,
        "ma20_at_boom": 9.5,
        "breakout_close": 11,
        "breakout_volume": 400,
        "current_change_percent": 1.2,
    }
    params = {"volume_ratio": 3.0, "boom_lookback_min": 5, "boom_lookback_max": 60, "boards": ["CYB"]}
    row["buy_signal"] = "测试买点"
    row["signal_strength"] = 66
    row["signal_strength_level"] = "中"
    row["signal_reminders"] = ["提醒1"]
    f = screen_row_to_signal_fields(row, parameters=params, search_date="2024-05-10")
    assert f is not None
    assert f["code"] == "600000"
    assert f["signal_date"] == date(2024, 5, 10)
    assert f["volume_ratio_param"] == 3.0
    assert "CYB" in f["boards_json"]
    assert f["buy_signal_text"] == "测试买点"
    assert f["signal_strength"] == 66
    assert f["signal_strength_level"] == "中"
    assert "提醒1" in f["signal_reminders_json"]
    row["phase_state"] = {"strategy_phase": "three_phase_v1", "C_limit": 10.5}
    f2 = screen_row_to_signal_fields(row, parameters=params, search_date="2024-05-10")
    assert f2 is not None
    assert "three_phase_v1" in (f2.get("phase_state_json") or "")


def test_screen_row_to_signal_fields_code_zfill():
    f2 = screen_row_to_signal_fields(
        {"code": "12345", "name": "x", "breakout_date": "2024-01-02"},
        parameters={},
        search_date="2024-01-02",
    )
    assert f2["code"] == "012345"


def test_screen_row_to_signal_fields_no_breakout():
    assert (
        screen_row_to_signal_fields(
            {"code": "600000", "name": "n", "breakout_date": None},
            parameters={},
            search_date="2024-01-01",
        )
        is None
    )
