# -*- coding: utf-8 -*-
"""RPE 管理端只读预计算入场信号：list_admin_entry_signals + GET /signals。"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_api.models import RPESignalTrace, RPEStrategyConfig

TRADE_DATE = "2026-11-04"
TRADE_D = date(2026, 11, 4)
CONFIG_ID = 1
WRITTEN_AT = datetime(2026, 11, 4, 18, 0, 0)


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    RPEStrategyConfig.__table__.create(bind=engine)
    RPESignalTrace.__table__.create(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(
        RPEStrategyConfig(
            id=CONFIG_ID,
            name="admin-signals-test",
            config_params={},
            is_active=True,
            is_default=True,
            precompute_enabled=True,
        )
    )
    session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _add_trace(
    db,
    *,
    code: str,
    entry_signal: bool,
    z_score: float | None = None,
    name: str = "",
    signal_type: str | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    config_id: int = CONFIG_ID,
    trade_date: date = TRADE_D,
    ratio: float | None = None,
    sector_name: str | None = None,
    close_price: float | None = None,
):
    ts = created_at or WRITTEN_AT
    db.add(
        RPESignalTrace(
            code=code,
            trade_date=trade_date,
            market_type="CN",
            config_id=config_id,
            name=name,
            signal_type=signal_type,
            entry_signal=entry_signal,
            z_score=z_score,
            ratio=ratio,
            sector_name=sector_name,
            close_price=close_price,
            created_at=ts,
            updated_at=updated_at or ts,
        )
    )


def test_rpe_list_admin_entry_signals_entry_only(db):
    from backend_core.strategies.rpe.signal_storage import list_admin_entry_signals

    _add_trace(
        db,
        code="000001",
        entry_signal=True,
        z_score=-2.1,
        name="平安银行",
        signal_type="catch_up",
        sector_name="银行",
        close_price=10.5,
    )
    _add_trace(
        db,
        code="000002",
        entry_signal=False,
        z_score=-0.2,
        name="万科A",
        signal_type="in_band",
    )
    _add_trace(
        db,
        code="000003",
        entry_signal=False,
        z_score=None,
        name="扫描占位",
        signal_type=None,
    )
    db.commit()

    out = list_admin_entry_signals(db, trade_date=TRADE_DATE, config_id=CONFIG_ID)
    assert set(out.keys()) >= {
        "items",
        "total",
        "trade_date",
        "config_id",
        "last_written_at",
        "has_any_trace",
    }
    assert out["trade_date"] == TRADE_DATE
    assert out["config_id"] == CONFIG_ID
    assert out["has_any_trace"] is True
    assert out["total"] == 1
    assert [row["code"] for row in out["items"]] == ["000001"]
    assert out["items"][0]["entry_signal"] is True
    assert out["items"][0]["signal_type"] == "catch_up"
    assert out["last_written_at"]


def test_rpe_list_admin_entry_signals_pagination(db):
    from backend_core.strategies.rpe.signal_storage import list_admin_entry_signals

    _add_trace(db, code="000001", entry_signal=True, z_score=-2.4, signal_type="catch_up")
    _add_trace(db, code="000002", entry_signal=True, z_score=-1.9, signal_type="catch_up")
    _add_trace(db, code="000003", entry_signal=True, z_score=-1.6, signal_type="catch_up")
    db.commit()

    page0 = list_admin_entry_signals(
        db,
        trade_date=TRADE_DATE,
        config_id=CONFIG_ID,
        limit=2,
        offset=0,
    )
    assert page0["total"] == 3
    assert [row["code"] for row in page0["items"]] == ["000001", "000002"]
    assert page0["has_any_trace"] is True

    page1 = list_admin_entry_signals(
        db,
        trade_date=TRADE_DATE,
        config_id=CONFIG_ID,
        limit=2,
        offset=2,
    )
    assert page1["total"] == 3
    assert [row["code"] for row in page1["items"]] == ["000003"]


def test_rpe_admin_path_does_not_require_live_screen(db, monkeypatch):
    from backend_api.admin import rpe_admin_routes
    from backend_api.auth import get_current_admin
    from backend_api.database import get_db
    from backend_core.strategies.rpe.strategy_engine import RPEStrategyEngine

    _add_trace(
        db,
        code="000001",
        entry_signal=True,
        z_score=-2.0,
        name="平安银行",
        signal_type="catch_up",
    )
    db.commit()

    calls = {"screen": 0}

    def _boom(*_args, **_kwargs):
        calls["screen"] += 1
        raise AssertionError("RPEStrategyEngine.screen must not be called")

    monkeypatch.setattr(RPEStrategyEngine, "screen", _boom)

    app = FastAPI()
    app.include_router(rpe_admin_routes.router)

    def _yield_db():
        yield db

    app.dependency_overrides[get_db] = _yield_db
    app.dependency_overrides[get_current_admin] = lambda: MagicMock()
    app.dependency_overrides[rpe_admin_routes._require_admin] = lambda: MagicMock()

    client = TestClient(app)
    res = client.get(
        "/api/admin/rpe/signals",
        params={"trade_date": TRADE_DATE, "config_id": CONFIG_ID},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert [row["code"] for row in body["items"]] == ["000001"]
    assert body["has_any_trace"] is True
    assert calls["screen"] == 0


def test_rpe_admin_signals_bad_trade_date_returns_400(db):
    from backend_api.admin import rpe_admin_routes
    from backend_api.auth import get_current_admin
    from backend_api.database import get_db

    app = FastAPI()
    app.include_router(rpe_admin_routes.router)

    def _yield_db():
        yield db

    app.dependency_overrides[get_db] = _yield_db
    app.dependency_overrides[get_current_admin] = lambda: MagicMock()
    app.dependency_overrides[rpe_admin_routes._require_admin] = lambda: MagicMock()

    client = TestClient(app)
    res = client.get(
        "/api/admin/rpe/signals",
        params={"trade_date": "not-a-date", "config_id": CONFIG_ID},
    )
    assert res.status_code == 400
