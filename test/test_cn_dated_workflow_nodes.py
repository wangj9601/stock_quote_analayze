"""A股日采节点：交易日参数与注册校验。"""

from datetime import date
from unittest.mock import patch

from backend_core.data_collectors.workflow.adapters import (
    exec_board_fund_flow_daily,
    exec_market_daily_review,
    exec_ths_fund_flow_daily,
    exec_zt_pool_em_daily,
)
from backend_core.data_collectors.workflow.context import WorkflowContext
from backend_core.data_collectors.workflow.node_registry import get_node


def test_dated_cn_nodes_registered_with_trade_date():
    for key in (
        "ths_fund_flow_daily",
        "board_fund_flow_daily",
        "zt_pool_em_daily",
        "market_daily_review",
    ):
        node = get_node(key)
        assert node is not None, key
        props = (node.param_schema or {}).get("properties") or {}
        assert "trade_date" in props, key
        assert props["trade_date"].get("format") == "date"


def test_strategy_nodes_still_registered():
    for key, name_part in (
        ("rs_rating_cn", "相对强度"),
        ("gms_signals_cn", "GMS"),
        ("urt_signals_cn", "URT"),
        ("csb_signals_cn", "CSB"),
        ("sbbr_signals_cn", "SBBR"),
        ("rpe_signals_cn", "RPE"),
        ("index_daily_cn", "指数日线"),
        ("stock_recommend_brief", "推荐简报"),
    ):
        node = get_node(key)
        assert node is not None, key
        assert name_part in (node.name or "")


@patch(
    "backend_core.data_collectors.akshare.board_fund_flow_daily.collect_board_fund_flow_daily"
)
@patch(
    "backend_core.data_collectors.workflow.adapters.cn_session_closed_today",
    return_value=True,
)
def test_board_fund_flow_runs_with_explicit_date_on_holiday(mock_closed, mock_collect):
    mock_collect.return_value = {"success": True, "written": 1}
    ctx = WorkflowContext(
        run_id="t",
        workflow_id=1,
        trigger_source="manual",
        trade_date=date(2026, 10, 1),
        node_params={"trade_date": "2026-09-30"},
    )
    result = exec_board_fund_flow_daily(ctx)
    assert result.success is True
    assert result.skipped is False
    mock_collect.assert_called_once_with(trade_date="2026-09-30")
    mock_closed.assert_not_called()


@patch(
    "backend_core.data_collectors.akshare.zt_pool_em.collect_zt_pool_em"
)
@patch(
    "backend_core.data_collectors.workflow.adapters.cn_session_closed_today",
    return_value=False,
)
def test_zt_pool_passes_trade_date(mock_closed, mock_collect):
    mock_collect.return_value = {"success": True, "written": 10}
    ctx = WorkflowContext(
        run_id="t",
        workflow_id=1,
        trigger_source="manual",
        node_params={"trade_date": "2026-09-29"},
    )
    result = exec_zt_pool_em_daily(ctx)
    assert result.success is True
    mock_collect.assert_called_once_with(trade_date="2026-09-29")


@patch(
    "backend_core.market_review.compute.collect_and_build_review"
)
@patch(
    "backend_core.data_collectors.workflow.adapters.cn_session_closed_today",
    return_value=False,
)
def test_market_daily_review_passes_trade_date(mock_closed, mock_review):
    mock_review.return_value = {"success": True, "trade_date": "2026-09-29"}
    ctx = WorkflowContext(
        run_id="t",
        workflow_id=1,
        trigger_source="manual",
        node_params={"trade_date": "2026-09-29"},
    )
    result = exec_market_daily_review(ctx)
    assert result.success is True
    mock_review.assert_called_once_with(
        trade_date="2026-09-29", collect_zt=False, export_md=True
    )


@patch(
    "backend_core.data_collectors.akshare.ths_fund_flow_daily.collect_ths_fund_flow_daily"
)
@patch(
    "backend_core.data_collectors.workflow.adapters.cn_session_closed_today",
    return_value=True,
)
def test_ths_fund_flow_skips_holiday_without_date(mock_closed, mock_collect):
    ctx = WorkflowContext(
        run_id="t",
        workflow_id=1,
        trigger_source="scheduled",
        trade_date=date(2026, 10, 1),
    )
    result = exec_ths_fund_flow_daily(ctx)
    assert result.skipped is True
    mock_collect.assert_not_called()
