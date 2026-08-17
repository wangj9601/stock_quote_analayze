"""
GMS 正式交易 API（内存 SQLite + 依赖覆盖）。
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
from backend_api.gms_formal_trade_routes import router
from backend_api.models import FormalTrade, TradeObserveHistory, TradeObserveStock, User


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
        username="gms_formal_trade_tester",
        email="gms_formal_trade_tester@example.com",
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


def _seed_observe(memory_db, test_user, code="600519"):
    row = TradeObserveStock(
        user_id=test_user.id,
        market="CN",
        code=code,
        name="贵州茅台",
        source="gms",
        signal_snapshot_json={"current_price": 1800.0, "signal_strength": 0.9},
        signal_date=date(2026, 5, 10),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    memory_db.add(row)
    memory_db.commit()
    memory_db.refresh(row)
    return row


def test_from_observe_list_update_close_and_delete(client, memory_db, test_user):
    observe = _seed_observe(memory_db, test_user)
    r = client.post(
        f"/api/stock/gms-formal-trade/from-observe/{observe.id}",
        json={"entry_price": 1750.5, "position_lots": 2, "notes": "计划持有"},
    )
    assert r.status_code == 200
    item = r.json()
    assert item["code"] == "600519"
    assert item["entry_price"] == 1750.5
    assert item["position_lots"] == 2
    assert item["status"] == "open"
    assert item["source_observe_id"] == observe.id
    trade_id = item["id"]

    assert memory_db.query(TradeObserveStock).filter(TradeObserveStock.id == observe.id).first() is None
    hist = (
        memory_db.query(TradeObserveHistory)
        .filter(TradeObserveHistory.source_observe_id == observe.id)
        .first()
    )
    assert hist is not None

    lst = client.get("/api/stock/gms-formal-trade/list")
    assert lst.status_code == 200
    assert lst.json()["total"] == 1

    closed = client.patch(
        f"/api/stock/gms-formal-trade/{trade_id}",
        json={"exit_price": 1800.0},
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
    assert closed.json()["exit_price"] == 1800.0
    assert closed.json()["pnl_percent"] is not None

    db_row = memory_db.query(FormalTrade).filter(FormalTrade.id == trade_id).first()
    assert db_row is not None
    assert db_row.status == "closed"

    reopened = client.patch(
        f"/api/stock/gms-formal-trade/{trade_id}",
        json={"reopen": True},
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "open"
    assert reopened.json()["exit_price"] is None
    assert reopened.json()["pnl_percent"] is None

    rm = client.delete(f"/api/stock/gms-formal-trade/{trade_id}")
    assert rm.status_code == 200
    assert client.get("/api/stock/gms-formal-trade/list").json()["total"] == 0


def test_from_observe_not_found(client):
    r = client.post(
        "/api/stock/gms-formal-trade/from-observe/99999",
        json={"entry_price": 10.0, "position_lots": 1},
    )
    assert r.status_code == 404


def test_from_observe_cleans_stale_observe_when_formal_trade_exists(client, memory_db, test_user):
    observe = _seed_observe(memory_db, test_user, code="601699")
    now = datetime.now()
    trade = FormalTrade(
        user_id=test_user.id,
        market="CN",
        code="601699",
        name="潞安环能",
        source="gms",
        source_observe_id=observe.id,
        entry_price=15.7,
        position_lots=2,
        status="open",
        entry_at=now,
        created_at=now,
        updated_at=now,
    )
    memory_db.add(trade)
    memory_db.commit()
    memory_db.refresh(trade)

    r = client.post(
        f"/api/stock/gms-formal-trade/from-observe/{observe.id}",
        json={"entry_price": 16.0, "position_lots": 1},
    )
    assert r.status_code == 200
    assert r.json()["id"] == trade.id
    assert memory_db.query(TradeObserveStock).filter(TradeObserveStock.id == observe.id).first() is None
    assert client.get("/api/stock/gms-formal-trade/list").json()["total"] == 1


def test_compute_formal_trade_pnl():
    from backend_api.trade_observe_service import compute_formal_trade_pnl

    amt, pct = compute_formal_trade_pnl(10.0, 11.0, 3, "CN")
    assert pct == pytest.approx(10.0)
    assert amt == pytest.approx(300.0)


def test_formal_trade_codes_for_signal_button(client, memory_db, test_user):
    now = datetime.now()
    memory_db.add(
        FormalTrade(
            user_id=test_user.id,
            market="CN",
            code="002709",
            name="天赐材料",
            source="gms",
            entry_price=50.0,
            position_lots=1,
            status="open",
            entry_at=now,
            created_at=now,
            updated_at=now,
        )
    )
    memory_db.commit()

    r = client.get("/api/stock/gms-formal-trade/codes")
    assert r.status_code == 200
    assert "CN:002709" in r.json()
