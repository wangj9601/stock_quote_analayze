"""
VSB 选股观察股 API：display_status 计算与列表接口（内存 SQLite + 依赖覆盖）。
"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend_api.auth import get_current_user_or_admin
from backend_api.database import get_db
from backend_api.models import User, VsbObserveStock
from backend_api.vsb_observe_stocks_routes import _display_status, router


@pytest.fixture
def memory_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    User.__table__.create(bind=engine)
    VsbObserveStock.__table__.create(bind=engine)
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
        username="vsb_observe_tester",
        email="vsb_observe_tester@example.com",
        password_hash="x",
        role="user",
        status="active",
    )
    memory_db.add(u)
    memory_db.commit()
    memory_db.refresh(u)
    return u


@pytest.fixture
def sample_row(memory_db, test_user):
    r = VsbObserveStock(
        market="CN",
        code="300825",
        name="阿尔特",
        signal_date=date(2026, 5, 8),
        boom_date="2026-04-29",
        run_search_date="2026-05-08",
        signal_strength=86,
        signal_strength_level="强(预)",
        buy_signal_text="买点摘要",
        screen_snapshot_json={"strategy_phase": "three_phase_v1", "volume_ratio": 3},
        created_at=datetime(2026, 5, 12, 14, 27, 26),
        updated_at=datetime(2026, 5, 12, 14, 27, 26),
    )
    memory_db.add(r)
    memory_db.commit()
    memory_db.refresh(r)
    return r


@pytest.fixture
def list_client(memory_db, test_user):
    app = FastAPI()
    app.include_router(router)

    def override_db():
        try:
            yield memory_db
        finally:
            pass

    def override_principal():
        return test_user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_or_admin] = override_principal
    return TestClient(app)


def test_display_status_three_phase_and_level():
    r = VsbObserveStock(
        market="CN",
        code="1",
        name=None,
        signal_date=date(2026, 1, 1),
        signal_strength_level="强(预)",
        screen_snapshot_json={"strategy_phase": "three_phase_v1"},
    )
    assert _display_status(r) == "三阶段 · 强(预)"


def test_display_status_legacy():
    r = VsbObserveStock(
        market="CN",
        code="1",
        name=None,
        signal_date=date(2026, 1, 1),
        signal_strength_level="中",
        screen_snapshot_json={"strategy_phase": "legacy"},
    )
    assert _display_status(r) == "旧版 · 中"


def test_display_status_unknown_phase_uses_raw():
    r = VsbObserveStock(
        market="CN",
        code="1",
        name=None,
        signal_date=date(2026, 1, 1),
        signal_strength_level="",
        screen_snapshot_json={"strategy_phase": "custom_x"},
    )
    assert _display_status(r) == "custom_x"


def test_display_status_no_snapshot_only_level():
    r = VsbObserveStock(
        market="CN",
        code="1",
        name=None,
        signal_date=date(2026, 1, 1),
        signal_strength_level="强",
        screen_snapshot_json=None,
    )
    assert _display_status(r) == "强"


def test_display_status_fallback_strategy_hit():
    r = VsbObserveStock(
        market="CN",
        code="1",
        name=None,
        signal_date=date(2026, 1, 1),
        signal_strength_level=None,
        screen_snapshot_json={},
    )
    assert _display_status(r) == "策略命中"


def test_list_returns_display_status(list_client, sample_row):
    res = list_client.get("/api/stock/vsb-observe-stocks/list?page=1&page_size=50")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["code"] == "300825"
    assert item["display_status"] == "三阶段 · 强(预)"


def test_list_market_filter_cn(list_client, sample_row):
    res = list_client.get("/api/stock/vsb-observe-stocks/list?page=1&page_size=50&market=CN")
    assert res.status_code == 200
    assert res.json()["total"] == 1

    res2 = list_client.get("/api/stock/vsb-observe-stocks/list?page=1&page_size=50&market=HK")
    assert res2.status_code == 200
    assert res2.json()["total"] == 0
