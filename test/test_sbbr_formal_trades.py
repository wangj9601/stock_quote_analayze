"""SBBR 正式交易仓位规则单测。"""

from backend_core.strategies.sbbr.config import get_default_sbbr_config
from backend_core.strategies.sbbr.position_advisor import advise_position


def test_cannot_exceed_max_positions():
    cfg = get_default_sbbr_config()
    r = advise_position(
        current_stage=None,
        allocated_pct=0,
        open_positions=3,
        total_capital=5_000_000,
        has_new_support=True,
        config=cfg,
    )
    assert r["next_action"] == "blocked"
    assert r["can_open"] is False


def test_reserve_cash_message_after_add():
    cfg = get_default_sbbr_config()
    r = advise_position(
        current_stage="add",
        allocated_pct=80,
        open_positions=1,
        total_capital=5_000_000,
        has_new_support=True,
        config=cfg,
    )
    assert r["next_action"] == "hold_reserve"
    assert r["max_allocated_pct"] == 80.0
