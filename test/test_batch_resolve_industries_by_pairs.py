"""batch_resolve_industries_by_pairs 单元测试。"""

from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend_api.gms_trade_observe_routes import batch_resolve_industries_by_pairs
from backend_api.models import (
    Base,
    IndustryBoardConstituent,
    StockBasicInfo,
)


def test_batch_resolve_industries_by_pairs_cn_board_first_and_skip_nan():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS industry_board_basic_info (
                    board_code TEXT PRIMARY KEY,
                    board_name TEXT
                )
                """
            )
        )
        db.add(StockBasicInfo(code="000566", name="海南海药", industry="nan"))
        db.add(IndustryBoardConstituent(board_code="BK0479", stock_code="000566", stock_name="海南海药"))
        db.execute(
            text(
                "INSERT INTO industry_board_basic_info (board_code, board_name) VALUES ('BK0479', '化学制药')"
            )
        )
        db.commit()
        out = batch_resolve_industries_by_pairs(db, [("CN", "000566"), ("CN", "999999")])
        assert out[("CN", "000566")] == "化学制药"
        assert ("CN", "999999") not in out
    finally:
        db.close()
        engine.dispose()


def test_batch_resolve_industries_by_pairs_cn_fallback_basic_info():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        db.add(StockBasicInfo(code="600519", name="贵州茅台", industry="白酒"))
        db.commit()
        with patch(
            "backend_api.gms_trade_observe_routes.batch_industry_board_names_by_stock_codes",
            return_value={},
        ):
            out = batch_resolve_industries_by_pairs(db, [("CN", "600519")])
        assert out[("CN", "600519")] == "白酒"
    finally:
        db.close()
        engine.dispose()
