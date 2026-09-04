# -*- coding: utf-8 -*-
"""realtime_bars：实时报价合并日 K 末根。"""

from backend_core.analysis.realtime_bars import (
    merge_realtime_into_bars,
    quote_to_ohlc_bar,
)


def test_quote_to_ohlc_bar_basic():
    bar = quote_to_ohlc_bar(
        {
            "code": "600519",
            "current_price": 1700.5,
            "open": 1680.0,
            "high": 1710.0,
            "low": 1675.0,
            "volume": 100000,
            "trade_date": "2026-09-04",
            "change_percent": 1.2,
            "source": "fuyao",
        }
    )
    assert bar is not None
    assert bar["date"] == "2026-09-04"
    assert bar["close"] == 1700.5
    assert bar["high"] == 1710.0
    assert bar["_realtime"] is True


def test_merge_appends_when_new_day():
    bars = [{"date": "2026-09-03", "high": 10, "low": 9, "close": 9.5, "volume": 1}]
    out, meta = merge_realtime_into_bars(
        bars,
        {
            "code": "000001",
            "current_price": 11.0,
            "open": 10.5,
            "high": 11.2,
            "low": 10.4,
            "volume": 20000,
            "trade_date": "2026-09-04",
            "source": "realtime_db",
        },
    )
    assert len(out) == 2
    assert out[-1]["date"] == "2026-09-04"
    assert out[-1]["close"] == 11.0
    assert meta and meta["merged"] is True


def test_merge_replaces_same_day():
    bars = [{"date": "2026-09-04", "high": 10, "low": 9, "close": 9.5, "volume": 1}]
    out, meta = merge_realtime_into_bars(
        bars,
        {
            "code": "000001",
            "current_price": 12.0,
            "open": 10.0,
            "high": 12.5,
            "low": 9.8,
            "volume": 5000,
            "trade_date": "2026-09-04",
            "source": "fuyao",
        },
    )
    assert len(out) == 1
    assert out[0]["close"] == 12.0
    assert out[0]["high"] == 12.5
    assert meta["current_price"] == 12.0
