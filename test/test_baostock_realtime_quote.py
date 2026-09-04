# -*- coding: utf-8 -*-
"""BaoStock 实时价回退：日 K + 可选 5 分钟末根。"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend_api.stock.stock_manage import _quote_from_baostock


class _FakeRs:
    def __init__(self, rows, fields, error_code="0"):
        self.fields = fields
        self.error_code = error_code
        self.error_msg = "success"
        self._rows = list(rows)
        self._i = -1

    def next(self):
        self._i += 1
        return self._i < len(self._rows)

    def get_row_data(self):
        return self._rows[self._i]


def test_quote_from_baostock_uses_daily_and_5m_close():
    daily_fields = [
        "date",
        "code",
        "open",
        "high",
        "low",
        "close",
        "preclose",
        "volume",
        "amount",
        "pctChg",
        "turn",
    ]
    daily_row = [
        "2026-09-03",
        "sh.600519",
        "1297.5",
        "1305.0",
        "1293.0",
        "1298.88",
        "1297.5",
        "1774765",
        "2305193119.46",
        "0.1064",
        "0.142",
    ]
    m5_fields = ["date", "time", "code", "open", "high", "low", "close", "volume", "amount"]
    m5_row = [
        "2026-09-03",
        "20260903145900000",
        "sh.600519",
        "1299.0",
        "1300.0",
        "1298.0",
        "1299.5",
        "1000",
        "1299500",
    ]

    fake_bs = MagicMock()
    fake_bs.login.return_value = SimpleNamespace(error_code="0", error_msg="success")
    fake_bs.logout.return_value = None

    def _query(symbol, fields, start_date=None, end_date=None, frequency="d", adjustflag="3"):
        if frequency == "d":
            return _FakeRs([daily_row], daily_fields)
        return _FakeRs([m5_row], m5_fields)

    fake_bs.query_history_k_data_plus.side_effect = _query

    with patch.dict("sys.modules", {"baostock": fake_bs}):
        with patch(
            "backend_api.utils.adj_quotes.throttle_third_party_fetch",
            return_value=None,
        ):
            q = _quote_from_baostock("600519", name="贵州茅台")

    assert q is not None
    assert q["source"] == "baostock"
    assert q["code"] == "600519"
    assert q["name"] == "贵州茅台"
    assert q["trade_date"] == "2026-09-03"
    assert abs(float(q["current_price"]) - 1299.5) < 1e-6
    assert abs(float(q["open"]) - 1297.5) < 1e-6
    assert q["update_time"].startswith("2026-09-03 14:59:00")


def test_quote_from_baostock_skips_bse():
    q = _quote_from_baostock("920000")
    assert q is None
