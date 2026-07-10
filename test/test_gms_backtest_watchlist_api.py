"""
GMS 回测：自选股股票池（watchlist）相关单元测试
"""

import os
import sys
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend_api.admin import gms_admin_routes
from backend_api.database import get_db


def _make_client(mock_session: MagicMock) -> TestClient:
    app = FastAPI()
    app.include_router(gms_admin_routes.router)

    def _override_db():
        yield mock_session

    app.dependency_overrides[get_db] = _override_db
    return TestClient(app)


def test_distinct_watchlist_codes_dedupe_and_sort():
    db = MagicMock()
    db.query.return_value.distinct.return_value.all.return_value = [
        ("600519",),
        ("000001",),
        ("600519",),
        ("00700",),
    ]
    assert gms_admin_routes._distinct_watchlist_codes(db) == ["000001", "00700", "600519"]


def test_create_backtest_watchlist_empty_returns_400():
    db = MagicMock()
    db.query.return_value.distinct.return_value.all.return_value = []
    client = _make_client(db)
    body = {
        "market": "all",
        "start_date": "2024-01-01",
        "end_date": "2024-06-01",
        "stock_pool_mode": "watchlist",
    }
    r = client.post("/api/admin/gms/backtests", json=body)
    assert r.status_code == 400
    assert "自选股" in (r.json().get("detail") or "")


@patch.object(gms_admin_routes.admin_interface, "create_backtest", return_value="task-id-1")
def test_create_backtest_watchlist_resolves_stock_pool(mock_create):
    db = MagicMock()
    db.query.return_value.distinct.return_value.all.return_value = [("600519",), ("000001",)]
    client = _make_client(db)
    body = {
        "market": "cn",
        "start_date": "2024-01-01",
        "end_date": "2024-06-01",
        "stock_pool_mode": "watchlist",
    }
    r = client.post("/api/admin/gms/backtests", json=body)
    assert r.status_code == 200
    assert r.json()["data"]["task_id"] == "task-id-1"
    mock_create.assert_called_once()
    cfg = mock_create.call_args[0][0]
    assert cfg["stock_pool_mode"] == "watchlist"
    assert cfg["stock_pool"] == ["000001", "600519"]


@patch.object(gms_admin_routes.admin_interface, "create_backtest", return_value="task-id-cyb")
def test_create_backtest_watchlist_filters_cn_board_segment(mock_create):
    db = MagicMock()
    db.query.return_value.distinct.return_value.all.return_value = [
        ("600519",),
        ("300001",),
        ("00700",),
    ]
    client = _make_client(db)
    body = {
        "market": "all",
        "cn_board_segment": "CYB",
        "start_date": "2024-01-01",
        "end_date": "2024-06-01",
        "stock_pool_mode": "watchlist",
    }
    r = client.post("/api/admin/gms/backtests", json=body)
    assert r.status_code == 200
    cfg = mock_create.call_args[0][0]
    assert cfg["cn_board_segment"] == "CYB"
    assert cfg["stock_pool"] == ["00700", "300001"]


def test_create_backtest_cn_board_segment_invalid_returns_400():
    client = _make_client(MagicMock())
    body = {
        "market": "cn",
        "cn_board_segment": "INVALID",
        "start_date": "2024-01-01",
        "end_date": "2024-06-01",
    }
    r = client.post("/api/admin/gms/backtests", json=body)
    assert r.status_code == 400


def test_create_backtest_hk_rejects_cn_board_segment():
    client = _make_client(MagicMock())
    body = {
        "market": "hk",
        "cn_board_segment": "CYB",
        "start_date": "2024-01-01",
        "end_date": "2024-06-01",
    }
    r = client.post("/api/admin/gms/backtests", json=body)
    assert r.status_code == 400
    assert "港股" in (r.json().get("detail") or "")


@patch.object(gms_admin_routes.admin_interface, "create_backtest", return_value="task-id-2")
def test_create_backtest_watchlist_ignores_body_stock_pool(mock_create):
    """watchlist 模式下以库表为准，忽略请求中的 stock_code / stock_pool。"""
    db = MagicMock()
    db.query.return_value.distinct.return_value.all.return_value = [("300001",)]
    client = _make_client(db)
    body = {
        "market": "all",
        "start_date": "2024-01-01",
        "end_date": "2024-06-01",
        "stock_pool_mode": "watchlist",
        "stock_code": "999999",
        "stock_pool": ["should", "be", "ignored"],
    }
    r = client.post("/api/admin/gms/backtests", json=body)
    assert r.status_code == 200
    cfg = mock_create.call_args[0][0]
    assert cfg["stock_pool"] == ["300001"]
    assert "stock_code" not in cfg


