# -*- coding: utf-8 -*-
"""URT 管理端预计算买点查询：list_admin_buy_signals + GET /signals。"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_api.models import URTSignalTrace, URTStrategyConfig
from backend_core.strategies.urt.trace_store import URT_TRACE_SCANNED_MARKER

TRADE_DATE = "2026-11-04"
CONFIG_ID = 1


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    URTStrategyConfig.__table__.create(bind=engine)
    URTSignalTrace.__table__.create(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(
        URTStrategyConfig(
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
    buy_signal: bool,
    score: float | None = None,
    name: str = "",
    created_at: datetime | None = None,
    config_id: int = CONFIG_ID,
    date: str = TRADE_DATE,
):
    db.add(
        URTSignalTrace(
            code=code,
            date=date,
            config_id=config_id,
            name=name,
            buy_signal=buy_signal,
            score=score,
            created_at=created_at or datetime(2026, 11, 4, 18, 0, 0),
        )
    )


def test_list_admin_buy_signals_filters_market_and_non_buys(db):
    from backend_core.strategies.urt.trace_store import list_admin_buy_signals

    _add_trace(db, code="000001", buy_signal=True, score=88.0, name="平安银行")
    _add_trace(db, code="00700", buy_signal=True, score=95.0, name="腾讯控股")
    _add_trace(db, code="000002", buy_signal=False, score=40.0, name="万科A")
    _add_trace(db, code=URT_TRACE_SCANNED_MARKER, buy_signal=False, score=0.0)
    db.commit()

    out = list_admin_buy_signals(
        db, trade_date=TRADE_DATE, config_id=CONFIG_ID, market="CN"
    )
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
    assert out["last_written_at"]

    hk = list_admin_buy_signals(
        db, trade_date=TRADE_DATE, config_id=CONFIG_ID, market="HK"
    )
    assert hk["total"] == 1
    assert [row["code"] for row in hk["items"]] == ["00700"]


def test_list_admin_buy_signals_pagination(db):
    from backend_core.strategies.urt.trace_store import list_admin_buy_signals

    _add_trace(db, code="000001", buy_signal=True, score=90.0)
    _add_trace(db, code="000002", buy_signal=True, score=80.0)
    _add_trace(db, code="000003", buy_signal=True, score=70.0)
    db.commit()

    page0 = list_admin_buy_signals(
        db,
        trade_date=TRADE_DATE,
        config_id=CONFIG_ID,
        market="CN",
        limit=2,
        offset=0,
    )
    assert page0["total"] == 3
    assert [row["code"] for row in page0["items"]] == ["000001", "000002"]

    page1 = list_admin_buy_signals(
        db,
        trade_date=TRADE_DATE,
        config_id=CONFIG_ID,
        market="CN",
        limit=2,
        offset=2,
    )
    assert page1["total"] == 3
    assert [row["code"] for row in page1["items"]] == ["000003"]


def test_list_admin_buy_signals_empty_with_scanned_only(db):
    from backend_core.strategies.urt.trace_store import list_admin_buy_signals

    _add_trace(db, code=URT_TRACE_SCANNED_MARKER, buy_signal=False, score=0.0)
    db.commit()

    out = list_admin_buy_signals(
        db, trade_date=TRADE_DATE, config_id=CONFIG_ID, market="CN"
    )
    assert out["items"] == []
    assert out["total"] == 0
    assert out["has_any_trace"] is True

    hk_only_marker = list_admin_buy_signals(
        db, trade_date=TRADE_DATE, config_id=CONFIG_ID, market="HK"
    )
    assert hk_only_marker["items"] == []
    assert hk_only_marker["total"] == 0
    assert hk_only_marker["has_any_trace"] is True


def test_list_admin_buy_signals_hk_ignores_cn_rows_and_shared_marker(db):
    """仅有 A 股买点与共享扫描占位时，港股查询不得把占位算成已扫描。"""
    from backend_core.strategies.urt.trace_store import list_admin_buy_signals

    cn_written = datetime(2026, 11, 4, 18, 0, 0)
    marker_written = datetime(2026, 11, 4, 23, 30, 0)
    _add_trace(
        db,
        code="000001",
        buy_signal=True,
        score=88.0,
        name="平安银行",
        created_at=cn_written,
    )
    _add_trace(
        db,
        code=URT_TRACE_SCANNED_MARKER,
        buy_signal=False,
        score=0.0,
        created_at=marker_written,
    )
    db.commit()

    hk = list_admin_buy_signals(
        db, trade_date=TRADE_DATE, config_id=CONFIG_ID, market="HK"
    )
    assert hk["items"] == []
    assert hk["total"] == 0
    assert hk["has_any_trace"] is False
    assert hk["last_written_at"] is None

    cn = list_admin_buy_signals(
        db, trade_date=TRADE_DATE, config_id=CONFIG_ID, market="CN"
    )
    assert cn["total"] == 1
    assert [row["code"] for row in cn["items"]] == ["000001"]
    assert cn["has_any_trace"] is True
    assert cn["last_written_at"] == cn_written.isoformat()


def test_list_admin_signals_route_400_when_no_config(monkeypatch):
    from backend_api.admin import urt_admin_routes
    from backend_api.database import get_db

    class _Mgr:
        def ensure_default_row(self, db):
            return None

        def resolve_effective_config_id(self, db):
            return None

        def list_precompute_config_ids(self, db):
            return []

    monkeypatch.setattr(urt_admin_routes, "URTConfigManager", _Mgr)
    monkeypatch.setattr(
        "backend_core.strategies.urt.scheduled_precompute.list_precompute_config_ids",
        lambda db: [],
    )

    app = FastAPI()
    app.include_router(urt_admin_routes.router)

    def _db():
        yield MagicMock()

    app.dependency_overrides[get_db] = _db
    client = TestClient(app)
    res = client.get("/api/admin/urt/signals", params={"trade_date": TRADE_DATE})
    assert res.status_code == 400
