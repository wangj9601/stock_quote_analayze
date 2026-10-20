# -*- coding: utf-8 -*-
"""强制刷新区间预计算：只删日期区间内的 trace。"""

from unittest.mock import MagicMock, patch

from backend_core.strategies.csb.trace_store import delete_trace_for_config_in_range


class _Col:
    def __eq__(self, other):
        return ("eq", other)

    def __ge__(self, other):
        return ("ge", other)

    def __le__(self, other):
        return ("le", other)


def test_delete_trace_for_config_in_range_filters_by_dates():
    fake_model = MagicMock(name="CSBSignalTrace")
    fake_model.config_id = _Col()
    fake_model.trade_date = _Col()

    q = MagicMock()
    q.filter.return_value = q
    q.delete.return_value = 12
    db = MagicMock()
    db.query.return_value = q

    with patch("backend_api.models.CSBSignalTrace", fake_model):
        n = delete_trace_for_config_in_range(
            db,
            config_id=1,
            start_date="2025-07-01",
            end_date="2026-10-20",
        )

    assert n == 12
    db.query.assert_called_once_with(fake_model)
    args = q.filter.call_args[0]
    assert ("eq", 1) in args
    assert ("ge", "2025-07-01") in args
    assert ("le", "2026-10-20") in args
    q.delete.assert_called_once_with(synchronize_session=False)
    db.commit.assert_called_once()


def test_delete_trace_for_config_in_range_rejects_bad_range():
    try:
        delete_trace_for_config_in_range(
            MagicMock(),
            config_id=1,
            start_date="2026-10-20",
            end_date="2025-07-01",
        )
        assert False, "expected ValueError"
    except ValueError as e:
        assert "不能晚于" in str(e)


def test_refresh_range_purges_only_date_window(monkeypatch):
    """run_csb_trace_refresh_range 应调用区间删除，而不是整版删除。"""
    calls = {}

    def _del_range(db, *, config_id, start_date, end_date):
        calls["range"] = (config_id, start_date, end_date)
        return 5

    def _del_all(*args, **kwargs):
        calls["all"] = True
        return 99

    class _CM:
        def ensure_default_row(self, db):
            return None

        def get_config(self, config_id, db=None):
            return {"min_score": 60}

    monkeypatch.setattr(
        "backend_core.strategies.csb.trace_store.delete_trace_for_config_in_range",
        _del_range,
    )
    monkeypatch.setattr(
        "backend_core.strategies.csb.trace_store.delete_trace_for_config",
        _del_all,
    )
    monkeypatch.setattr(
        "backend_core.strategies.csb.config.CSBConfigManager",
        _CM,
    )
    monkeypatch.setattr(
        "backend_core.strategies.csb.backtest_runner._trading_dates",
        lambda db, s, e: ["2025-07-01"],
    )
    monkeypatch.setattr(
        "backend_core.strategies.csb.backtest_runner._ensure_trace_for_backtest_range",
        lambda *a, **k: {"days": 1, "written": 0},
    )
    monkeypatch.setattr(
        "backend_core.strategies.csb.data_loader.CSBDataLoader",
        lambda db: MagicMock(),
    )
    monkeypatch.setattr(
        "backend_core.strategies.csb.strategy_engine.CSBStrategyEngine",
        lambda *a, **k: MagicMock(),
    )
    monkeypatch.setattr(
        "backend_api.database.SessionLocal",
        lambda: MagicMock(),
    )

    from backend_core.strategies.csb import scheduled_precompute as sp

    out = sp.run_csb_trace_refresh_range(
        1,
        start_date="2025-07-01",
        end_date="2026-10-20",
        purge_first=True,
    )
    assert out.get("success") is True
    assert calls.get("range") == (1, "2025-07-01", "2026-10-20")
    assert "all" not in calls
