"""
用户端 /api/stock/gms-backtest 路由单元测试（mock admin_interface）
"""

import os
import sys
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend_api.stock import gms_trace_routes
from backend_api.database import get_db


def _make_client(mock_session: MagicMock) -> TestClient:
    app = FastAPI()
    app.include_router(gms_trace_routes.router)

    def _override_db():
        yield mock_session

    app.dependency_overrides[get_db] = _override_db
    return TestClient(app)


@patch.object(gms_trace_routes, "_GMS_BACKTEST_AVAILABLE", True)
@patch.object(gms_trace_routes, "_gms_build_task_name", return_value="GMS回测_000001_测试")
@patch.object(gms_trace_routes, "_gms_admin_if")
def test_post_gms_backtest_single_stock(mock_admin_if, _mock_name):
    mock_admin_if.create_backtest = MagicMock(return_value="task-uuid-1")
    db = MagicMock()
    client = _make_client(db)
    body = {
        "code": "000001",
        "start_date": "2024-01-01",
        "end_date": "2024-06-01",
        "market": "cn",
        "target_pct": 0.05,
        "horizon_days": 20,
        "min_score": 0,
    }
    r = client.post("/api/stock/gms-backtest", json=body)
    assert r.status_code == 200
    j = r.json()
    assert j["success"] is True
    assert j["data"]["task_id"] == "task-uuid-1"
    mock_admin_if.create_backtest.assert_called_once()
    cfg = mock_admin_if.create_backtest.call_args[0][0]
    assert cfg["stock_pool_mode"] == "single"
    assert cfg["stock_code"] == "000001"
    assert cfg["market"] == "cn"
    assert "signal_scope" not in cfg


@patch.object(gms_trace_routes, "_GMS_BACKTEST_AVAILABLE", True)
@patch.object(gms_trace_routes, "_gms_admin_if")
def test_get_gms_backtest_task(mock_admin_if):
    mock_admin_if.get_task = MagicMock(
        return_value={
            "task_id": "tid",
            "status": "completed",
            "progress": 100,
            "summary": {"hit_rate": 0.5, "total_samples": 10, "hit_count": 5},
        }
    )
    app = FastAPI()
    app.include_router(gms_trace_routes.router)
    client = TestClient(app)
    r = client.get("/api/stock/gms-backtest/tid")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "completed"
    assert r.json()["data"]["summary"]["hit_rate"] == 0.5


@patch.object(gms_trace_routes, "_GMS_BACKTEST_AVAILABLE", True)
@patch.object(gms_trace_routes, "_gms_admin_if")
def test_get_gms_backtest_not_found(mock_admin_if):
    mock_admin_if.get_task = MagicMock(return_value=None)
    app = FastAPI()
    app.include_router(gms_trace_routes.router)
    client = TestClient(app)
    r = client.get("/api/stock/gms-backtest/missing")
    assert r.status_code == 404


@patch.object(gms_trace_routes, "_GMS_BACKTEST_AVAILABLE", True)
@patch.object(gms_trace_routes, "_gms_admin_if")
def test_export_gms_backtest_no_file(mock_admin_if):
    mock_admin_if.download_report = MagicMock(return_value=None)
    app = FastAPI()
    app.include_router(gms_trace_routes.router)
    client = TestClient(app)
    r = client.get("/api/stock/gms-backtest/not-a-task/export")
    assert r.status_code == 404


@patch.object(gms_trace_routes, "_GMS_BACKTEST_AVAILABLE", True)
@patch.object(gms_trace_routes, "_gms_admin_if")
def test_cancel_gms_backtest(mock_admin_if):
    mock_admin_if.cancel_task = MagicMock(return_value=True)
    app = FastAPI()
    app.include_router(gms_trace_routes.router)
    client = TestClient(app)
    r = client.post("/api/stock/gms-backtest/some-id/cancel")
    assert r.status_code == 200
    assert r.json()["success"] is True
    mock_admin_if.cancel_task.assert_called_once_with("some-id")
