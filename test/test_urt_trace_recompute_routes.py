"""URT 信号历史强制重算：任务表 CRUD 与路由辅助函数。"""

import sys
import os

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_api.database import SessionLocal, engine
from backend_api.models import UrtTraceRecomputeTask
from backend_api.stock import urt_frontend_routes as urt_routes


@pytest.fixture()
def recompute_task_db():
    UrtTraceRecomputeTask.__table__.create(bind=engine, checkfirst=True)
    urt_routes._trace_recompute_table_ready = True
    db = SessionLocal()
    try:
        db.query(UrtTraceRecomputeTask).delete()
        db.commit()
        yield db
    finally:
        db.query(UrtTraceRecomputeTask).delete()
        db.commit()
        db.close()
        urt_routes._trace_recompute_table_ready = False


def test_find_running_trace_recompute(recompute_task_db):
    urt_routes._create_trace_recompute_task(
        "urt_t1",
        {
            "status": "running",
            "progress": 10,
            "message": "calc",
            "code": "000676",
            "config_id": 1,
            "config_name": "default",
            "current": 1,
            "total": 10,
        },
    )
    assert urt_routes._find_running_trace_recompute("000676", 1) == "urt_t1"
    assert urt_routes._find_running_trace_recompute("000676", 2) is None


def test_update_and_get_trace_recompute_task(recompute_task_db):
    task_id = "urt_t2"
    urt_routes._create_trace_recompute_task(
        task_id,
        {
            "status": "pending",
            "progress": 0,
            "message": "created",
            "code": "000001",
            "config_id": 1,
            "config_name": "default",
            "current": 0,
            "total": 0,
        },
    )
    urt_routes._update_trace_recompute_task(
        task_id,
        status="completed",
        progress=100,
        saved_count=12,
        message="done",
    )
    task = urt_routes._get_trace_recompute_task(task_id)
    assert task is not None
    assert task["status"] == "completed"
    assert task["saved_count"] == 12
    assert urt_routes._get_trace_recompute_task("missing") is None


def test_normalize_code():
    assert urt_routes._normalize_code("676") == "000676"
    assert urt_routes._normalize_code("000676") == "000676"
