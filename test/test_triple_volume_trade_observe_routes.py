"""
3倍量策略交易观察股 API（内存 SQLite + 依赖覆盖）。
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend_api.auth import get_current_user
from backend_api.database import get_db
from backend_api.models import TripleVolumeTradeObserveStock, User
from backend_api.triple_volume_trade_observe_routes import router


@pytest.fixture
def memory_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    User.__table__.create(bind=engine)
    TripleVolumeTradeObserveStock.__table__.create(bind=engine)
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
        username="tvo_trade_observe_tester",
        email="tvo_trade_observe_tester@example.com",
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


def test_add_list_codes_and_remove(client):
    r = client.post(
        "/api/stock/triple-volume-trade-observe/add",
        json={
            "code": "000403",
            "market": "CN",
            "name": "派林生物",
            "observe_trade_date": "2026-06-18",
            "snapshot": {"volume_ratio_actual": 3.1, "status": "观察中"},
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == "000403"
    assert body["observe_trade_date"] == "2026-06-18"

    codes = client.get("/api/stock/triple-volume-trade-observe/codes")
    assert codes.status_code == 200
    assert codes.json() == ["CN:000403"]

    lst = client.get("/api/stock/triple-volume-trade-observe/list")
    assert lst.status_code == 200
    assert lst.json()["total"] == 1

    item_id = body["id"]
    rm = client.delete(f"/api/stock/triple-volume-trade-observe/{item_id}")
    assert rm.status_code == 200
    assert client.get("/api/stock/triple-volume-trade-observe/list").json()["total"] == 0


def test_remove_not_found(client):
    r = client.delete("/api/stock/triple-volume-trade-observe/99999")
    assert r.status_code == 404


def test_add_upsert_same_code(client):
    payload = {
        "code": "000931",
        "market": "CN",
        "observe_trade_date": "2026-06-17",
    }
    r1 = client.post("/api/stock/triple-volume-trade-observe/add", json=payload)
    assert r1.status_code == 200
    payload["observe_trade_date"] = "2026-06-18"
    payload["name"] = "中关村"
    r2 = client.post("/api/stock/triple-volume-trade-observe/add", json=payload)
    assert r2.status_code == 200
    assert r2.json()["observe_trade_date"] == "2026-06-18"
    assert client.get("/api/stock/triple-volume-trade-observe/list").json()["total"] == 1
