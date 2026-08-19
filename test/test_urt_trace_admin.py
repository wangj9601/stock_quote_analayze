"""URT 管理端 trace 清理 / 区间刷新辅助函数。"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_core.strategies.urt.trace_store import (
    URT_TRACE_SCANNED_MARKER,
    count_trace_rows_for_config,
    delete_trace_for_config,
)


def test_scanned_marker_unchanged():
    assert URT_TRACE_SCANNED_MARKER == "__URT_SCANNED__"


def test_delete_trace_for_config(monkeypatch):
    deleted = {"n": 0}

    class _Q:
        def filter(self, *_a, **_k):
            return self

        def delete(self, **_k):
            deleted["n"] = 12
            return 12

    class _DB:
        def query(self, _model):
            return _Q()

        def commit(self):
            pass

    n = delete_trace_for_config(_DB(), config_id=3)
    assert n == 12
    assert deleted["n"] == 12


def test_count_trace_rows_for_config(monkeypatch):
    class _Q:
        def select_from(self, *_a, **_k):
            return self

        def filter(self, *_a, **_k):
            return self

        def scalar(self):
            return 56

    class _DB:
        def query(self, _fn):
            return _Q()

    assert count_trace_rows_for_config(_DB(), config_id=1) == 56


def test_refresh_range_delegates(monkeypatch):
    from backend_core.strategies.urt import scheduled_precompute as sp

    calls = {}

    def _purge(db, *, config_id):
        calls["purged"] = config_id
        return 100

    def _dates(db, start, end):
        calls["dates"] = (start, end)
        return ["2026-01-02", "2026-01-03"]

    def _ensure(db, **kw):
        calls["ensure"] = kw
        return {"precomputed_days": 2, "precompute_hits": 5}

    class _Row:
        id = 7

    class _CM:
        def ensure_default_row(self, db):
            pass

        def get_config_row(self, db, cid):
            return _Row()

        def get_config(self, cid, db=None):
            return {"min_score": 70}

    class _Loader:
        pass

    class _Engine:
        pass

    class _DB:
        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr("backend_api.database.SessionLocal", lambda: _DB())
    monkeypatch.setattr("backend_core.strategies.urt.config.URTConfigManager", _CM)
    monkeypatch.setattr("backend_core.strategies.urt.data_loader.URTDataLoader", lambda db, market="CN": _Loader())
    monkeypatch.setattr("backend_core.strategies.urt.strategy_engine.URTStrategyEngine", lambda loader, cfg: _Engine())
    monkeypatch.setattr("backend_core.strategies.urt.trace_store.delete_trace_for_config", _purge)
    monkeypatch.setattr(
        "backend_core.strategies.urt.backtest_runner._trading_dates",
        _dates,
    )
    monkeypatch.setattr(
        "backend_core.strategies.urt.backtest_runner._ensure_trace_for_backtest_range",
        _ensure,
    )

    out = sp.run_urt_trace_refresh_range(
        7,
        start_date="2026-01-01",
        end_date="2026-01-03",
        purge_first=True,
    )
    assert out["success"] is True
    assert out["purged_rows"] == 100
    assert calls["purged"] == 7
    assert calls["ensure"]["config_id"] == 7
