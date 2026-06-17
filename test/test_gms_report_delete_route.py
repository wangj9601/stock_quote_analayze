"""GMS 管理端：删除历史报告路由"""

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


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(gms_admin_routes.router)

    def _override_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = _override_db
    return TestClient(app)


@patch.object(gms_admin_routes, "admin_interface")
def test_delete_report_success(mock_admin_if):
    mock_admin_if.delete_report = MagicMock(return_value=True)
    client = _make_client()

    r = client.post("/api/admin/gms/reports/rpt-001/delete")
    assert r.status_code == 200
    assert r.json()["success"] is True
    mock_admin_if.delete_report.assert_called_once_with("rpt-001")


@patch.object(gms_admin_routes, "admin_interface")
def test_delete_report_not_found(mock_admin_if):
    mock_admin_if.delete_report = MagicMock(return_value=False)
    client = _make_client()

    r = client.delete("/api/admin/gms/reports/missing-id")
    assert r.status_code == 404
