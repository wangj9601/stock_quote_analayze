"""分析频道：龙头/中军加入 GMS 策略观察股 API 与服务。"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend_api.models import (
    GMSStrategyVersion,
    GMSStrategyVersionStock,
    StockBasicInfo,
)
from backend_api.services.gms_strategy_watchlist import (
    BOARD_ROLE_REMARK,
    add_gms_strategy_watchlist_stock,
    add_gms_strategy_watchlist_stocks_batch,
    ensure_gms_strategy_watchlist_stock,
    is_in_gms_strategy_watchlist,
)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    tables = [
        GMSStrategyVersion.__table__,
        GMSStrategyVersionStock.__table__,
        StockBasicInfo.__table__,
    ]
    for t in tables:
        t.create(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(
        GMSStrategyVersion(
            id=1,
            strategy_code="GMS",
            version_name="V1",
            version_no=1,
            is_active=True,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
    )
    session.add(StockBasicInfo(code="600519", name="贵州茅台"))
    session.add(StockBasicInfo(code="000001", name="平安银行"))
    session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_add_result_added_and_skipped(db):
    r1 = add_gms_strategy_watchlist_stock(
        db, market="CN", code="600519", name="贵州茅台", remark=BOARD_ROLE_REMARK
    )
    assert r1.status == "added"
    db.commit()
    r2 = add_gms_strategy_watchlist_stock(db, market="CN", code="600519")
    assert r2.status == "skipped"
    assert is_in_gms_strategy_watchlist(db, market="CN", code="600519")


def test_add_result_failed_invalid_code(db):
    r = add_gms_strategy_watchlist_stock(db, market="CN", code="")
    assert r.status == "failed"


def test_batch_add_dedupe_and_counts(db):
    summary = add_gms_strategy_watchlist_stocks_batch(
        db,
        [
            {"code": "600519", "name": "贵州茅台", "role": "leader"},
            {"code": "000001", "name": "平安银行", "role": "mid"},
            {"code": "600519", "name": "贵州茅台", "role": "leader"},
        ],
        remark=BOARD_ROLE_REMARK,
    )
    db.commit()
    assert summary["added"] == 2
    assert summary["skipped"] == 1
    assert summary["failed"] == 0
    assert summary["total"] == 3
    assert ensure_gms_strategy_watchlist_stock(db, market="CN", code="600519") is False
    row = (
        db.query(GMSStrategyVersionStock)
        .filter(GMSStrategyVersionStock.stock_code == "000001")
        .first()
    )
    assert row is not None
    assert row.remark == BOARD_ROLE_REMARK
    assert row.status == "active"


def test_batch_without_active_version_fails(db):
    db.query(GMSStrategyVersion).update({"is_active": False})
    db.commit()
    summary = add_gms_strategy_watchlist_stocks_batch(
        db, [{"code": "600519", "name": "贵州茅台"}]
    )
    assert summary["added"] == 0
    assert summary["failed"] == 1
    assert summary["items"][0]["message"]


def test_route_add_endpoint_success(db, monkeypatch):
    from backend_api.stock import board_analysis_routes as routes

    user = MagicMock()
    user.id = 1
    monkeypatch.setattr(routes, "_require_gms_strategy_watchlist_perm", lambda _db, _u: None)

    body = routes.GmsStrategyWatchlistAddRequest(
        stocks=[
            routes.GmsStrategyWatchlistStockItem(code="600519", name="贵州茅台", role="leader"),
            routes.GmsStrategyWatchlistStockItem(code="000001", name="平安银行", role="mid"),
        ],
        board_name="白酒",
    )
    resp = routes.add_gms_strategy_watchlist_from_analysis(body=body, db=db, user=user)
    assert resp["success"] is True
    assert resp["added"] == 2
    assert resp["skipped"] == 0
    assert "白酒" in (
        db.query(GMSStrategyVersionStock)
        .filter(GMSStrategyVersionStock.stock_code == "600519")
        .first()
        .remark
    )
