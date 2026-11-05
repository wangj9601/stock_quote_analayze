# -*- coding: utf-8 -*-
"""CSB 管理端预计算入场信号查询：list_admin_entry_signals + GET /signals。"""

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

from backend_api.models import CSBSignalTrace, CSBStrategyConfig
from backend_core.strategies.csb.config import CSB_STOCK_DAY_SCANNED, CSB_TRACE_SCANNED_MARKER

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
    CSBStrategyConfig.__table__.create(bind=engine)
    CSBSignalTrace.__table__.create(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(
        CSBStrategyConfig(
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
    score: float | None = None,
    name: str = "",
    signal_type: str = "CSB_BREAKOUT",
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    config_id: int = CONFIG_ID,
    trade_date: date = TRADE_D,
):
    ts = created_at or WRITTEN_AT
    db.add(
        CSBSignalTrace(
            code=code,
            trade_date=trade_date,
            config_id=config_id,
            signal_type=signal_type,
            name=name,
            entry_signal=entry_signal,
            score=score,
            created_at=ts,
            updated_at=updated_at or ts,
        )
    )


def test_list_admin_entry_signals_only_entries(db):
    from backend_core.strategies.csb.trace_store import list_admin_entry_signals

    _add_trace(db, code="000001", entry_signal=True, score=88.0, name="平安银行")
    _add_trace(db, code="000002", entry_signal=False, score=40.0, name="万科A")
    _add_trace(
        db,
        code=CSB_TRACE_SCANNED_MARKER,
        entry_signal=False,
        score=0.0,
        signal_type="SCANNED",
    )
    _add_trace(
        db,
        code="000003",
        entry_signal=False,
        score=10.0,
        signal_type=CSB_STOCK_DAY_SCANNED,
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
    assert out["last_written_at"]


def test_list_admin_entry_signals_pagination_and_meta(db):
    from backend_core.strategies.csb.trace_store import list_admin_entry_signals

    _add_trace(db, code="000001", entry_signal=True, score=90.0)
    _add_trace(db, code="000002", entry_signal=True, score=80.0)
    _add_trace(db, code="000003", entry_signal=True, score=70.0)
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
    assert page0["last_written_at"]
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
    assert page1["last_written_at"]


def test_list_admin_entry_signals_no_rows_has_any_false(db):
    from backend_core.strategies.csb.trace_store import list_admin_entry_signals

    out = list_admin_entry_signals(db, trade_date=TRADE_DATE, config_id=CONFIG_ID)
    assert out["items"] == []
    assert out["total"] == 0
    assert out["has_any_trace"] is False
    assert out["last_written_at"] is None


def test_list_admin_signals_route_400_when_no_config(monkeypatch):
    from backend_api.admin import csb_admin_routes
    from backend_api.database import get_db

    class _Mgr:
        def ensure_default_row(self, db):
            return None

        def list_precompute_config_ids(self, db):
            return []

        def get_config_row(self, db, config_id):
            return None

    monkeypatch.setattr(csb_admin_routes, "CSBConfigManager", _Mgr)
    monkeypatch.setattr(
        csb_admin_routes, "_resolve_effective_config_id", lambda db, mgr: None
    )
    monkeypatch.setattr(
        "backend_core.strategies.csb.scheduled_precompute.list_precompute_config_ids",
        lambda db: [],
    )

    app = FastAPI()
    app.include_router(csb_admin_routes.router)

    def _db():
        yield MagicMock()

    app.dependency_overrides[get_db] = _db
    client = TestClient(app)
    res = client.get("/api/admin/csb/signals", params={"trade_date": TRADE_DATE})
    assert res.status_code == 400
