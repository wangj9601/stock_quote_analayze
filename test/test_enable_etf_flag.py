"""
ENABLE_ETF 开关：选股 API 忽略 etf scope；ui-config 下发 enable_etf。
"""

import os
import sys
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend_api.database import get_db
from backend_api.stock import stock_screening_routes
from backend_api.stock import gms_frontend_routes


class _DummyDB:
    def query(self, *args, **kwargs):
        raise AssertionError("ETF disabled 时不应查库")


def _make_screening_client():
    app = FastAPI()
    app.include_router(stock_screening_routes.router)

    def _override_db():
        yield _DummyDB()

    app.dependency_overrides[get_db] = _override_db
    return TestClient(app)


@patch.object(stock_screening_routes, "GMS_AVAILABLE", True)
@patch("backend_core.config.config.is_etf_enabled", return_value=False)
def test_gms_strategy_scope_etf_skipped_when_disabled(_mock_etf):
    client = _make_screening_client()
    resp = client.get("/api/screening/gms-strategy?scope=etf&date=2026-04-23")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"] == []
    assert data.get("enable_etf") is False
    assert "ENABLE_ETF" in (data.get("message") or "")


@patch.object(gms_frontend_routes, "is_etf_enabled", return_value=False)
def test_gms_ui_config_enable_etf_false(_mock_etf):
    app = FastAPI()
    app.include_router(gms_frontend_routes.router)
    client = TestClient(app)
    resp = client.get("/api/frontend/gms/ui-config")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["enable_etf"] is False
