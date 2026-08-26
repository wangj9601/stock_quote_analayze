"""URT 回测详情：交易逻辑与风控参数元数据。"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_core.strategies.urt.backtest_runner import build_urt_trade_meta


def test_build_urt_trade_meta_defaults():
    meta = build_urt_trade_meta()
    risk = meta["risk_params"]
    logic = meta["trade_logic"]
    assert risk["stop_loss_pct_max"] == 10
    assert risk["time_stop_down_days"] == 3
    assert risk["time_stop_min_loss_pct"] == 4.0
    assert risk["take_profit_alert_pct_min"] == 8
    assert risk["trailing_drawdown_pct"] == 5
    assert "观察期 10" in logic["summary"]
    assert any("开盘价" in r for r in logic["rules"])
    codes = [x["code"] for x in logic["exit_priority"]]
    assert codes == ["target_hit"]


def test_build_urt_trade_meta_custom_risk():
    meta = build_urt_trade_meta(
        target_pct=0.15,
        horizon_days=30,
        min_score=80,
        risk={
            "stop_loss_pct_max": 8,
            "time_stop_down_days": 2,
            "take_profit_alert_pct_min": 20,
            "trailing_drawdown_pct": 6,
        },
    )
    assert meta["risk_params"]["stop_loss_pct_max"] == 8
    assert "30" in meta["trade_logic"]["summary"]
    assert "80" in meta["trade_logic"]["summary"]
    assert any("8%" in r for r in meta["trade_logic"]["rules"])


def test_build_urt_trade_meta_target_range():
    meta = build_urt_trade_meta(target_pct=0.05, target_pct_max=0.08, horizon_days=10)
    summary = meta["trade_logic"]["summary"]
    assert "5.0%～8.0%" in summary
    joined = " ".join(meta["trade_logic"]["rules"])
    assert "5.0%～8.0%" in joined
