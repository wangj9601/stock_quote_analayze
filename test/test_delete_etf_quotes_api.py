"""管理端 ETF 实时/历史行情删除接口（Mock DB）。"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from backend_api.admin.quotes import router as admin_quotes_router
from backend_api.database import get_db
from backend_api.auth import get_current_admin


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(admin_quotes_router)
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
        ("/api/admin/quotes/etf/realtime/delete", {"scope": "single", "code": "510300"}),
        (
            "/api/admin/quotes/etf/historical/delete",
            {"scope": "all", "start_date": "2026-01-01", "end_date": "2026-01-31"},
        ),
    ],
)
def test_etf_delete_ok(client, path, payload):
    c, mock_db = client
    _mock_delete_chain(mock_db)
    r = c.post(path, json=payload)
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_etf_rt_single_no_code_422(client):
    c, _ = client
    r = c.post("/api/admin/quotes/etf/realtime/delete", json={"scope": "single"})
    assert r.status_code == 422
