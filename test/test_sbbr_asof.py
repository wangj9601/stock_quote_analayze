"""SBBR 历史回溯（asof）单测：截断行情、隔离未来数据。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

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


def _make_bars(end: str = "2024-06-28", n: int = 80, close: float = 10.0) -> List[Dict[str, Any]]:
    """生成连续自然日假 K 线（足够 detect 用）。"""
    from datetime import datetime, timedelta

    end_d = datetime.strptime(end, "%Y-%m-%d").date()
    bars = []
    for i in range(n):
        d = end_d - timedelta(days=n - 1 - i)
        # 轻微上行，避免被下跌通道过滤
        c = close + (i % 7) * 0.02
        bars.append(_bar(d.strftime("%Y-%m-%d"), close=c, vol=80 + (i % 5) * 10))
    return bars


def test_truncate_bars_asof_excludes_future():
    bars = [
        _bar("2024-06-01"),
        _bar("2024-06-03"),
        _bar("2024-06-05"),
        _bar("2024-06-10"),
    ]
    out = SBBRDataLoader.truncate_bars_asof(bars, "2024-06-05")
    assert [b["date"] for b in out] == ["2024-06-01", "2024-06-03", "2024-06-05"]
    assert all(b["date"] <= "2024-06-05" for b in out)


def test_truncate_bars_asof_empty_or_none():
    bars = [_bar("2024-06-01")]
    assert SBBRDataLoader.truncate_bars_asof(bars, None) == bars
    assert SBBRDataLoader.truncate_bars_asof([], "2024-06-01") == []


class _AsofFakeLoader:
    """模拟 loader：load_bars 故意返回含未来日的全量，验证引擎会截断。"""

    def __init__(self, bars: List[Dict[str, Any]]):
        self._bars = bars
        self.last_end_date: Optional[str] = None

    def resolve_trade_date(self) -> str:
        return self._bars[-1]["date"]

    def resolve_effective_trade_date(self, requested: Optional[str] = None) -> str:
        if not requested:
            return self.resolve_trade_date()
        d = str(requested)[:10]
        # 对齐到 <= requested 的最后一根
        candidates = [b["date"] for b in self._bars if b["date"] <= d]
        return candidates[-1] if candidates else self.resolve_trade_date()

    def load_bars(self, code, *, end_date=None, limit=120):
        self.last_end_date = end_date
        # 故意返回「未截断」全量，模拟脏数据；引擎应再 truncate
        return list(self._bars[-int(limit) :])

    def load_share_map(self, codes=None, as_of_date=None):
        return {
            "000001": {
                "code": "000001",
                "name": "测试",
                "total_shares": 1e9,
                "free_float_shares": 6e8,
            }
        }

    def load_market_returns(self, *, end_date=None, lookback=80, index_code="000001"):
        return [0.0] * 40

    def build_size_universe(self, config, trade_date=None, limit=None):
        return []


def test_evaluate_code_asof_isolates_future_bars():
    """asof 日之后的 K 线不得参与计算；结果 date 应为 asof。"""
    all_bars = _make_bars(end="2024-06-28", n=90)
    asof = "2024-06-10"
    engine = SBBRStrategyEngine(config=get_default_sbbr_config())
    engine.loader = _AsofFakeLoader(all_bars)

    row = engine.evaluate_code("000001", date=asof)
    assert row is not None
    assert row["date"] == asof
    assert row["detail"]["asof_date"] == asof
    assert row["detail"]["bar_end_date"] <= asof
    # 假 loader 虽返回全量，引擎 truncate 后 bar_end 不应超过 asof
    assert engine.loader.last_end_date == asof


def test_evaluate_code_without_asof_uses_latest_bar():
    all_bars = _make_bars(end="2024-06-28", n=80)
    engine = SBBRStrategyEngine(config=get_default_sbbr_config())
    engine.loader = _AsofFakeLoader(all_bars)
    row = engine.evaluate_code("000001", date=None)
    assert row is not None
    assert row["date"] == all_bars[-1]["date"]


def test_screen_resolves_weekend_to_prior_trading_day():
    """screen 应对非交易日请求对齐到 <= 请求日的最近有 K 线日。"""
    all_bars = _make_bars(end="2024-06-28", n=90)
    # 去掉 06-15（假设为请求日周六，无行情），保留 06-14
    bars = [b for b in all_bars if b["date"] != "2024-06-15"]
    engine = SBBRStrategyEngine(config=get_default_sbbr_config())
    fake = _AsofFakeLoader(bars)
    engine.loader = fake

    # 直接测 resolve
    assert fake.resolve_effective_trade_date("2024-06-15") == "2024-06-14"
    assert fake.resolve_effective_trade_date("2024-06-14") == "2024-06-14"
    assert fake.resolve_effective_trade_date(None) == bars[-1]["date"]

    rows = engine.screen(codes=["000001"], date="2024-06-15", require_size=False, require_bottom=False)
    assert len(rows) == 1
    assert rows[0]["date"] == "2024-06-14"


def test_asof_close_differs_from_future_close():
    """同一股票：历史 asof 收盘应与含未来数据的最新收盘不同（隔离校验）。"""
    bars = _make_bars(end="2024-06-20", n=60, close=10.0)
    # 人为抬高最后几天收盘，模拟「未来」信息
    for b in bars[-5:]:
        b["close"] = 50.0
        b["open"] = 50.0
        b["high"] = 51.0
        b["low"] = 49.0

    asof = bars[-10]["date"]  # 抬高之前
    engine = SBBRStrategyEngine(config=get_default_sbbr_config())
    engine.loader = _AsofFakeLoader(bars)

    hist = engine.evaluate_code("000001", date=asof)
    latest = engine.evaluate_code("000001", date=bars[-1]["date"])
    assert hist is not None and latest is not None
    assert hist["close"] < 20  # asof 日仍约 10 附近
    assert latest["close"] == 50.0
    assert hist["close"] != latest["close"]
