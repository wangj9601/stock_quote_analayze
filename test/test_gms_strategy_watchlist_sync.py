"""GMS 策略观察股同步服务单元测试。"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend_api.models import (
    Base,
    GMSStrategyVersion,
    GMSStrategyVersionStock,
    StockBasicInfo,
)
from backend_api.services.gms_strategy_watchlist import (
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
    session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_ensure_writes_when_missing(db):
    assert not is_in_gms_strategy_watchlist(db, market="CN", code="600519")
    created = ensure_gms_strategy_watchlist_stock(db, market="CN", code="600519", name="贵州茅台")
    assert created is True
    db.commit()
    row = (
        db.query(GMSStrategyVersionStock)
        .filter(
            GMSStrategyVersionStock.version_id == 1,
            GMSStrategyVersionStock.stock_code == "600519",
        )
        .first()
    )
    assert row is not None
    assert row.market == "A"
    assert row.status == "active"
    assert row.remark == "交易观察自动加入"


def test_ensure_skips_when_exists(db):
    db.add(
        GMSStrategyVersionStock(
            version_id=1,
            market="A",
            stock_code="600519",
            stock_name="贵州茅台",
            status="active",
        )
    )
    db.commit()
    created = ensure_gms_strategy_watchlist_stock(db, market="CN", code="600519")
    assert created is False
