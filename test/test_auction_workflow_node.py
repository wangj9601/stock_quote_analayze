"""A股集合竞价终态采集节点：注册与执行行为（Mock，不连外网）。"""

from datetime import date
from unittest.mock import MagicMock, patch

from backend_core.data_collectors.workflow.adapters import exec_cn_auction_final
from backend_core.data_collectors.workflow.context import WorkflowContext
from backend_core.data_collectors.workflow.node_registry import get_node


def test_cn_auction_final_registered():
    node = get_node("cn_auction_final")
    assert node is not None
    assert node.name == "A股集合竞价终态"
    assert node.category == "cn"
    assert node.executor is exec_cn_auction_final
    props = (node.param_schema or {}).get("properties") or {}
    assert "trade_date" in props
    assert props["trade_date"].get("format") == "date"


@patch(
    "backend_core.data_collectors.workflow.adapters.cn_session_closed_today",
    return_value=True,
)
def test_cn_auction_final_skips_holiday_without_date(mock_closed):
    ctx = WorkflowContext(
        run_id="t",
        workflow_id=1,
        trigger_source="cron",
        trade_date=date(2026, 10, 1),
    )
    result = exec_cn_auction_final(ctx)
    assert result.skipped is True
    assert "休市" in result.message


@patch("backend_api.services.auction_service.collect_auction_snapshot")
@patch("backend_api.database.SessionLocal")
@patch(
    "backend_core.data_collectors.workflow.adapters.cn_session_closed_today",
    return_value=False,
)
def test_cn_auction_final_calls_collect_final(mock_closed, mock_session_cls, mock_collect):
    db = MagicMock()
    mock_session_cls.return_value = db
    mock_collect.return_value = {
        "success": True,
        "trade_date": "2026-10-10",
        "auction_phase": "final",
        "saved": 100,
    }
    ctx = WorkflowContext(
        run_id="t",
        workflow_id=1,
        trigger_source="cron",
        node_params={"trade_date": "2026-10-10"},
    )
    result = exec_cn_auction_final(ctx)
    assert result.success is True
    assert result.skipped is False
    mock_collect.assert_called_once_with(
        db,
        stage="final",
        trade_date="2026-10-10",
        refresh_benchmark=True,
    )
    db.close.assert_called_once()


@patch("backend_api.services.auction_service.collect_auction_snapshot")
@patch("backend_api.database.SessionLocal")
@patch(
    "backend_core.data_collectors.workflow.adapters.cn_session_closed_today",
    return_value=False,
)
def test_cn_auction_final_fails_when_collect_fails(mock_closed, mock_session_cls, mock_collect):
    mock_session_cls.return_value = MagicMock()
    mock_collect.return_value = {"success": False, "message": "not_ready"}
    ctx = WorkflowContext(
        run_id="t",
        workflow_id=1,
        trigger_source="manual",
    )
    result = exec_cn_auction_final(ctx)
    assert result.success is False
    assert "not_ready" in (result.error or "")
