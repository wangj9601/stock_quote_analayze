"""
GMS 交易价格计划 compute_price_plan 与观察 API 集成测试。
"""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend_api.auth import get_current_user
from backend_api.database import get_db
from backend_api.gms_trade_observe_routes import router
from backend_api.models import (
    GmsFormalTrade,
    GmsTradeObserveHistory,
    GmsTradeObserveStock,
    GMSStrategyVersion,
    GMSStrategyVersionStock,
    HistoricalQuotes,
    StockBasicInfo,
    User,
)
from backend_core.strategies.gms.trade_price_plan import (
    DEFAULT_STOP_LOSS_PCT,
    DEFAULT_TARGET_PCT,
    compute_price_plan,
)


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
    GmsFormalTrade.__table__.create(bind=engine)
    GMSStrategyVersion.__table__.create(bind=engine)
    GMSStrategyVersionStock.__table__.create(bind=engine)
    StockBasicInfo.__table__.create(bind=engine)
    HistoricalQuotes.__table__.create(bind=engine)
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
        username="gms_price_plan_tester",
        email="gms_price_plan_tester@example.com",
        password_hash="x",
        role="user",
        status="active",
    )
    memory_db.add(u)
    memory_db.add(
        GMSStrategyVersion(
            strategy_code="GMS",
            version_name="V1",
            version_no=1,
            is_active=True,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
    )
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


def test_compute_price_plan_uses_t_plus_1_open(memory_db):
    memory_db.add(
        HistoricalQuotes(
            code="600519",
            date=date(2026, 5, 16),
            open=101.5,
            close=102.0,
            high=103.0,
            low=100.0,
        )
    )
    memory_db.commit()

    plan = compute_price_plan(
        memory_db,
        market="CN",
        code="600519",
        signal_date=date(2026, 5, 15),
        snapshot={
            "buy_type": "右侧",
            "current_price": 100.0,
            "d_ma20": 98.0,
        },
    )
    assert plan["buy_price_suggested"] == 101.5
    assert plan["buy_price_source"] == "t_plus_1_open"
    assert plan["stop_loss_price"] == round(101.5 * (1 - DEFAULT_STOP_LOSS_PCT), 4)
    assert plan["take_profit_price"] == round(101.5 * (1 + DEFAULT_TARGET_PCT), 4)
    assert plan["reference_sell_price"] == round(98.0 * 1.15, 4)
    assert plan["buy_price_alt"].get("signal_close") == 100.0


def test_compute_price_plan_fallback_signal_close(memory_db):
    plan = compute_price_plan(
        memory_db,
        market="CN",
        code="600519",
        signal_date=date(2026, 5, 15),
        snapshot={
            "buy_type": "左侧",
            "current_price": 88.8,
            "d_ma20": 87.5,
        },
    )
    assert plan["buy_price_suggested"] == 88.8
    assert plan["buy_price_source"] == "signal_close"
    assert any("T+1" in n for n in plan["notes"])
    assert plan["buy_price_alt"].get("conservative_ma20") == 87.5


@patch("backend_core.strategies.gms.trade_price_plan._get_entry_open_next_day", return_value=50.0)
def test_compute_price_plan_left_buy_alt(_mock_open, memory_db):
    plan = compute_price_plan(
        memory_db,
        market="CN",
        code="000001",
        signal_date=date(2026, 5, 15),
        snapshot={
            "left_buy_signal": True,
            "buy_type": "左侧",
            "current_price": 49.0,
            "d_ma20": 48.0,
        },
    )
    assert plan["buy_price_suggested"] == 50.0
    assert plan["buy_price_alt"]["conservative_ma20"] == 48.0
    assert plan["params"]["buy_type"] == "左侧"


def test_observe_list_returns_price_plan(client, memory_db):
    with patch(
        "backend_core.strategies.gms.trade_price_plan._get_entry_open_next_day",
        return_value=12.34,
    ):
        r = client.post(
            "/api/stock/gms-trade-observe/add",
            json={
                "code": "000001",
                "market": "CN",
                "name": "平安银行",
                "signal_date": "2026-05-15",
                "snapshot": {
                    "buy_type": "右侧",
                    "current_price": 12.0,
                    "d_ma20": 11.5,
                    "sell_signal": False,
                },
            },
        )
    assert r.status_code == 200
    body = r.json()
    assert "price_plan" in body
    assert body["price_plan"]["buy_price_suggested"] == 12.34
    assert body["snapshot"]["price_plan"]["buy_price_suggested"] == 12.34

    lst = client.get("/api/stock/gms-trade-observe/list")
    assert lst.status_code == 200
    items = lst.json()["items"]
    assert len(items) == 1
    assert items[0]["price_plan"]["stop_loss_price"] == round(12.34 * 0.95, 4)


def test_observe_price_plan_refresh_endpoint(client, memory_db):
    with patch(
        "backend_core.strategies.gms.trade_price_plan._get_entry_open_next_day",
        return_value=20.0,
    ):
        add = client.post(
            "/api/stock/gms-trade-observe/add",
            json={
                "code": "600519",
                "market": "CN",
                "name": "贵州茅台",
                "signal_date": "2026-05-15",
                "snapshot": {"current_price": 19.0, "d_ma20": 18.0},
            },
        )
    item_id = add.json()["id"]

    with patch(
        "backend_core.strategies.gms.trade_price_plan._get_entry_open_next_day",
        return_value=21.0,
    ):
        refreshed = client.get(f"/api/stock/gms-trade-observe/{item_id}/price-plan")
    assert refreshed.status_code == 200
    data = refreshed.json()
    assert data["buy_price_suggested"] == 21.0

    row = memory_db.query(GmsTradeObserveStock).filter(GmsTradeObserveStock.id == item_id).first()
    assert row.signal_snapshot_json["price_plan"]["buy_price_suggested"] == 21.0
