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


def test_baseline_stop_has_no_buffer():
    cfg = get_default_csb_config()
    after = [
        _bar("2024-06-01", 10.2, 10.5, 10.0, 10.4),
        _bar("2024-06-02", 10.3, 10.4, 9.9, 9.95),
    ]
    r = evaluate_structure_exit_rules(
        entry_price=10.4,
        entry_low=10.0,
        channel_upper=None,
        bars_after_entry=after,
        signal_date="2024-06-01",
        config=cfg,
    )
    assert r.get("exit_reason") == "baseline_stop"


def test_distribution_stall_after_rally():
    cfg = get_default_csb_config()
    prior = [_bar(f"2024-05-{i+1:02d}", 10, 10.2, 9.8, 10.0, vol=1_000_000) for i in range(20)]
    for b in prior:
        b["turnover_rate"] = 1.5
    after = [
        _bar("2024-06-01", 10.2, 10.6, 10.1, 10.5, vol=1_200_000),
        _bar("2024-06-02", 10.8, 11.5, 10.7, 11.3, vol=1_200_000),
        # 涨幅已超过 8%，高换手但实体极小、长上影
        _bar("2024-06-03", 11.28, 11.90, 11.2, 11.30, vol=4_000_000),
    ]
    after[-1]["turnover_rate"] = 6.0
    r = evaluate_structure_exit_rules(
        entry_price=10.0,
        entry_low=9.5,
        channel_upper=None,
        bars_after_entry=after,
        signal_date="2024-05-31",
        config=cfg,
        prior_bars=prior,
    )
    assert r.get("exit_reason") == "distribution"
    assert r.get("distribution_kind") == "stall"


def test_trail_ratchet_uses_ma_after_gain():
    cfg = get_default_csb_config()
    prior = [_bar(f"2024-05-{i+1:02d}", 10, 10.2, 9.9, 10.0, vol=1_000_000) for i in range(25)]
    after = [_bar("2024-06-01", 10.1, 10.4, 10.0, 10.3, vol=1_000_000)]
    px = 10.3
    for i in range(2, 8):
        px += 0.15
        after.append(_bar(f"2024-06-{i:02d}", px - 0.05, px + 0.1, px - 0.08, px, vol=1_000_000))
    # 收盘跌回阶梯线之下，但仍高于基准止损
    after.append(_bar("2024-06-08", 10.6, 10.7, 10.3, 10.4, vol=1_000_000))
    r = evaluate_structure_exit_rules(
        entry_price=10.2,
        entry_low=9.0,
        channel_upper=None,
        bars_after_entry=after,
        signal_date="2024-05-31",
        config=cfg,
        prior_bars=prior,
    )
    assert r.get("exit_reason") == "ma_trail"


def test_false_break_only_for_breakout_not_probe():
    """PROBE 收盘落回上轨之下不应判假突破；同价序列对 BREAKOUT 应判假突破。"""
    cfg = get_default_csb_config()
    after = [
        _bar("2024-06-01", 9.8, 10.1, 9.7, 9.95),  # 信号日：PROBE 在通道内
        _bar("2024-06-02", 9.9, 10.0, 9.6, 9.7),  # 收盘 < 上轨 10.0
        _bar("2024-06-03", 9.7, 9.9, 9.5, 9.8),
        _bar("2024-06-04", 9.8, 10.0, 9.6, 9.85),
    ]
    probe = evaluate_structure_exit_rules(
        entry_price=9.95,
        entry_low=9.5,
        channel_upper=10.0,
        bars_after_entry=after,
        signal_date="2024-06-01",
        config=cfg,
        signal_type="CSB_PROBE",
        channel_lower=9.0,
    )
    assert probe.get("exit_reason") != "false_break"

    breakout = evaluate_structure_exit_rules(
        entry_price=10.4,
        entry_low=9.9,
        channel_upper=10.0,
        bars_after_entry=[
            _bar("2024-06-01", 10.0, 10.5, 9.9, 10.4),
            _bar("2024-06-02", 10.4, 10.6, 9.5, 9.6),
            _bar("2024-06-03", 9.6, 9.8, 9.4, 9.7),
        ],
        signal_date="2024-06-01",
        config=cfg,
        signal_type="CSB_BREAKOUT",
    )
    assert breakout.get("exit_reason") == "false_break"


