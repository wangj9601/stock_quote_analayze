# -*- coding: utf-8 -*-
"""默认参数基线：出场 v3 + 分≥80 + 利润保护。"""

from backend_core.strategies.csb.config import CSBConfigManager, get_default_csb_config


def test_factory_default_is_v3_baseline():
    cfg = get_default_csb_config()
    assert float(cfg["min_score"]) == 80.0
    d = cfg["defense"]
    assert abs(float(d["probe_stop_buffer_pct"]) - 0.02) < 1e-9
    assert int(d["probe_stop_confirm_days"]) == 3
    assert abs(float(d["channel_fail_buffer_pct"]) - 0.015) < 1e-9
    assert int(d["channel_fail_confirm_days"]) == 3
    assert abs(float(d["profit_lock_gain"]) - 0.10) < 1e-9


def test_runtime_upgrades_old_factory_values():
    mgr = CSBConfigManager()
    old = {
        "min_score": 60.0,
        "defense": {
            "probe_stop_buffer_pct": 0.01,
            "probe_stop_confirm_days": 2,
            "channel_fail_buffer_pct": 0.005,
            "channel_fail_confirm_days": 2,
        },
    }
    merged = mgr._apply_v2_runtime(mgr._deep_merge(mgr.get_default_config(), old))
    assert float(merged["min_score"]) == 80.0
    d = merged["defense"]
    assert abs(float(d["probe_stop_buffer_pct"]) - 0.02) < 1e-9
    assert int(d["probe_stop_confirm_days"]) == 3
    assert abs(float(d["channel_fail_buffer_pct"]) - 0.015) < 1e-9
    assert int(d["channel_fail_confirm_days"]) == 3


def test_runtime_keeps_custom_min_score():
    mgr = CSBConfigManager()
    custom = mgr._apply_v2_runtime(
        mgr._deep_merge(mgr.get_default_config(), {"min_score": 72.0, "defense": {"probe_stop_buffer_pct": 0.03}})
    )
    assert float(custom["min_score"]) == 72.0
    assert abs(float(custom["defense"]["probe_stop_buffer_pct"]) - 0.03) < 1e-9
