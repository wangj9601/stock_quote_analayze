"""
GMS 管理端回测：自选股按用户范围创建任务
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


@patch.object(gms_admin_routes, "_build_task_name_with_stocks", return_value="GMS回测_自选股用户")
@patch.object(gms_admin_routes, "_distinct_watchlist_codes", return_value=["000001", "00700"])
@patch.object(gms_admin_routes, "admin_interface")
def test_create_backtest_watchlist_with_user_id(mock_admin_if, mock_codes, _mock_name):
    mock_admin_if.create_backtest = MagicMock(return_value="task-watchlist-uid")
    db = MagicMock()
    client = _make_client(db)

    body = {
        "market": "all",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "target_pct": 0.05,
        "horizon_days": 20,
        "min_score": 0,
        "stock_pool_mode": "watchlist",
        "watchlist_user_id": 123,
    }
    r = client.post("/api/admin/gms/backtests", json=body)
    assert r.status_code == 200
    mock_codes.assert_called_once_with(db, user_id=123)
    cfg = mock_admin_if.create_backtest.call_args[0][0]
    assert cfg["stock_pool_mode"] == "watchlist"
    assert cfg["watchlist_user_id"] == 123
    assert cfg["stock_pool"] == ["000001", "00700"]


@patch.object(gms_admin_routes, "_build_task_name_with_stocks", return_value="GMS回测_全自选")
@patch.object(gms_admin_routes, "_distinct_watchlist_codes", return_value=["000001"])
@patch.object(gms_admin_routes, "admin_interface")
def test_create_backtest_watchlist_all_users(mock_admin_if, mock_codes, _mock_name):
    mock_admin_if.create_backtest = MagicMock(return_value="task-watchlist-all")
    db = MagicMock()
    client = _make_client(db)

    body = {
        "market": "all",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "target_pct": 0.05,
        "horizon_days": 20,
        "min_score": 0,
        "stock_pool_mode": "watchlist",
    }
    r = client.post("/api/admin/gms/backtests", json=body)
    assert r.status_code == 200
    mock_codes.assert_called_once_with(db, user_id=None)
    cfg = mock_admin_if.create_backtest.call_args[0][0]
    assert cfg["stock_pool_mode"] == "watchlist"
    assert "watchlist_user_id" not in cfg
    assert cfg["stock_pool"] == ["000001"]
