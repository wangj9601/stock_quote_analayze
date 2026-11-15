# -*- coding: utf-8 -*-
"""CUPB 历史区间：单日、闭区间、跨度与起止颠倒。"""

import pytest

from datetime import date

from backend_core.strategies.cup_bottom.signal_storage import (
    normalize_ashare_code,
    resolve_trace_span,
    stock_history_span,
)


def test_single_trade_date():
    d0, d1 = resolve_trace_span(trade_date="2026-11-13")
    assert d0.isoformat() == "2026-11-13"
    assert d1 == d0


def test_open_ended_side_is_that_day():
    d0, d1 = resolve_trace_span(start_date="2026-11-01")
    assert d0 == d1
    assert d0.isoformat() == "2026-11-01"
    d0, d1 = resolve_trace_span(end_date="2026-11-13")
    assert d0.isoformat() == "2026-11-13"


def test_inclusive_range():
    d0, d1 = resolve_trace_span(start_date="2026-10-01", end_date="2026-11-13")
    assert d0.isoformat() == "2026-10-01"
    assert d1.isoformat() == "2026-11-13"


def test_reversed_range_rejected():
    with pytest.raises(ValueError, match="开始日不能晚于结束日"):
        resolve_trace_span(start_date="2026-11-13", end_date="2026-10-01")


def test_span_over_180_days_allowed():
    d0, d1 = resolve_trace_span(start_date="2020-01-01", end_date="2026-11-13")
    assert d0.isoformat() == "2020-01-01"
    assert d1.isoformat() == "2026-11-13"
    assert (d1 - d0).days > 180


def test_missing_dates_rejected():
    with pytest.raises(ValueError, match="交易日或日期区间"):
        resolve_trace_span()


def test_stock_code_and_default_window():
    assert normalize_ashare_code("519") == "000519"
    assert normalize_ashare_code("SH600519") == "600519"
    with pytest.raises(ValueError, match="股票代码"):
        normalize_ashare_code("杯底")
    latest = date(2026, 11, 13)
    assert stock_history_span(latest) is None
    d0, d1 = stock_history_span(None, end_date="2026-11-13")
    assert d0 is None
    assert d1.isoformat() == "2026-11-13"
    d0, d1 = stock_history_span(latest, start_date="2020-01-01", end_date="2026-11-13")
    assert (d1 - d0).days > 180
    assert stock_history_span(None) is None
