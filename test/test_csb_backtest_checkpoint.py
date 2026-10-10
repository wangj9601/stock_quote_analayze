# -*- coding: utf-8 -*-
"""CSB 回测持久化检查点 / 重启后从 paused 续跑。"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


def test_save_and_get_checkpoint(monkeypatch):
    from backend_core.strategies.csb import backtest_storage

    stored: Dict[str, Any] = {"config": {"start_date": "2024-01-01"}, "status": "running"}

    class Row:
        def __init__(self):
            self.config = stored["config"]
            self.status = stored["status"]
            self.details_csv_bytes = None
            self.logs = []
            self.message = ""
            self.progress = 13

    row = Row()

    class Q:
        def filter(self, *a, **k):
            return self

        def first(self):
            return row

    class Sess:
        def query(self, *a, **k):
            return Q()

        def commit(self):
            stored["config"] = dict(row.config)

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(backtest_storage, "_session", lambda: Sess())
    monkeypatch.setattr(
        backtest_storage,
        "get_task",
        lambda _tid: {"task_id": "t1", "config": stored["config"], "status": row.status},
    )

    assert backtest_storage.save_checkpoint(
        "t1",
        {
            "phase": "precompute",
            "precompute_stock_offset": 1680,
            "backtest_date_index": 0,
            "cooldown": {},
            "precompute_meta": {"missing_before": 47},
        },
    )
    cp = backtest_storage.get_checkpoint("t1")
    assert cp["phase"] == "precompute"
    assert cp["precompute_stock_offset"] == 1680


def test_partial_details_roundtrip(monkeypatch):
    from backend_core.strategies.csb import backtest_storage

    class Row:
        def __init__(self):
            self.details_csv_bytes = None
            self.config = {}
            self.status = "running"

    row = Row()

    class Q:
        def filter(self, *a, **k):
            return self

        def first(self):
            return row

    class Sess:
        def query(self, *a, **k):
            return Q()

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(backtest_storage, "_session", lambda: Sess())
    rows = [{"code": "000001", "signal_date": "2024-01-02", "pnl_pct": 1.2}]
    assert backtest_storage.save_partial_details("t1", rows) is True
    loaded = backtest_storage.load_partial_details("t1")
    assert loaded == rows


def test_screen_universe_respects_stock_offset(monkeypatch):
    from backend_core.strategies.csb.strategy_engine import CSBStrategyEngine

    calls: List[str] = []

    class FakeLoader:
        def load_bars_batch(self, codes, **kwargs):
            for c in codes:
                calls.append(c)
            return {c: [{"date": "2024-01-02", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}] for c in codes}

    engine = CSBStrategyEngine(loader=FakeLoader(), config={"min_score": 0, "min_listing_bars": 1, "scan": {"history_bars": 10}})

    def fake_hits(code, name, hist, dates, cfg, require_entry=True):
        return [{"code": code, "signal_date": dates[0], "score": 80, "entry_signal": True}]

    monkeypatch.setattr(
        "backend_core.strategies.csb.strategy_engine._hits_for_stock_dates",
        fake_hits,
    )
    monkeypatch.setattr(
        "backend_core.strategies.csb.strategy_engine._screen_workers",
        lambda: 1,
    )
    monkeypatch.setattr(
        "backend_core.strategies.csb.strategy_engine.history_calendar_days_for_fetch",
        lambda _cfg: 10,
    )
    monkeypatch.setattr(
        "backend_core.strategies.csb.data_loader.CSBDataLoader.resolve_hist_batch_chunk_size",
        lambda **k: 2,
    )
    monkeypatch.setattr(
        "backend_core.strategies.csb.data_loader.CSBDataLoader.default_date_window",
        lambda *_a, **_k: ("2023-01-01", "2024-01-02"),
    )

    stocks: List[Tuple[str, str]] = [(f"{i:06d}", f"n{i}") for i in range(6)]
    hits, ok = engine.screen_universe_for_dates(
        stocks, ["2024-01-02"], require_entry=True, stock_offset=4, chunk_size=2
    )
    assert ok is True
    assert calls == ["000004", "000005"]
    assert len(hits["2024-01-02"]) == 2


def test_resume_after_restart_starts_thread(monkeypatch):
    from backend_core.strategies.csb import backtest_storage, backtest_worker

    started = []
    state = {"status": "paused", "config": {"checkpoint": {"phase": "precompute", "precompute_stock_offset": 10}}}

    monkeypatch.setattr(backtest_worker, "is_task_alive", lambda _tid: False)
    monkeypatch.setattr(backtest_worker, "request_resume", lambda _tid: None)
    monkeypatch.setattr(
        backtest_storage,
        "get_task",
        lambda tid: {"task_id": tid, "status": state["status"], "config": state["config"]},
    )

    def _prepare(tid):
        state["status"] = "pending"
        return True

    monkeypatch.setattr(backtest_storage, "prepare_checkpoint_resume", _prepare)
    monkeypatch.setattr(backtest_storage, "resume_task", lambda _tid: False)
    monkeypatch.setattr(backtest_worker, "start_backtest_task", lambda tid: started.append(tid))

    from backend_api.admin import csb_admin_routes as routes
    import asyncio

    res = asyncio.run(routes.resume_backtest("task-restart"))
    assert res["success"] is True
    assert res.get("mode") == "checkpoint"
    assert started == ["task-restart"]
    assert state["status"] == "pending"


def test_mark_zombie_running_failed(monkeypatch):
    from backend_core.strategies.csb import backtest_storage

    rows = [
        type("R", (), {"task_id": "a", "status": "running", "message": "", "error": None, "completed_at": None})(),
        type("R", (), {"task_id": "b", "status": "paused", "message": "", "error": None, "completed_at": None})(),
        type("R", (), {"task_id": "c", "status": "running", "message": "", "error": None, "completed_at": None})(),
    ]

    class Q:
        def filter(self, *a, **k):
            return self

        def all(self):
            return [r for r in rows if r.status == "running"]

    class Sess:
        def query(self, *a, **k):
            return Q()

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(backtest_storage, "_session", lambda: Sess())
    n = backtest_storage.mark_zombie_running_tasks_failed("进程中断")
    assert n == 2
    assert rows[0].status == "failed"
    assert rows[1].status == "paused"
    assert rows[2].status == "failed"
