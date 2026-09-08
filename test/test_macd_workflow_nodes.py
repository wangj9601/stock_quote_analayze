"""MACD 日算节点：解析与空列表行为单测（不连外网）。"""

from datetime import date

from backend_core.data_collectors.workflow.adapters import (
    _resolve_macd_trade_date,
    exec_macd_cn,
    exec_macd_hk,
)
from backend_core.data_collectors.workflow.context import WorkflowContext
from backend_core.data_collectors.workflow.node_registry import get_node


def test_macd_nodes_registered():
    cn = get_node("macd_cn")
    hk = get_node("macd_hk")
    assert cn is not None and cn.name == "A股MACD日算"
    assert hk is not None and hk.name == "港股MACD日算"
    assert cn.executor is exec_macd_cn
    assert hk.executor is exec_macd_hk


def test_resolve_macd_trade_date_from_node_params():
    ctx = WorkflowContext(
        run_id="t",
        workflow_id=1,
        trigger_source="manual",
        trade_date=date(2026, 1, 1),
        node_params={"trade_date": "2026-09-08"},
    )
    assert _resolve_macd_trade_date(ctx) == "2026-09-08"


def test_resolve_macd_trade_date_fallback_ctx():
    ctx = WorkflowContext(
        run_id="t",
        workflow_id=1,
        trigger_source="manual",
        trade_date=date(2026, 9, 7),
    )
    assert _resolve_macd_trade_date(ctx) == "2026-09-07"
