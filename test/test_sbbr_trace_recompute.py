# -*- coding: utf-8 -*-
"""SBBR 信号历史强制重算：存储层与路由辅助可导入性。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


def test_recompute_helpers_importable():
    from backend_core.strategies.sbbr.signal_storage import (
        delete_traces_for_code_config,
        recompute_trace_for_stock,
    )

    assert callable(delete_traces_for_code_config)
    assert callable(recompute_trace_for_stock)


def test_recompute_trace_for_stock_writes_rows(monkeypatch):
    """用假 loader / engine 验证：清旧 → 按日评估 → upsert。"""
    from backend_core.strategies.sbbr import signal_storage as ss

    calls = {"deleted": 0, "upserts": [], "progress": []}

    class _FakeTrace:
        def __init__(self):
            self._n = 0

        def filter(self, *a, **k):
            return self

        def delete(self, synchronize_session=False):
            calls["deleted"] += 1
            return 3

        def count(self):
            return self._n

    class _FakeQuery:
        def __init__(self, n=0):
            self._trace = _FakeTrace()
            self._trace._n = n

        def filter(self, *a, **k):
            return self._trace

    class _FakeDB:
        def __init__(self):
            self._written = 0

        def query(self, model):
            return _FakeQuery(n=self._written)

        def commit(self):
            return None

        def rollback(self):
            return None

    def _bar(date: str, close: float = 10.0) -> Dict[str, Any]:
        return {
            "date": date,
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": 100.0,
            "amount": close * 100,
            "turnover_rate": 2.0,
        }

    def _make_bars(n: int = 50) -> List[Dict[str, Any]]:
        from datetime import timedelta

        end = datetime.strptime("2024-06-28", "%Y-%m-%d").date()
        out = []
        for i in range(n):
            d = end - timedelta(days=n - 1 - i)
            out.append(_bar(d.strftime("%Y-%m-%d"), close=10 + (i % 5) * 0.1))
        return out

    bars = _make_bars(50)
    idx = list(bars)

    class _Loader:
        def resolve_effective_trade_date(self, requested=None):
            return bars[-1]["date"]

        def load_bars(self, code, *, end_date=None, limit=120):
            src = idx if str(code) == "000001" else bars
            out = list(src)
            if end_date:
                out = [b for b in out if b["date"] <= str(end_date)[:10]]
            return out[-int(limit) :]

        def load_share_map(self, codes=None, as_of_date=None):
            return {
                "600354": {
                    "code": "600354",
                    "name": "敦煌种业",
                    "total_shares": 1e9,
                    "free_float_shares": 5e8,
                }
            }

        @staticmethod
        def truncate_bars_asof(bars_in, asof):
            if not asof:
                return list(bars_in)
            return [b for b in bars_in if b["date"] <= str(asof)[:10]]

    class _Engine:
        def __init__(self, db_session=None, config=None):
            self.loader = _Loader()
            self.config = config or {}

        def evaluate_code(self, code, *, date=None, config=None, share_info=None, market_returns=None, bars=None):
            return {
                "code": code,
                "name": "敦煌种业",
                "date": date,
                "size_ok": True,
                "bottom_matched": False,
                "entry_signal": False,
                "close": 10.0,
                "detail": {},
            }

    def _fake_upsert(db, rows, *, config_id, trade_date):
        calls["upserts"].append((len(rows), trade_date, config_id))
        db._written = getattr(db, "_written", 0) + len(rows)
        return len(rows)

    monkeypatch.setattr(ss, "upsert_signal_traces", _fake_upsert)
    monkeypatch.setattr(
        "backend_core.strategies.sbbr.strategy_engine.SBBRStrategyEngine",
        _Engine,
    )
    monkeypatch.setattr(
        "backend_core.strategies.sbbr.data_loader.SBBRDataLoader.truncate_bars_asof",
        _Loader.truncate_bars_asof,
    )
    monkeypatch.setattr(
        "backend_core.strategies.sbbr.config.SBBRConfigManager.get_config",
        lambda self, cid=None: {"scan": {"history_bars": 40}, "entry": {}},
    )

    # delete_traces uses real model query path — stub via FakeDB + patch model import inside
    from backend_api import models as models_mod

    class _SBBRSignalTrace:
        code = object()
        config_id = object()

    monkeypatch.setattr(models_mod, "SBBRSignalTrace", _SBBRSignalTrace, raising=False)

    db = _FakeDB()
    # delete_traces_for_code_config will call db.query(...).filter().delete + commit
    # Our FakeDB.query returns FakeQuery which has filter.delete

    def progress_cb(cur, tot, msg):
        calls["progress"].append((cur, tot, msg))

    written = ss.recompute_trace_for_stock(
        db,
        code="600354",
        config_id=1,
        config={"scan": {"history_bars": 40}, "entry": {}},
        lookback_calendar_days=120,
        progress_cb=progress_cb,
    )

    assert calls["deleted"] == 1
    assert calls["upserts"], "应至少 upsert 一批"
    assert written == db._written
    assert calls["progress"], "应有进度回调"
