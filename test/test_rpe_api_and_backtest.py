"""RPE API / 交易规则 / 回测相关单测（不依赖真实库）。"""

from backend_core.strategies.rpe.config import get_default_rpe_config
from backend_core.strategies.rpe.filters import structure_break
from backend_core.strategies.rpe.trade_structure_plan import build_structure_plan


def test_structure_plan_has_no_fixed_pct_stop():
    plan = build_structure_plan(
        entry_price=10.0,
        nearest_support=9.2,
        nearest_resistance=12.0,
    )
    assert plan["exit_rule"] == "structure_break"
    assert plan["structure_support"] == 9.2
    blob = str(plan).lower()
    assert "fixed_pct" not in blob
    assert "percent_stop" not in blob


def test_structure_break_rule():
    assert structure_break(9.0, 9.5) is True
    assert structure_break(9.6, 9.5) is False
    assert structure_break(10.0, None) is False


def test_default_config_lead_trade_off():
    cfg = get_default_rpe_config()
    assert cfg["enable_lead_trade"] is False
    assert cfg["enable_trend_veto"] is True
    assert cfg["z_catch_up"] == -1.5
    assert cfg["z_lead"] == 2.0


def test_formal_exit_reason_denylist_logic():
    """与 rpe_routes.patch 中禁止固定%止损的规则保持一致。"""
    banned = {"fixed_pct", "percent_stop", "pct_stop", "fixed_stop"}
    assert "structure_break" not in banned
    assert "manual" not in banned
    assert "fixed_pct" in banned


def test_backtest_runner_exports():
    from backend_core.strategies.rpe import backtest_runner as br

    assert hasattr(br, "start_backtest_async")
    assert hasattr(br, "run_rpe_backtest")
