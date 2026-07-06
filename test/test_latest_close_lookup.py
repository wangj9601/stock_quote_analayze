"""latest_close_lookup 单元测试（内存 SQLite）。"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend_api.models import HistoricalQuotes, StockRealtimeQuote
from backend_api.utils.latest_close_lookup import batch_lookup_latest_closes


@pytest.fixture
def memory_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    HistoricalQuotes.__table__.create(bind=engine)
    StockRealtimeQuote.__table__.create(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_prefers_realtime_over_historical(memory_db):
    memory_db.add(
        HistoricalQuotes(code="600519", date=date(2026, 6, 24), close=1720.5)
    )
    memory_db.add(
        StockRealtimeQuote(
            code="600519",
            trade_date="2026-06-25",
            current_price=1750.0,
        )
    )
    memory_db.commit()

    result = batch_lookup_latest_closes(memory_db, [("CN", "600519")])
    close, qdate = result[("CN", "600519")]
    assert close == 1750.0
    assert qdate == "2026-06-25"


def test_falls_back_to_historical_when_realtime_missing(memory_db):
    memory_db.add(
        HistoricalQuotes(code="600519", date=date(2026, 6, 20), close=1688.0)
    )
    memory_db.add(
        HistoricalQuotes(code="600519", date=date(2026, 6, 24), close=1720.5)
    )
    memory_db.commit()

    result = batch_lookup_latest_closes(memory_db, [("CN", "600519")])
    close, qdate = result[("CN", "600519")]
    assert close == 1720.5
    assert qdate == "2026-06-24"
