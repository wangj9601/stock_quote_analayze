# -*- coding: utf-8 -*-
"""URT risk_exit 回测元数据与离场接入。"""

from backend_core.strategies.urt.backtest_runner import build_urt_trade_meta
from backend_core.strategies.urt.config import URTConfigManager
from backend_core.strategies.urt.signal_detector import evaluate_exit_rules


def test_build_urt_trade_meta_risk_exit_mode():
    meta = build_urt_trade_meta(exit_mode="risk_exit", horizon_days=20, target_pct=0.1)
    assert meta["risk_params"]["exit_mode"] == "risk_exit"
    codes = {x["code"] for x in meta["trade_logic"]["exit_priority"]}
    assert "price_stop" in codes
    assert "horizon_end" in codes


def test_build_urt_trade_meta_hit_rate_default():
    meta = build_urt_trade_meta()
    assert meta["risk_params"]["exit_mode"] == "hit_rate"
    assert "不止损" in meta["trade_logic"]["summary"]


def test_evaluate_exit_rules_price_stop_triggers():
    cfg = URTConfigManager().get_default_config()
    out = evaluate_exit_rules(
        entry_price=100.0,
        closes=[100.0, 95.0, 89.0],
        peak_price=100.0,
        cfg=cfg,
    )
    assert out is not None
    assert out["exit_reason"] == "price_stop"
