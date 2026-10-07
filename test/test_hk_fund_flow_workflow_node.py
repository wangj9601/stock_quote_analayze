"""采集流程节点 hk_fund_flow_daily：交易日参数与休市跳过逻辑。"""

from datetime import date
from unittest.mock import patch

from backend_core.data_collectors.workflow.adapters import (
    _has_explicit_trade_date,
    _resolve_node_trade_date,
    exec_hk_fund_flow_daily,
)
from backend_core.data_collectors.workflow.context import WorkflowContext
from backend_core.data_collectors.workflow.node_registry import get_node


def test_hk_fund_flow_node_registered_with_trade_date_schema():
    node = get_node("hk_fund_flow_daily")
    assert node is not None
    assert node.executor is exec_hk_fund_flow_daily
    props = (node.param_schema or {}).get("properties") or {}
    assert "trade_date" in props
    assert props["trade_date"].get("format") == "date"


def test_resolve_node_trade_date_from_node_params():
    ctx = WorkflowContext(
        run_id="t",
        workflow_id=1,
        trigger_source="manual",
        trade_date=date(2026, 1, 1),
        node_params={"trade_date": "2026-09-08"},
    )
    assert _resolve_node_trade_date(ctx) == "2026-09-08"
    assert _has_explicit_trade_date(ctx) is True


def test_resolve_node_trade_date_fallback_ctx_not_explicit():
    ctx = WorkflowContext(
        run_id="t",
        workflow_id=1,
        trigger_source="manual",
        trade_date=date(2026, 9, 7),
    )
    assert _resolve_node_trade_date(ctx) == "2026-09-07"
    assert _has_explicit_trade_date(ctx) is False


@patch(
    "backend_core.data_collectors.workflow.adapters.hk_session_closed_today",
    return_value=True,
)
def test_hk_fund_flow_skips_on_holiday_without_date(mock_closed):
    ctx = WorkflowContext(
        run_id="t",
        workflow_id=1,
        trigger_source="scheduled",
        trade_date=date(2026, 10, 1),
    )
    result = exec_hk_fund_flow_daily(ctx)
    assert result.success is True
    assert result.skipped is True
    mock_closed.assert_called()


@patch(
    "backend_core.data_collectors.akshare.hk_fund_flow_from_file.collect_hk_fund_flow_from_file"
)
@patch(
    "backend_core.data_collectors.workflow.adapters.hk_session_closed_today",
    return_value=True,
)
def test_hk_fund_flow_runs_on_holiday_with_explicit_date(mock_closed, mock_collect):
    mock_collect.return_value = {
        "success": True,
        "trade_date": "2026-09-30",
        "written": 10,
    }
    ctx = WorkflowContext(
        run_id="t",
        workflow_id=1,
        trigger_source="manual",
        trade_date=date(2026, 10, 1),
        node_params={"trade_date": "2026-09-30"},
    )
    result = exec_hk_fund_flow_daily(ctx)
    assert result.success is True
    assert result.skipped is False
    mock_collect.assert_called_once_with(trade_date="2026-09-30")
    mock_closed.assert_not_called()
