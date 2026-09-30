# -*- coding: utf-8 -*-
"""自选股轻量代码接口 /api/watchlist/codes 与 GET /api/watchlist?limit=N。"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def client():
    from backend_api import watchlist_manage
    from backend_api.auth import get_current_user
    from backend_api.database import get_db
    from backend_api.models import (
        Base, User, Watchlist, StockRealtimeQuote, StockRealtimeQuoteHK,
    )

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__, Watchlist.__table__,
            StockRealtimeQuote.__table__, StockRealtimeQuoteHK.__table__,
        ],
    )
    Session = sessionmaker(bind=engine)

    base = datetime(2026, 9, 1, 9, 0, 0)
    with Session() as s:
        s.add_all([
            Watchlist(user_id=6, stock_code="600519", stock_name="贵州茅台",
                      group_name="default", created_at=base),
            Watchlist(user_id=6, stock_code="00700", stock_name="腾讯控股",
                      group_name="港股", created_at=base + timedelta(minutes=1)),
            # 同一代码出现在另一个分组：codes 接口应去重
            Watchlist(user_id=6, stock_code="600519", stock_name="贵州茅台",
                      group_name="白酒", created_at=base + timedelta(minutes=2)),
            Watchlist(user_id=6, stock_code="000001", stock_name="平安银行",
                      group_name="default", created_at=base + timedelta(minutes=3)),
            Watchlist(user_id=7, stock_code="300750", stock_name="宁德时代",
                      group_name="default", created_at=base),
        ])
        s.commit()

    def _get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(watchlist_manage.router)
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=6)
    with TestClient(app) as c:
        yield c


def test_codes_returns_dedup_codes_newest_first_for_current_user(client):
    resp = client.get("/api/watchlist/codes")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert [it["code"] for it in body["data"]] == ["000001", "600519", "00700"]
    first_600519 = next(it for it in body["data"] if it["code"] == "600519")
    assert first_600519["group_name"] == "白酒"
    assert set(body["data"][0].keys()) == {"code", "name", "group_name"}


def test_get_watchlist_limit_returns_newest_n_rows(client):
    resp = client.get("/api/watchlist?limit=2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert [it["code"] for it in body["data"]] == ["000001", "600519"]


def test_get_watchlist_without_limit_returns_all_rows(client):
    resp = client.get("/api/watchlist")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 4


def test_get_watchlist_rejects_invalid_limit(client):
    assert client.get("/api/watchlist?limit=0").status_code == 422
