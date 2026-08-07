"""SBBR 单股历史信号回溯单测。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from backend_core.strategies.sbbr.config import get_default_sbbr_config
from backend_core.strategies.sbbr.data_loader import SBBRDataLoader
from backend_core.strategies.sbbr.strategy_engine import SBBRStrategyEngine


def _bar(date: str, close: float = 10.0, vol: float = 100.0) -> Dict[str, Any]:
    return {
        "date": date,
        "open": close,
        "high": close * 1.02,
        "low": close * 0.98,
        "close": close,
        "volume": vol,
        "amount": close * vol,
        "turnover_rate": 3.0,
    }


def _make_bars(end: str = "2024-06-28", n: int = 100, close: float = 10.0) -> List[Dict[str, Any]]:
    from datetime import datetime, timedelta

    end_d = datetime.strptime(end, "%Y-%m-%d").date()
    bars = []
    for i in range(n):
        d = end_d - timedelta(days=n - 1 - i)
        c = close + (i % 7) * 0.02
        bars.append(_bar(d.strftime("%Y-%m-%d"), close=c, vol=80 + (i % 5) * 10))
    return bars


class _HistFakeLoader:
    def __init__(self, bars: List[Dict[str, Any]], index_bars: Optional[List[Dict[str, Any]]] = None):
        self._bars = bars
        self._index = index_bars if index_bars is not None else list(bars)

    def resolve_trade_date(self) -> str:
        return self._bars[-1]["date"]

    def resolve_effective_trade_date(self, requested: Optional[str] = None) -> str:
        if not requested:
            return self.resolve_trade_date()
        d = str(requested)[:10]
        candidates = [b["date"] for b in self._bars if b["date"] <= d]
        return candidates[-1] if candidates else self.resolve_trade_date()

    def load_bars(self, code, *, end_date=None, limit=120):
        src = self._index if str(code) == "000001" and self._index is not self._bars else self._bars
        # 对历史股与指数：同序列即可
        if str(code) != "000001":
            src = self._bars
        else:
            src = self._index
        out = list(src)
        if end_date:
            out = [b for b in out if b["date"] <= str(end_date)[:10]]
        return out[-int(limit) :]

    def load_share_map(self, codes=None, as_of_date=None):
        return {
            "000002": {
                "code": "000002",
                "name": "历史测",
                "total_shares": 1e9,
                "free_float_shares": 6e8,
            }
        }

    def load_market_returns(self, *, end_date=None, lookback=80, index_code="000001"):
        return [0.0] * 40

    def build_size_universe(self, config, trade_date=None, limit=None):
        return []


def test_evaluate_history_rejects_inverted_range():
    engine = SBBRStrategyEngine(config=get_default_sbbr_config())
    engine.loader = _HistFakeLoader(_make_bars())
    with pytest.raises(ValueError, match="开始日期"):
        engine.evaluate_history("000002", start_date="2024-06-20", end_date="2024-06-10")


def test_evaluate_history_rejects_span_over_limit():
    engine = SBBRStrategyEngine(config=get_default_sbbr_config())
    engine.loader = _HistFakeLoader(_make_bars(n=200))
    with pytest.raises(ValueError, match="跨度"):
        engine.evaluate_history(
            "000002",
            start_date="2024-01-01",
            end_date="2024-06-28",
            max_calendar_days=30,
        )


def test_evaluate_history_asof_no_future_leak():
    """区间内每日结果只用 ≤ 当日 K 线；抬高「未来」收盘不影响更早 asof。"""
    bars = _make_bars(end="2024-06-20", n=90, close=10.0)
    for b in bars[-5:]:
        b["close"] = 50.0
        b["open"] = 50.0
        b["high"] = 51.0
        b["low"] = 49.0

    asof_mid = bars[-12]["date"]
    engine = SBBRStrategyEngine(config=get_default_sbbr_config())
    engine.loader = _HistFakeLoader(bars)

    out = engine.evaluate_history(
        "000002",
        start_date=bars[-20]["date"],
        end_date=bars[-1]["date"],
        require_size=False,
        max_calendar_days=60,
        max_trade_days=40,
    )
    assert out["total"] >= 1
    mid_rows = [r for r in out["data"] if r["date"] == asof_mid]
    assert mid_rows, f"missing row for {asof_mid}"
    assert mid_rows[0]["close"] < 20
    latest = [r for r in out["data"] if r["date"] == bars[-1]["date"]]
    assert latest and latest[0]["close"] == 50.0


def test_evaluate_history_respects_max_trade_days():
    bars = _make_bars(end="2024-06-28", n=150)
    engine = SBBRStrategyEngine(config=get_default_sbbr_config())
    engine.loader = _HistFakeLoader(bars)
    out = engine.evaluate_history(
        "000002",
        start_date=bars[0]["date"],
        end_date=bars[-1]["date"],
        max_calendar_days=200,
        max_trade_days=15,
    )
    assert out["trade_days"] == 15
    assert out["total"] <= 15


def test_truncate_used_by_history_path():
    bars = [_bar("2024-06-01"), _bar("2024-06-05"), _bar("2024-06-10")]
    assert [b["date"] for b in SBBRDataLoader.truncate_bars_asof(bars, "2024-06-05")] == [
        "2024-06-01",
        "2024-06-05",
    ]
