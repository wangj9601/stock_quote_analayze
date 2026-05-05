"""
管理端删除 A 股实时行情接口的基础校验测试（不连接真实数据库）。
"""

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
        u.username = "test_admin"
        return u

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_admin] = override_admin

    return TestClient(app), mock_db


def test_delete_single_without_code_422(client):
    c, _ = client
    r = c.post("/api/admin/quotes/realtime/stocks/delete", json={"scope": "single"})
    assert r.status_code == 422


def test_delete_single_calls_delete(client):
    c, mock_db = client
    chain = MagicMock()
    mock_db.query.return_value = chain
    chain.filter.return_value = chain
    chain.delete.return_value = 3
    r = c.post(
        "/api/admin/quotes/realtime/stocks/delete",
        json={"scope": "single", "code": "600519", "start_date": "2026-01-01", "end_date": "2026-01-31"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"]["deleted"] == 3


def test_invalid_date_format_400(client):
    c, mock_db = client
    chain = MagicMock()
    mock_db.query.return_value = chain
    chain.filter.return_value = chain
    chain.delete.return_value = 0
    r = c.post(
        "/api/admin/quotes/realtime/stocks/delete",
        json={"scope": "all", "start_date": "2026/01/01"},
    )
    assert r.status_code == 400
