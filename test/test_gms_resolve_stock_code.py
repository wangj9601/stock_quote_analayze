"""GMS 单股查询：代码/名称解析"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend_api.models import Base, StockBasicInfo
from backend_api.stock.stock_screening_routes import (
    _normalize_stock_code_for_gms_pool,
    _resolve_gms_stock_code_from_input,
)

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def test_db():
    engine = create_engine(TEST_DATABASE_URL, echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(StockBasicInfo(code="000001", name="平安银行"))
    db.commit()
    yield db
    db.close()
    Base.metadata.drop_all(engine)


def test_normalize_hk_code():
    assert _normalize_stock_code_for_gms_pool("700") == "00700"


def test_resolve_by_code(test_db):
    assert _resolve_gms_stock_code_from_input(test_db, "000001") == "000001"


def test_resolve_by_name(test_db):
    assert _resolve_gms_stock_code_from_input(test_db, "平安银行") == "000001"


def test_resolve_missing(test_db):
    assert _resolve_gms_stock_code_from_input(test_db, "不存在的股票") is None
