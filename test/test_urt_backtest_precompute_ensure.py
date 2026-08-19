"""URT 回测区间预计算覆盖检测。"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_core.strategies.urt.trace_store import (
    URT_TRACE_SCANNED_MARKER,
    dates_ready_for_universe_backtest,
    dates_with_trace_coverage,
    marker_covers_universe_request,
)


def test_scanned_marker_constant():
    assert URT_TRACE_SCANNED_MARKER == "__URT_SCANNED__"


def test_pool_marker_does_not_cover_full_market():
    extra = {"marker": "universe_scanned", "hits": 0, "candidates": 111, "scope": "pool"}
    assert marker_covers_universe_request(extra, want_pool=False, min_full_market_codes=500) is False
    assert marker_covers_universe_request(
        extra, want_pool=True, pool_need=89, min_full_market_codes=500
    ) is True


def test_full_market_marker_covers_pool_and_market():
    extra = {"marker": "universe_scanned", "hits": 12, "candidates": 4800, "scope": "full_market"}
    assert marker_covers_universe_request(extra, want_pool=False, min_full_market_codes=500) is True
    assert marker_covers_universe_request(extra, want_pool=True, pool_need=80) is True


def test_marker_without_scope_needs_candidate_count():
    assert marker_covers_universe_request({}, want_pool=False) is False
    assert marker_covers_universe_request({"candidates": 600}, want_pool=False) is True
    assert marker_covers_universe_request({"candidates": 100}, want_pool=False) is False



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