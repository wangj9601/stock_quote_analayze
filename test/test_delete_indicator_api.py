"""管理端 MA / MAVOL / PVFRS 指标删除接口（Mock DB）。"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from backend_api.admin.indicators import router as admin_indicators_router
from backend_api.database import get_db
from backend_api.auth import get_current_admin


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(admin_indicators_router)
    mock_db = MagicMock()

    def override_db():
        yield mock_db

    def override_admin():
        u = MagicMock()
        u.username = "admin"
        return u

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_admin] = override_admin
    return TestClient(app), mock_db


def _mock_delete_chain(mock_db):
    chain = MagicMock()
    mock_db.query.return_value = chain
    chain.filter.return_value = chain
    chain.delete.return_value = 1


@pytest.mark.parametrize(
    "path,payload",
    [
        (
            "/api/admin/indicators/ma/delete",
            {"scope": "single", "code": "600000", "market_type": "CN"},
        ),
        (
            "/api/admin/indicators/mavol/delete",
            {"scope": "all", "market_type": "CN", "start_date": "2026-01-01", "end_date": "2026-01-31"},
        ),
        (
            "/api/admin/indicators/pvfrs/delete",
            {"scope": "single", "code": "00700", "market_type": "HK", "start_date": "2026-04-01", "end_date": "2026-04-05"},
        ),
    ],
)
def test_indicator_delete_ok(client, path, payload):
    c, mock_db = client
    _mock_delete_chain(mock_db)
    r = c.post(path, json=payload)
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_ma_single_no_market_422(client):
    c, _ = client
    r = c.post(
        "/api/admin/indicators/ma/delete",
        json={"scope": "single", "code": "600000"},
    )
    assert r.status_code == 422
