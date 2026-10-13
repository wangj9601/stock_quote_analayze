# -*- coding: utf-8 -*-
"""CSB 回测优化：PROBE 止损缓冲、入场过滤、量能导出、预设。"""

from __future__ import annotations

from backend_core.strategies.csb.backtest_factor_report import flatten_score_factors
from backend_core.strategies.csb.backtest_presets import apply_backtest_preset, list_backtest_presets
from backend_core.strategies.csb.backtest_runner import filter_backtest_signals
from backend_core.strategies.csb.config import CSB_BREAKOUT, CSB_LPS, CSB_PROBE, get_default_csb_config
from backend_core.strategies.csb.defense_exit import evaluate_structure_exit_rules


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


def test_probe_baseline_stop_needs_confirm_with_buffer():
    cfg = get_default_csb_config()
    # entry_low=10，缓冲 1% → 止损线 9.9；单日收 9.85 未达连续确认
    after = [
        _bar("2024-06-01", 10.2, 10.5, 10.0, 10.4),
        _bar("2024-06-02", 10.0, 10.1, 9.8, 9.85),
    ]
    r = evaluate_structure_exit_rules(
        entry_price=10.4,
        entry_low=10.0,
        channel_upper=None,
        bars_after_entry=after,
        signal_date="2024-06-01",
        config=cfg,
        signal_type=CSB_PROBE,
        channel_lower=9.0,
    )
    assert r.get("exit_reason") != "baseline_stop"

    after2 = after + [_bar("2024-06-03", 9.8, 9.9, 9.7, 9.82)]
    r2 = evaluate_structure_exit_rules(
        entry_price=10.4,
        entry_low=10.0,
        channel_upper=None,
        bars_after_entry=after2,
        signal_date="2024-06-01",
        config=cfg,
        signal_type=CSB_PROBE,
        channel_lower=9.0,
    )
    assert r2.get("exit_reason") == "baseline_stop"


def test_breakout_baseline_stop_still_immediate():
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
        signal_type=CSB_BREAKOUT,
    )
    assert r.get("exit_reason") == "baseline_stop"


def test_filter_backtest_signals_probe_rules():
    cfg = get_default_csb_config()
    cfg.setdefault("backtest", {})["min_touch_count"] = 3
    cfg["backtest"]["probe_min_score"] = 80
    cfg["backtest"]["allowed_signal_types"] = [CSB_PROBE, CSB_BREAKOUT, CSB_LPS]
    signals = [
        {"code": "1", "signal_type": CSB_PROBE, "score": 85, "touch_count": 4},
        {"code": "2", "signal_type": CSB_PROBE, "score": 70, "touch_count": 4},
        {"code": "3", "signal_type": CSB_PROBE, "score": 90, "touch_count": 2},
        {"code": "4", "signal_type": CSB_BREAKOUT, "score": 70, "touch_count": 1},
        {"code": "5", "signal_type": CSB_LPS, "score": 75, "touch_count": 2},
    ]
    out = filter_backtest_signals(signals, cfg)
    codes = {s["code"] for s in out}
    assert codes == {"1", "4", "5"}


def test_filter_max_signals_per_day():
    cfg = get_default_csb_config()
    cfg.setdefault("backtest", {})["max_signals_per_day"] = 2
    signals = [
        {"code": "a", "score": 90, "signal_type": CSB_PROBE, "touch_count": 3},
        {"code": "b", "score": 80, "signal_type": CSB_PROBE, "touch_count": 3},
        {"code": "c", "score": 70, "signal_type": CSB_PROBE, "touch_count": 3},
    ]
    out = filter_backtest_signals(signals, cfg)
    assert len(out) == 2
    assert out[0]["code"] == "a"
    assert out[1]["code"] == "b"


def test_flatten_fills_vol_ratio_for_probe():
    sig = {
        "signal_type": CSB_PROBE,
        "vol_expand_mult": None,
        "vol_ratio_5_20": 0.73,
        "touch_count": 3,
        "detail": {"entry": {"vol_ratio_5_20": 0.73}},
    }
    flat = flatten_score_factors(sig)
    assert flat.get("vol_ratio_5_20") == 0.73
    # PROBE 无放量倍数时，用 5/20 量比回填便于分桶
    assert flat.get("vol_expand_mult") == 0.73


def test_presets_exist_and_apply():
    names = {p["id"] for p in list_backtest_presets()}
    assert "optimized_probe" in names
    assert "breakout_lps_only" in names
    assert "hit_rate_probe" in names
    assert "structure_v2" in names
    body = {"exit_mode": "hit_rate", "target_pct": 0.10, "min_score": 60}
    applied = apply_backtest_preset("optimized_probe", body)
    assert applied["exit_mode"] == "structure_exit"
    assert abs(float(applied["target_pct"]) - 0.05) < 1e-9
    assert float(applied["min_score"]) >= 80
    assert applied.get("min_touch_count") == 3
    assert CSB_PROBE in (applied.get("allowed_signal_types") or [])

    v2 = apply_backtest_preset("structure_v2", body)
    assert v2["exit_mode"] == "structure_exit"
    assert abs(float(v2["target_pct"]) - 0.05) < 1e-9
    assert v2.get("min_touch_count") == 3
    overrides = v2.get("defense_overrides") or {}
    assert abs(float(overrides.get("channel_fail_buffer_pct")) - 0.015) < 1e-9
    assert int(overrides.get("channel_fail_confirm_days")) == 3
