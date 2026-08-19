# -*- coding: utf-8 -*-
"""URT 单股追溯重算：日期区间裁剪与进度节流。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List


class _FakeDB:
    def query(self, model):
        class _Q:
            def filter(self, *a, **k):
                return self

            def delete(self, synchronize_session=False):
                return 0

        return _Q()

    def commit(self):
        return None


def _bar(date: str, close: float = 10.0) -> Dict[str, Any]:
    return {
        "date": date,
        "name": "测试股",
        "open": close,
        "high": close * 1.01,
        "low": close * 0.99,
        "close": close,
        "volume": 100.0,
        "amount": close * 100,
        "turnover_rate": 2.0,
    }


def _make_hist_desc(n: int, end: str = "2024-06-28") -> List[Dict[str, Any]]:
    end_d = datetime.strptime(end, "%Y-%m-%d").date()
    out: List[Dict[str, Any]] = []
    for i in range(n):
        d = end_d - timedelta(days=n - 1 - i)
        out.append(_bar(d.strftime("%Y-%m-%d")))
    out.reverse()
    return out


def test_throttled_progress_cb_skips_frequent_calls():
    from backend_core.strategies.urt.trace_store import _throttled_progress_cb

    calls: List[tuple] = []

    cb = _throttled_progress_cb(lambda c, t, m: calls.append((c, t, m)), min_step=5)
    assert cb is not None
    for i in range(1, 12):
        cb(i, 20, f"step {i}")
    assert calls[0] == (1, 20, "step 1")
    assert calls[-1] == (11, 20, "step 11")
    assert len(calls) < 11


def test_recompute_trace_for_stock_range_clips_eval_days(monkeypatch):
    from backend_core.strategies.urt import trace_store as ts

    hist = _make_hist_desc(80, end="2024-06-28")
    eval_calls: List[str] = []
    deleted = {"mode": ""}

    class _FakeQuery:
        def filter(self, *a, **k):
            return self

        def delete(self, synchronize_session=False):
            return 0

    class _FakeDB:
        def query(self, model):
            return _FakeQuery()

        def commit(self):
            return None

    class _Loader:
        def __init__(self, db=None):
            self.db = db

        @staticmethod
        def resolve_effective_history_end_date(db, requested):
            return "2024-06-28"

        def fetch_historical_desc(self, code, start_date=None, end_date=None):
            out = list(hist)
            if end_date:
                out = [b for b in out if b["date"] <= str(end_date)[:10]]
            if start_date:
                out = [b for b in out if b["date"] >= str(start_date)[:10]]
            out.sort(key=lambda x: x["date"], reverse=True)
            return out

    def _fake_eval(bars_desc, cfg, require_pass=False):
        d = str(bars_desc[0].get("date") or "")[:10]
        eval_calls.append(d)
        return {
            "signal_date": d,
            "buy_signal": False,
            "score": 50,
            "close": 10.0,
            "score_detail": {},
        }

    monkeypatch.setattr(ts, "delete_trace_for_code_config_in_range", lambda *a, **k: deleted.update(mode="range") or 0)
    monkeypatch.setattr(ts, "delete_trace_for_code_config", lambda *a, **k: deleted.update(mode="full") or 0)
    monkeypatch.setattr(ts, "upsert_trace_rows", lambda db, **k: len(k.get("rows") or []))
    monkeypatch.setattr("backend_core.strategies.urt.data_loader.URTDataLoader", _Loader)
    monkeypatch.setattr(
        "backend_core.strategies.urt.signal_detector.evaluate_buy_signal",
        _fake_eval,
    )
    monkeypatch.setattr(
        "backend_core.strategies.urt.indicators.min_bars_needed",
        lambda cfg: 20,
    )
    monkeypatch.setattr(
        "backend_core.strategies.urt.signal_detector.history_calendar_days_for_fetch",
        lambda cfg: 30,
    )

    written = ts.recompute_trace_for_stock(
        _FakeDB(),
        code="002271",
        config_id=1,
        config={},
        start_date="2024-06-01",
        end_date="2024-06-28",
    )

    assert deleted["mode"] == "range"
    assert written == len(eval_calls)
    assert eval_calls, "应对区间内可评日调用 evaluate"
    assert min(eval_calls) >= "2024-06-01"
    assert max(eval_calls) <= "2024-06-28"
    assert len(eval_calls) < 60, "区间重算应远少于全历史 80 日"


def test_recompute_without_range_deletes_full_history(monkeypatch):
    from backend_core.strategies.urt import trace_store as ts

    deleted = {"mode": ""}
    monkeypatch.setattr(ts, "delete_trace_for_code_config_in_range", lambda *a, **k: deleted.update(mode="range") or 0)
    monkeypatch.setattr(ts, "delete_trace_for_code_config", lambda *a, **k: deleted.update(mode="full") or 0)
    monkeypatch.setattr(ts, "upsert_trace_rows", lambda db, **k: 0)

    class _Loader:
        def __init__(self, db=None):
            self.db = db

        @staticmethod
        def resolve_effective_history_end_date(db, requested):
            return "2024-06-28"

        def fetch_historical_desc(self, code, start_date=None, end_date=None):
            return []

    monkeypatch.setattr("backend_core.strategies.urt.data_loader.URTDataLoader", _Loader)

    ts.recompute_trace_for_stock(
        _FakeDB(),
        code="002271",
        config_id=1,
        config={},
    )
    assert deleted["mode"] == "full"
