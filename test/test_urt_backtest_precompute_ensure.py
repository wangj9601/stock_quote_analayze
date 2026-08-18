"""URT 回测区间预计算覆盖检测。"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_core.strategies.urt.trace_store import (
    URT_TRACE_SCANNED_MARKER,
    dates_ready_for_universe_backtest,
    dates_with_trace_coverage,
)


def test_scanned_marker_constant():
    assert URT_TRACE_SCANNED_MARKER == "__URT_SCANNED__"


def test_dates_with_trace_coverage_empty_dates():
    class _Dummy:
        pass

    # 无日期时不访问 DB
    assert dates_with_trace_coverage(_Dummy(), config_id=1, dates=[]) == set()
def test_ensure_trace_uses_range_scan_not_per_day(monkeypatch):
    """缺覆盖时走区间一次扫描，禁止按日 screen_universe。"""
    from backend_core.strategies.urt import backtest_runner as br

    calls = []
    marks = []

    class Eng:
        def screen_universe_for_dates(self, stocks, dates, **_k):
            calls.append(list(dates))
            return {d: [] for d in dates}, True

        def screen_universe(self, *_a, **_k):
            raise AssertionError("should not day-scan")

    class Loader:
        def list_a_share_candidates(self, stock_codes=None):
            return [("000001", "t")]

    monkeypatch.setattr(br, "dates_ready_for_universe_backtest", lambda *_a, **_k: set())
    monkeypatch.setattr(br, "upsert_trace_rows", lambda *_a, **_k: 0)
    monkeypatch.setattr(
        br,
        "mark_date_scanned",
        lambda _db, **kw: marks.append(kw["trade_date"]),
    )

    meta = br._ensure_trace_for_backtest_range(
        db=object(),
        dates=["2026-01-05", "2026-01-06"],
        config_id=1,
        cfg={},
        loader=Loader(),
        engine=Eng(),
        stock_pool=None,
    )
    assert calls == [["2026-01-05", "2026-01-06"]]
    assert marks == ["2026-01-05", "2026-01-06"]
    assert meta["precomputed_days"] == 2
    assert meta["range_scan"] is True
    assert meta["range_scan_completed"] is True


def test_ensure_trace_cancel_does_not_mark(monkeypatch):
    from backend_core.strategies.urt import backtest_runner as br

    marks = []

    class Eng:
        def screen_universe_for_dates(self, stocks, dates, **_k):
            return {d: [] for d in dates}, False

    class Loader:
        def list_a_share_candidates(self, stock_codes=None):
            return [("000001", "t")]

    monkeypatch.setattr(br, "dates_ready_for_universe_backtest", lambda *_a, **_k: set())
    monkeypatch.setattr(br, "upsert_trace_rows", lambda *_a, **_k: 0)
    monkeypatch.setattr(
        br,
        "mark_date_scanned",
        lambda *_a, **_k: marks.append(1),
    )

    meta = br._ensure_trace_for_backtest_range(
        db=object(),
        dates=["2026-01-05"],
        config_id=1,
        cfg={},
        loader=Loader(),
        engine=Eng(),
        stock_pool=None,
    )
    assert marks == []
    assert meta["precomputed_days"] == 0
    assert meta["range_scan_completed"] is False