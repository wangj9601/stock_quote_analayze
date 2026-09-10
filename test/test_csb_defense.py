# -*- coding: utf-8 -*-
"""CSB 假突破与入口检测边界单测。"""

from backend_core.strategies.csb.config import get_default_csb_config
from backend_core.strategies.csb.defense_exit import check_false_break, evaluate_structure_exit_rules


def _bar(date: str, o: float, h: float, l: float, c: float, vol: float = 1e6) -> dict:
    return {
        "date": date,
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "volume": vol,
        "turnover_rate": 2.0,
    }


def test_false_break_triggers_when_close_below_upper():
    bars = [
        _bar("2024-06-01", 10, 10.5, 9.9, 10.4),
        _bar("2024-06-02", 10.4, 10.6, 9.5, 9.6),  # 收盘跌破上轨 10.0
        _bar("2024-06-03", 9.6, 9.8, 9.4, 9.7),
        _bar("2024-06-04", 9.7, 9.9, 9.5, 9.8),
    ]
    r = check_false_break(
        bars,
        breakout_date="2024-06-01",
        channel_upper=10.0,
        false_break_days=3,
    )
    assert r.get("false_break") is True


def test_false_break_ok_when_holds_above():
    bars = [
        _bar("2024-06-01", 10, 10.5, 9.9, 10.4),
        _bar("2024-06-02", 10.4, 10.8, 10.1, 10.5),
        _bar("2024-06-03", 10.5, 10.9, 10.2, 10.6),
        _bar("2024-06-04", 10.6, 11.0, 10.3, 10.7),
    ]
    r = check_false_break(
        bars,
        breakout_date="2024-06-01",
        channel_upper=10.0,
        false_break_days=3,
    )
    assert r.get("false_break") is not True


def test_structure_exit_baseline_stop():
    cfg = get_default_csb_config()
    after = [
        _bar("2024-06-01", 10.0, 10.5, 9.9, 10.4),
        _bar("2024-06-02", 10.2, 10.3, 9.0, 9.1),
    ]
    r = evaluate_structure_exit_rules(
        entry_price=10.4,
        entry_low=9.8,
        channel_upper=None,  # 跳过假突破，只测基准止损
        bars_after_entry=after,
        signal_date="2024-06-01",
        config=cfg,
    )
    assert r.get("exit_reason") == "baseline_stop"
