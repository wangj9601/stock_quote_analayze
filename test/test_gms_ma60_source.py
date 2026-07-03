"""
GMS MA60 数据源单元测试（ma_indicators.ma60 → ma60_d）。
"""

from __future__ import annotations

from unittest.mock import MagicMock

from backend_core.strategies.gms.ma60_source import (
    batch_lookup_ma60_d,
    batch_lookup_ma60_lag,
    enrich_rows_ma60_d,
    enrich_rows_ma60_flat,
    is_ma60_flat,
    lookup_ma60_d,
    ma60_key,
    normalize_indicator_date,
    resolve_ma60_flat_lookback_days,
)


def test_normalize_indicator_date():
    assert normalize_indicator_date("2026-05-10T00:00:00") == "2026-05-10"
    assert normalize_indicator_date(None) == ""


def test_lookup_ma60_d_returns_value():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = (12.34,)
    v = lookup_ma60_d(db, "600519", "2026-05-10", "CN")
    assert v == 12.34


def test_lookup_ma60_d_missing():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    assert lookup_ma60_d(db, "600519", "2026-05-10", "CN") is None


def test_batch_lookup_ma60_d():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [
        ("600519", "2026-05-10", "CN", 11.0),
        ("000001", "2026-05-10", "CN", 9.5),
    ]
    keys = [("600519", "2026-05-10", "CN"), ("000001", "2026-05-10", "CN")]
    out = batch_lookup_ma60_d(db, keys)
    assert out[ma60_key("600519", "2026-05-10", "CN")] == 11.0
    assert out[ma60_key("000001", "2026-05-10", "CN")] == 9.5


def test_enrich_rows_ma60_d_only_fills_missing():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [
        ("600519", "2026-05-10", "CN", 15.0),
    ]
    rows = [
        {"code": "600519", "date": "2026-05-10", "market_type": "CN", "ma60_d": 99.0},
        {"code": "600519", "date": "2026-05-11", "market_type": "CN"},
    ]
    enrich_rows_ma60_d(db, rows)
    assert rows[0]["ma60_d"] == 99.0
    assert rows[1].get("ma60_d") is None


def test_resolve_ma60_flat_lookback_days():
    assert resolve_ma60_flat_lookback_days({"observation_period": 20}) == 20
    assert resolve_ma60_flat_lookback_days({"observation_period": 30, "scoring": {}}) == 30
    assert resolve_ma60_flat_lookback_days(
        {"observation_period": 20, "scoring": {"ma60_flat_lookback_days": 15}}
    ) == 15
    assert resolve_ma60_flat_lookback_days({}) == 20


def test_is_ma60_flat_boundaries():
    assert is_ma60_flat(10.0, 10.0, 0.015) is True
    assert is_ma60_flat(10.14, 10.0, 0.015) is True
    assert is_ma60_flat(10.16, 10.0, 0.015) is False
    assert is_ma60_flat(10.0, None, 0.015) is False
    assert is_ma60_flat(None, 10.0, 0.015) is False


def test_batch_lookup_ma60_lag():
    db = MagicMock()
    history = [
        ("2026-05-10", 12.0),
        ("2026-05-09", 11.9),
        ("2026-05-08", 11.8),
    ]
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = history
    keys = [("600519", "2026-05-10", "CN")]
    out = batch_lookup_ma60_lag(db, keys, lookback_days=2)
    assert out[ma60_key("600519", "2026-05-10", "CN")] == 11.8


def test_enrich_rows_ma60_flat_sets_flags():
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
        ("2026-05-10", 12.0),
        ("2026-05-09", 11.95),
        ("2026-05-08", 11.9),
        ("2026-05-07", 11.85),
    ]
    rows = [{"code": "600519", "date": "2026-05-10", "market_type": "CN", "ma60_d": 12.0}]
    enrich_rows_ma60_flat(db, rows, lookback_days=2, tol=0.015)
    assert rows[0]["ma60_d_lag"] == 11.9
    assert rows[0]["ma60_flat"] is True
