"""
GMS 用户交易观察股 API（内存 SQLite + 依赖覆盖）。
"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend_api.auth import get_current_user
from backend_api.database import get_db
from backend_api.gms_trade_observe_routes import router
from backend_api.models import GmsTradeObserveHistory, GmsTradeObserveStock, User


@pytest.fixture
def memory_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    User.__table__.create(bind=engine)
    GmsTradeObserveStock.__table__.create(bind=engine)
    GmsTradeObserveHistory.__table__.create(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


@pytest.fixture
def test_user(memory_db):
    u = User(
        id=1,
        username="gms_trade_observe_tester",
        email="gms_trade_observe_tester@example.com",
        password_hash="x",
        role="user",
        status="active",
    )
    memory_db.add(u)
    memory_db.commit()
    memory_db.refresh(u)
    return u


@pytest.fixture
def client(memory_db, test_user):
    app = FastAPI()
    app.include_router(router)

    def override_db():
        try:
            yield memory_db
        finally:
            pass

    def override_user():
        return test_user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return TestClient(app)


def test_add_list_codes_and_remove(client, memory_db, test_user):
    r = client.post(
        "/api/stock/gms-trade-observe/add",
        json={
            "code": "600519",
            "market": "CN",
            "name": "贵州茅台",
            "signal_date": "2026-05-15",
            "snapshot": {"signal_strength": 0.82, "buy_type": "左侧"},
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == "600519"
    item_id = body["id"]

    codes = client.get("/api/stock/gms-trade-observe/codes")
    assert codes.status_code == 200
    assert "CN:600519" in codes.json()

    lst = client.get("/api/stock/gms-trade-observe/list")
    assert lst.status_code == 200
    data = lst.json()
    assert data["total"] == 1
    assert data["items"][0]["snapshot"]["buy_type"] == "左侧"

    r2 = client.post(
        "/api/stock/gms-trade-observe/add",
        json={
            "code": "600519",
            "market": "CN",
            "name": "贵州茅台",
            "signal_date": "2026-05-15",
            "snapshot": {"buy_type": "更新", "signal_date": "2026-05-15"},
        },
    )
    assert r2.status_code == 200
    assert r2.json()["id"] == item_id

    rm = client.delete(f"/api/stock/gms-trade-observe/{item_id}")
    assert rm.status_code == 200
    rm_body = rm.json()
    assert rm_body.get("history_id")
    assert client.get("/api/stock/gms-trade-observe/list").json()["total"] == 0

    hist = client.get("/api/stock/gms-trade-observe/history")
    assert hist.status_code == 200
    hist_data = hist.json()
    assert hist_data["total"] == 1
    assert hist_data["items"][0]["code"] == "600519"
    assert hist_data["items"][0]["source_observe_id"] == item_id
    assert hist_data["items"][0]["snapshot"]["buy_type"] == "更新"


def test_remove_not_found(client):
    r = client.delete("/api/stock/gms-trade-observe/99999")
    assert r.status_code == 404


def test_add_requires_signal_date(client):
    r = client.post(
        "/api/stock/gms-trade-observe/add",
        json={"code": "000001", "market": "CN", "name": "平安银行"},
    )
    assert r.status_code == 400


def test_list_signal_date_from_snapshot(memory_db, test_user):
    row = GmsTradeObserveStock(
        user_id=test_user.id,
        market="CN",
        code="600519",
        name="贵州茅台",
        signal_date=None,
        signal_snapshot_json={"signal_date": "2026-05-15", "buy_type": "左侧"},
        created_at=datetime(2026, 5, 19, 10, 0, 0),
        updated_at=datetime(2026, 5, 19, 10, 0, 0),
    )
    memory_db.add(row)
    memory_db.commit()
    from backend_api.gms_trade_observe_routes import _row_to_item

    item = _row_to_item(row)
    assert item.signal_date == "2026-05-15"
