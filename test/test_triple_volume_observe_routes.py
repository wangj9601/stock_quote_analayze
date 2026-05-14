"""
日终爆量观察股：导出列与选股页「观察股池 → 日终爆量」表格一致。
"""

from __future__ import annotations

from datetime import date, datetime
from io import BytesIO

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend_api.auth import get_current_user_or_admin
from backend_api.database import get_db
from backend_api.models import TripleVolumeObserveStock, User
from backend_api.triple_volume_observe_routes import router


@pytest.fixture
def memory_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    User.__table__.create(bind=engine)
    TripleVolumeObserveStock.__table__.create(bind=engine)
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
        username="tvo_tester",
        email="tvo_tester@example.com",
        password_hash="x",
        role="user",
        status="active",
    )
    memory_db.add(u)
    memory_db.commit()
    memory_db.refresh(u)
    return u


@pytest.fixture
def tvo_sample(memory_db):
    r = TripleVolumeObserveStock(
        market="CN",
        code="300018",
        name="中元股份",
        observe_trade_date=date(2024, 5, 13),
        prev_trade_date=date(2024, 5, 11),
        prev_volume=186700.0,
        curr_volume=592700.0,
        volume_ratio_actual=3.174,
        status="待观察",
        vsb_evaluated_at=None,
        vsb_detail_json={"k": "v"},
        created_at=datetime(2024, 5, 13, 20, 0, 0),
        updated_at=datetime(2024, 5, 13, 21, 48, 40),
    )
    memory_db.add(r)
    memory_db.commit()
    memory_db.refresh(r)
    return r


@pytest.fixture
def export_client(memory_db, test_user):
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


EXPECTED_EXPORT_COLUMNS = [
    "市场",
    "代码",
    "名称",
    "观察日",
    "前交易日",
    "前日量",
    "当日量",
    "量比",
    "状态",
    "复核时间",
    "更新时间",
]


def test_export_columns_match_observe_pool_table(export_client, tvo_sample):
    res = export_client.get("/api/stock/triple-volume-observe/export")
    assert res.status_code == 200
    df = pd.read_excel(BytesIO(res.content), sheet_name="观察股")
    assert list(df.columns) == EXPECTED_EXPORT_COLUMNS
    assert len(df) == 1
    row = df.iloc[0]
    code_cell = str(row["代码"]).strip()
    if "." in code_cell:
        code_cell = code_cell.split(".")[0]
    assert code_cell == "300018"
    assert str(row["观察日"]).startswith("2024-05-13")
    assert str(row["前交易日"]).startswith("2024-05-11")
    assert abs(float(row["前日量"]) - 186700.0) < 1e-6
    assert abs(float(row["当日量"]) - 592700.0) < 1e-6
    assert abs(float(row["量比"]) - 3.17) < 0.001
    assert row["状态"] == "待观察"
    assert row["复核时间"] == "" or pd.isna(row["复核时间"])
