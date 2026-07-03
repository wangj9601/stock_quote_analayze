"""GMS 信号追溯：强制重算异步任务与进度（DB 持久化）"""

import os
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_api.models import GmsTraceRecomputeTask
from backend_api.stock import gms_trace_routes


@pytest.fixture
def trace_task_db(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    GmsTraceRecomputeTask.__table__.create(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    monkeypatch.setattr(gms_trace_routes, "SessionLocal", Session)
    monkeypatch.setattr(gms_trace_routes, "engine", engine)
    gms_trace_routes._trace_recompute_table_ready = True

    db = Session()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


class TestGmsTraceRecomputeTasks:
    def setup_method(self):
        gms_trace_routes._trace_recompute_table_ready = False

    def test_find_running_trace_recompute(self, trace_task_db):
        trace_task_db.add(
            GmsTraceRecomputeTask(
                task_id="t1",
                status="running",
                code="002106",
                config_id=1,
                progress=10,
            )
        )
        trace_task_db.commit()
        assert gms_trace_routes._find_running_trace_recompute("002106", 1) == "t1"
        assert gms_trace_routes._find_running_trace_recompute("002106", 2) is None

    def test_get_trace_recompute_task_missing(self, trace_task_db):
        assert gms_trace_routes._get_trace_recompute_task("missing") is None

    def test_create_and_update_task(self, trace_task_db):
        task_id = "test_task_1"
        gms_trace_routes._create_trace_recompute_task(task_id, {
            "task_id": task_id,
            "status": "pending",
            "progress": 0,
            "code": "002106",
            "market_type": "CN",
            "config_id": 1,
            "message": "等待",
        })
        gms_trace_routes._update_trace_recompute_task(
            task_id,
            status="running",
            progress=50,
            message="计算中",
            current=2,
            total=4,
        )
        gms_trace_routes._update_trace_recompute_task(
            task_id,
            status="completed",
            progress=100,
            saved_count=3,
            message="完成",
        )
        task = gms_trace_routes._get_trace_recompute_task(task_id)
        assert task["status"] == "completed"
        assert task["progress"] == 100
        assert task["saved_count"] == 3
