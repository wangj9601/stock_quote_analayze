"""batch_resolve_industries_by_pairs 单元测试。"""

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend_api.gms_trade_observe_routes import batch_resolve_industries_by_pairs
from backend_api.models import StockBasicInfo


def test_batch_resolve_industries_by_pairs_cn():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    StockBasicInfo.__table__.create(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        db.add(StockBasicInfo(code="000566", name="海南海药", industry="化学制药"))
        db.commit()
        out = batch_resolve_industries_by_pairs(db, [("CN", "000566"), ("CN", "999999")])
        assert out[("CN", "000566")] == "化学制药"
        assert ("CN", "999999") not in out
    finally:
        db.close()
        engine.dispose()