def test_probe_channel_fail_needs_confirm_days():
    """PROBE：连续 3 日收盘跌破「下轨×(1-缓冲)」才 channel_fail。"""
    cfg = get_default_csb_config()
    # 下轨 9.0 × 0.985 = 8.865
    after = [
        _bar("2024-06-01", 9.8, 10.0, 9.7, 9.9),
        _bar("2024-06-02", 9.9, 10.0, 9.6, 9.85),
        _bar("2024-06-03", 9.8, 9.9, 8.8, 8.80),  # 第 1 日破地板，尚不离场
        _bar("2024-06-04", 8.9, 9.0, 8.7, 8.75),  # 第 2 日，尚不离场
        _bar("2024-06-05", 8.8, 8.9, 8.6, 8.70),  # 第 3 日确认
    ]
    r = evaluate_structure_exit_rules(
        entry_price=9.9,
        entry_low=8.5,
        channel_upper=10.0,
        bars_after_entry=after,
        signal_date="2024-06-01",
        config=cfg,
        signal_type="CSB_PROBE",
        channel_lower=9.0,
    )
    assert r.get("exit_reason") == "channel_fail"
    assert r.get("exit_date") == "2024-06-05"


def test_probe_single_day_pierce_does_not_channel_fail():
    """单日刺穿下轨后收回 → 不算通道失效。"""
    cfg = get_default_csb_config()
    after = [
        _bar("2024-06-01", 9.8, 10.0, 9.7, 9.9),
        _bar("2024-06-02", 9.8, 9.9, 8.8, 8.90),  # 刺穿
        _bar("2024-06-03", 9.0, 9.3, 8.95, 9.20),  # 收回，打断连续
        _bar("2024-06-04", 9.2, 9.4, 9.1, 9.30),
    ]
    r = evaluate_structure_exit_rules(
        entry_price=9.9,
        entry_low=8.5,
        channel_upper=10.0,
        bars_after_entry=after,
        signal_date="2024-06-01",
        config=cfg,
        signal_type="CSB_PROBE",
        channel_lower=9.0,
    )
    assert r.get("exit_reason") != "channel_fail"


def test_probe_channel_fail_buffer_ignores_shallow_dip():
    """收盘略低于名义下轨但仍在缓冲带内 → 不累计失效。"""
    cfg = get_default_csb_config()
    # 下轨 9.0，缓冲后地板 8.865；9.0~8.90 之间的浅跌不触发
    after = [
        _bar("2024-06-01", 9.8, 10.0, 9.7, 9.9),
        _bar("2024-06-02", 9.9, 10.0, 8.97, 8.97),
        _bar("2024-06-03", 8.97, 9.1, 8.90, 8.90),
        _bar("2024-06-04", 8.90, 9.2, 8.88, 9.10),
    ]
    r = evaluate_structure_exit_rules(
        entry_price=9.9,
        entry_low=8.5,
        channel_upper=10.0,
        bars_after_entry=after,
        signal_date="2024-06-01",
        config=cfg,
        signal_type="CSB_PROBE",
        channel_lower=9.0,
    )
    assert r.get("exit_reason") != "channel_fail"


def test_lps_skips_false_break():
    """LPS 回踩上轨附近，收盘略低于上轨不应判假突破。"""
    cfg = get_default_csb_config()
    after = [
        _bar("2024-06-01", 10.1, 10.3, 9.95, 10.05),
        _bar("2024-06-02", 10.0, 10.2, 9.9, 9.95),  # < upper 10.0
        _bar("2024-06-03", 9.95, 10.1, 9.9, 10.0),
        _bar("2024-06-04", 10.0, 10.2, 9.95, 10.1),
    ]
    r = evaluate_structure_exit_rules(
        entry_price=10.05,
        entry_low=9.8,
        channel_upper=10.0,
        bars_after_entry=after,
        signal_date="2024-06-01",
        config=cfg,
        signal_type="CSB_LPS",
    )
    assert r.get("exit_reason") != "false_break"
