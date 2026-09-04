# -*- coding: utf-8 -*-
"""新浪财经实时快照解析单测。"""

from unittest.mock import MagicMock, patch

from backend_api.stock.stock_manage import _quote_from_sina


def test_quote_from_sina_parses_hq_string():
    body = (
        'var hq_str_sh600519="贵州茅台,1700.00,1690.00,1710.50,1720.00,1688.00,'
        "0,0,12345600,2100000000.00,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,"
        '2026-09-03,15:00:00,00";\n'
    ).encode("gbk")

    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False

    with patch("urllib.request.urlopen", return_value=mock_resp):
        with patch(
            "backend_api.utils.adj_quotes.throttle_third_party_fetch",
            return_value=None,
        ):
            q = _quote_from_sina("600519")

    assert q is not None
    assert q["source"] == "sina"
    assert q["code"] == "600519"
    assert q["name"] == "贵州茅台"
    assert abs(float(q["current_price"]) - 1710.5) < 1e-6
    assert abs(float(q["pre_close"]) - 1690.0) < 1e-6
    assert q["trade_date"] == "2026-09-03"
    assert str(q["update_time"]).startswith("2026-09-03 15:00:00")
