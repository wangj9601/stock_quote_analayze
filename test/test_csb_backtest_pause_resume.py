# -*- coding: utf-8 -*-
"""CSB 回测协作式暂停 / 恢复。"""

from __future__ import annotations

import threading
import time

import pytest


def test_control_check_blocks_while_paused_then_resumes(monkeypatch):
    from backend_core.strategies.csb import backtest_storage, backtest_worker

    monkeypatch.setattr(backtest_storage, "get_task", lambda _tid: {"status": "running"})
    monkeypatch.setattr(backtest_worker, "_PAUSE_POLL_SEC", 0.05)

    tid = "pause-resume-unit-1"
    with backtest_worker._lock:
        backtest_worker._cancelled.discard(tid)
        backtest_worker._paused.discard(tid)

    backtest_worker.request_pause(tid)

    done = {"v": False}

    def run():
        assert backtest_worker.control_check(tid) is False
        done["v"] = True

    t = threading.Thread(target=run, daemon=True)
    t.start()
    time.sleep(0.12)
    assert done["v"] is False
    backtest_worker.request_resume(tid)
    t.join(timeout=2.0)
    assert done["v"] is True


def test_control_check_cancel_unblocks_pause(monkeypatch):
    from backend_core.strategies.csb import backtest_storage, backtest_worker

    monkeypatch.setattr(backtest_storage, "get_task", lambda _tid: {"status": "running"})
    monkeypatch.setattr(backtest_worker, "_PAUSE_POLL_SEC", 0.05)

    tid = "pause-cancel-unit-1"
    with backtest_worker._lock:
        backtest_worker._cancelled.discard(tid)
        backtest_worker._paused.discard(tid)

    backtest_worker.request_pause(tid)
    result = {"cancelled": None}

    def run():
        result["cancelled"] = backtest_worker.control_check(tid)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    time.sleep(0.12)
    backtest_worker.request_cancel(tid)
    t.join(timeout=2.0)
    assert result["cancelled"] is True
    with backtest_worker._lock:
        backtest_worker._cancelled.discard(tid)
        backtest_worker._paused.discard(tid)


def test_pause_task_only_from_running(monkeypatch):
    from backend_core.strategies.csb import backtest_storage

    class Row:
        def __init__(self, status):
            self.status = status
            self.message = ""
            self.logs = []
            self.completed_at = None

    class Q:
        def __init__(self, row):
            self._row = row

        def filter(self, *a, **k):
            return self

        def first(self):
            return self._row

    class Sess:
        def __init__(self, row):
            self._row = row
            self.committed = False

        def query(self, *a, **k):
            return Q(self._row)

        def commit(self):
            self.committed = True

        def rollback(self):
            pass

        def close(self):
            pass

    running = Row("running")
    sess = Sess(running)
    monkeypatch.setattr(backtest_storage, "_session", lambda: sess)
    assert backtest_storage.pause_task("t1") is True
    assert running.status == "paused"
    assert sess.committed is True

    completed = Row("completed")
    monkeypatch.setattr(backtest_storage, "_session", lambda: Sess(completed))
    assert backtest_storage.pause_task("t2") is False
    assert completed.status == "completed"


def test_resume_task_only_from_paused(monkeypatch):
    from backend_core.strategies.csb import backtest_storage

    class Row:
        def __init__(self, status):
            self.status = status
            self.message = ""
            self.logs = []

    class Q:
        def __init__(self, row):
            self._row = row

        def filter(self, *a, **k):
            return self

        def first(self):
            return self._row

    class Sess:
        def __init__(self, row):
            self._row = row

        def query(self, *a, **k):
            return Q(self._row)

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    paused = Row("paused")
    monkeypatch.setattr(backtest_storage, "_session", lambda: Sess(paused))
    assert backtest_storage.resume_task("t1") is True
    assert paused.status == "running"

    running = Row("running")
    monkeypatch.setattr(backtest_storage, "_session", lambda: Sess(running))
    assert backtest_storage.resume_task("t2") is False
    assert running.status == "running"


@pytest.mark.asyncio
async def test_pause_resume_api_routes(monkeypatch):
    from backend_api.admin import csb_admin_routes as routes

    calls = {"pause": None, "resume": None, "storage_pause": None, "storage_resume": None}

    monkeypatch.setattr(
        "backend_core.strategies.csb.backtest_worker.request_pause",
        lambda tid: calls.__setitem__("pause", tid),
    )
    monkeypatch.setattr(
        "backend_core.strategies.csb.backtest_worker.request_resume",
        lambda tid: calls.__setitem__("resume", tid),
    )
    monkeypatch.setattr(
        "backend_core.strategies.csb.backtest_storage.pause_task",
        lambda tid: calls.__setitem__("storage_pause", tid) or True,
    )
    monkeypatch.setattr(
        "backend_core.strategies.csb.backtest_storage.resume_task",
        lambda tid: calls.__setitem__("storage_resume", tid) or True,
    )
    monkeypatch.setattr(
        "backend_core.strategies.csb.backtest_storage.get_task",
        lambda tid: {"task_id": tid, "status": "paused"},
    )

    r1 = await routes.pause_backtest("task-abc")
    r2 = await routes.resume_backtest("task-abc")
    assert r1["success"] is True
    assert r2["success"] is True
    assert calls["pause"] == "task-abc"
    assert calls["resume"] == "task-abc"
    assert calls["storage_pause"] == "task-abc"
    assert calls["storage_resume"] == "task-abc"
