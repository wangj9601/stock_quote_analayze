# -*- coding: utf-8 -*-
"""统一交易观察 / 正式交易 API 单测（内存 SQLite）。"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend_api.auth import get_current_user
from backend_api.database import get_db
from backend_api.formal_trade_routes import router as formal_router
from backend_api.models import FormalTrade, TradeObserveHistory, TradeObserveStock, User
from backend_api.trade_observe_routes import router as observe_router


@pytest.fixture
def memory_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    User.__table__.create(bind=engine)
    TradeObserveStock.__table__.create(bind=engine)
    TradeObserveHistory.__table__.create(bind=engine)
    FormalTrade.__table__.create(bind=engine)
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
        username="unified_observe_tester",
        email="unified_observe_tester@example.com",
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
    app.include_router(observe_router)
    app.include_router(formal_router)

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


def test_add_list_filter_source_and_codes(client):
    r1 = client.post(
        "/api/stock/trade-observe/add",
        json={
            "source": "urt",
            "code": "600000",
            "market": "CN",
            "name": "浦发银行",
            "signal_date": "2026-08-14",
            "snapshot": {"score": 70},
        },
    )
    assert r1.status_code == 200, r1.text
    assert r1.json()["source"] == "urt"

    r2 = client.post(
        "/api/stock/trade-observe/add",
        json={
            "source": "stock_analysis",
            "code": "600000",
            "market": "CN",
            "name": "浦发银行",
            "signal_date": "2026-08-14",
        },
    )
    assert r2.status_code == 200
    assert r2.json()["id"] != r1.json()["id"]

    all_list = client.get("/api/stock/trade-observe/list")
    assert all_list.status_code == 200
    assert all_list.json()["total"] == 2

    urt_only = client.get("/api/stock/trade-observe/list?source=urt")
    assert urt_only.json()["total"] == 1
    assert urt_only.json()["items"][0]["source"] == "urt"

    codes = client.get("/api/stock/trade-observe/codes")
    assert codes.status_code == 200
    assert "CN:600000" in codes.json()


def test_add_gann_trend_source(client):
    r = client.post(
        "/api/stock/trade-observe/add",
        json={
            "source": "gann_trend",
            "code": "600562",
            "market": "CN",
            "name": "国睿科技",
            "signal_date": "2026-08-21",
            "snapshot": {"bias": "bearish", "summary": "偏空"},
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "gann_trend"
    assert body["code"] == "600562"

    filtered = client.get("/api/stock/trade-observe/list?source=gann_trend")
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["source"] == "gann_trend"

    codes = client.get("/api/stock/trade-observe/codes?source=gann_trend")
    assert codes.status_code == 200
    assert "CN:600562" in codes.json()


def test_from_observe_and_duplicate_open(client):
    obs = client.post(
        "/api/stock/trade-observe/add",
        json={
            "source": "gms",
            "code": "000001",
            "market": "CN",
            "name": "平安银行",
            "signal_date": "2026-08-14",
        },
    )
    assert obs.status_code == 200
    oid = obs.json()["id"]

    formal = client.post(
        f"/api/stock/formal-trade/from-observe/{oid}",
        json={"entry_price": 10.5, "position_lots": 2},
    )
    assert formal.status_code == 200, formal.text
    assert formal.json()["status"] == "open"
    assert formal.json()["source"] == "gms"
    trade_id = formal.json()["id"]

    # 转入正式后观察行会移除；同 observe_id 再转应 404
    again = client.post(
        f"/api/stock/formal-trade/from-observe/{oid}",
        json={"entry_price": 11.0, "position_lots": 1},
    )
    assert again.status_code == 404

    codes = client.get("/api/stock/formal-trade/codes")
    assert "CN:000001" in codes.json()

    closed = client.patch(
        f"/api/stock/formal-trade/{trade_id}",
        json={"exit_price": 11.0, "status": "closed"},
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
    assert closed.json().get("pnl_percent") is not None


def test_remove_observe_writes_history(client, memory_db):
    obs = client.post(
        "/api/stock/trade-observe/add",
        json={
            "source": "rpe",
            "code": "300001",
            "signal_date": "2026-08-01",
        },
    )
    oid = obs.json()["id"]
    rm = client.delete(f"/api/stock/trade-observe/{oid}")
    assert rm.status_code == 200
    assert client.get("/api/stock/trade-observe/list?source=rpe").json()["total"] == 0
    hist = client.get("/api/stock/trade-observe/history")
    assert hist.status_code == 200
    assert hist.json()["total"] >= 1
