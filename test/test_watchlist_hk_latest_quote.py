# -*- coding: utf-8 -*-
"""自选股港股行情：按代码取各自最新日，避免全局最新日缺票。"""
from unittest.mock import MagicMock


def test_latest_quotes_by_codes_builds_per_code_max_join():
    from backend_api.watchlist_manage import _latest_quotes_by_codes
    from backend_api.models import StockRealtimeQuoteHK

    db = MagicMock()
    # query chain for subquery then join query
    q1 = MagicMock()
    q2 = MagicMock()
    db.query.side_effect = [q1, q2]
    q1.filter.return_value = q1
    q1.group_by.return_value = q1
    q1.subquery.return_value = MagicMock(name="subq")
    q2.join.return_value = q2
    fake_row = MagicMock(code="00700", trade_date="2026-09-08", current_price=435.4)
    q2.all.return_value = [fake_row]

    rows = _latest_quotes_by_codes(db, StockRealtimeQuoteHK, ["00700", "03396"])
    assert len(rows) == 1
    assert rows[0].code == "00700"
    assert db.query.call_count == 2


def test_latest_quotes_by_codes_empty():
    from backend_api.watchlist_manage import _latest_quotes_by_codes
    from backend_api.models import StockRealtimeQuoteHK

    db = MagicMock()
    assert _latest_quotes_by_codes(db, StockRealtimeQuoteHK, []) == []
    db.query.assert_not_called()
