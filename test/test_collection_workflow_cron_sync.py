"""采集流程 cron 热同步单元测试。"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from backend_core.data_collectors.workflow import cron_sync


def setup_function():
    cron_sync.reset_sync_state_for_tests()


def test_build_cron_signature_stable_and_sensitive():
    t = datetime(2026, 9, 17, 15, 38, 0)
    a = SimpleNamespace(
        id=1,
        enabled=True,
        trigger_type="cron",
        cron_dow="mon-fri",
        cron_hour="15",
        cron_minute=38,
        skip_on_holiday="CN",
        updated_at=t,
    )
    b = SimpleNamespace(**{**a.__dict__, "cron_minute": 40})
    c = SimpleNamespace(**{**a.__dict__, "updated_at": datetime(2026, 9, 17, 15, 39, 0)})
    s1 = cron_sync.build_cron_signature([a])
    s2 = cron_sync.build_cron_signature([a])
    assert s1 == s2
    assert s1 != cron_sync.build_cron_signature([b])
    assert s1 != cron_sync.build_cron_signature([c])


def test_reload_skips_when_signature_unchanged():
    row = SimpleNamespace(
        id=7,
        name="wf",
        enabled=True,
        trigger_type="cron",
        cron_dow="mon-fri",
        cron_hour="15",
        cron_minute=38,
        skip_on_holiday="CN",
        updated_at=datetime(2026, 9, 17, 15, 0, 0),
    )
    scheduler = MagicMock()
    scheduler.get_jobs.return_value = []
    scheduler.get_job.return_value = None

    def factory():
        db = MagicMock()
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.all.return_value = [row]
        db.query.return_value = q
        return db

    start_fn = MagicMock(return_value="cwr_x")
    changed, msg = cron_sync.reload_workflow_cron_jobs(
        scheduler, factory, start_fn=start_fn, force=True
    )
    assert changed is True
    assert "registered=1" in msg
    assert scheduler.add_job.call_count == 1

    changed2, msg2 = cron_sync.reload_workflow_cron_jobs(
        scheduler, factory, start_fn=start_fn, force=False
    )
    assert changed2 is False
    assert msg2 == "unchanged"
    assert scheduler.add_job.call_count == 1


def test_sync_defers_when_db_has_running():
    row = SimpleNamespace(
        id=1,
        name="wf",
        enabled=True,
        trigger_type="cron",
        cron_dow="mon-fri",
        cron_hour="15",
        cron_minute=38,
        skip_on_holiday="CN",
        updated_at=datetime(2026, 9, 17, 16, 0, 0),
    )
    scheduler = MagicMock()
    scheduler.get_jobs.return_value = []
    scheduler.get_job.return_value = None

    call_n = {"n": 0}

    def factory():
        call_n["n"] += 1
        db = MagicMock()
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.limit.return_value = q
        # first call(s): load cron rows; later: running check
        if call_n["n"] <= 1:
            q.all.return_value = [row]
            q.first.return_value = None
        else:
            q.all.return_value = [row]
            q.first.return_value = ("cwr_busy",)
        db.query.return_value = q
        return db

    # seed last signature as empty so sync sees change
    cron_sync.reset_sync_state_for_tests()
    changed, msg = cron_sync.sync_workflow_cron_if_idle(
        scheduler, factory, start_fn=MagicMock(), local_busy_check=lambda: False
    )
    # Depending on call order, may reload or busy — force busy path explicitly
    cron_sync.reset_sync_state_for_tests()

    def factory_busy():
        db = MagicMock()
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.limit.return_value = q
        q.all.return_value = [row]
        q.first.return_value = ("cwr_busy",)  # has running
        db.query.return_value = q
        return db

    # Set signature different by first computing empty then busy
    with cron_sync._lock:
        cron_sync._last_signature = "old"
    changed, msg = cron_sync.sync_workflow_cron_if_idle(
        scheduler, factory_busy, start_fn=MagicMock(), local_busy_check=lambda: False
    )
    assert changed is False
    assert msg == "busy_db"
    assert scheduler.add_job.call_count == 0


def test_sync_defers_when_local_busy():
    row = SimpleNamespace(
        id=2,
        name="wf2",
        enabled=True,
        trigger_type="cron",
        cron_dow="mon-fri",
        cron_hour="15",
        cron_minute=0,
        skip_on_holiday="NONE",
        updated_at=datetime(2026, 9, 17, 16, 1, 0),
    )
    scheduler = MagicMock()

    def factory():
        db = MagicMock()
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.limit.return_value = q
        q.all.return_value = [row]
        q.first.return_value = None
        db.query.return_value = q
        return db

    with cron_sync._lock:
        cron_sync._last_signature = "old"
    changed, msg = cron_sync.sync_workflow_cron_if_idle(
        scheduler, factory, start_fn=MagicMock(), local_busy_check=lambda: True
    )
    assert changed is False
    assert msg == "busy_local"