@patch.object(gms_admin_routes.admin_interface, "create_backtest", return_value="task-id-industry")
@patch.object(
    gms_admin_routes,
    "_resolve_industry_board_backtest_codes",
    return_value=(["BK0479"], ["000001", "600519"]),
)
def test_create_backtest_industry_board_resolves_stock_pool(mock_resolve, mock_create):
    client = _make_client(MagicMock())
    body = {
        "market": "cn",
        "start_date": "2024-01-01",
        "end_date": "2024-06-01",
        "stock_pool_mode": "industry_board",
        "industry_board_codes": ["BK0479"],
    }
    r = client.post("/api/admin/gms/backtests", json=body)
    assert r.status_code == 200
    mock_resolve.assert_called_once()
    cfg = mock_create.call_args[0][0]
    assert cfg["stock_pool_mode"] == "industry_board"
    assert cfg["industry_board_codes"] == ["BK0479"]
    assert cfg["stock_pool"] == ["000001", "600519"]


def test_create_backtest_industry_board_requires_codes():
    client = _make_client(MagicMock())
    body = {
        "market": "cn",
        "start_date": "2024-01-01",
        "end_date": "2024-06-01",
        "stock_pool_mode": "industry_board",
    }
    r = client.post("/api/admin/gms/backtests", json=body)
    assert r.status_code == 400
    assert "行业板块" in (r.json().get("detail") or "")


def test_create_backtest_industry_board_rejects_hk_market():
    client = _make_client(MagicMock())
    body = {
        "market": "hk",
        "start_date": "2024-01-01",
        "end_date": "2024-06-01",
        "stock_pool_mode": "industry_board",
        "industry_board_codes": ["BK0479"],
    }
    r = client.post("/api/admin/gms/backtests", json=body)
    assert r.status_code == 400
    assert "A 股" in (r.json().get("detail") or "")


def test_create_backtest_industry_board_rejects_all_market():
    client = _make_client(MagicMock())
    body = {
        "market": "all",
        "start_date": "2024-01-01",
        "end_date": "2024-06-01",
        "stock_pool_mode": "industry_board",
        "industry_board_codes": ["BK0479"],
    }
    r = client.post("/api/admin/gms/backtests", json=body)
    assert r.status_code == 400
    assert "港股暂无" in (r.json().get("detail") or "")


@patch.object(gms_admin_routes.admin_interface, "create_backtest", return_value="task-id-concept")
@patch.object(
    gms_admin_routes,
    "_resolve_concept_board_backtest_codes",
    return_value=(["BK0428", "BK0479"], ["000001", "300001"]),
)
def test_create_backtest_concept_board_accepts_multiple_codes(mock_resolve, mock_create):
    client = _make_client(MagicMock())
    body = {
        "market": "cn",
        "start_date": "2024-01-01",
        "end_date": "2024-06-01",
        "stock_pool_mode": "concept_board",
        "concept_board_codes": ["BK0428", "BK0479"],
    }
    r = client.post("/api/admin/gms/backtests", json=body)
    assert r.status_code == 200
    cfg = mock_create.call_args[0][0]
    assert cfg["market"] == "cn"
    assert cfg["concept_board_codes"] == ["BK0428", "BK0479"]
    assert cfg["stock_pool"] == ["000001", "300001"]


@patch.object(gms_admin_routes.admin_interface, "delete_tasks_batch", return_value={"deleted": 2, "failed": [], "failed_count": 0})
def test_batch_delete_backtests(mock_batch):
    client = _make_client(MagicMock())
    r = client.post(
        "/api/admin/gms/backtests/batch-delete",
        json={"task_ids": ["task-a", "task-b"]},
    )
    assert r.status_code == 200
    assert r.json()["data"]["deleted"] == 2
    mock_batch.assert_called_once_with(["task-a", "task-b"])


def test_batch_delete_backtests_empty_ids_returns_400():
    client = _make_client(MagicMock())
    r = client.post("/api/admin/gms/backtests/batch-delete", json={"task_ids": ["", "  "]})
    assert r.status_code == 400
