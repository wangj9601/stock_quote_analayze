"""多股 GMS 回测：每个 (市场, 交易日) 仅一次批量 get_selection_results（整池 stock_pool）。"""

import os
import sys
from unittest.mock import MagicMock

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend_core.strategies.gms import backtest_runner as br


def test_multistock_one_market_batch_calls(monkeypatch):
    """2 只 A 股、2 个交易日：应 2 次选股调用，每次 stock_pool 为整池。"""
    db = MagicMock()
    monkeypatch.setattr(br, "_get_trading_dates_cn", lambda _db, _s, _e: ["2024-01-02", "2024-01-03"])

    calls = []

    def fake_get_selection_results(self, date=None, stock_pool=None, market=None, **kwargs):
        calls.append(
            {
                "date": date,
                "stock_pool": list(stock_pool) if stock_pool else None,
                "market": market,
            }
        )
        return []

    monkeypatch.setattr(br.GMSFrontendInterface, "get_selection_results", fake_get_selection_results)

    br.run_gms_backtest(
        db,
        "2024-01-01",
        "2024-01-31",
        market="cn",
        stock_pool=["000001", "600000"],
    )

    assert len(calls) == 2
    expected_pool = br._codes_for_market_from_pool(["000001", "600000"], "cn")
    for c in calls:
        assert c["market"] == "cn"
        assert c["stock_pool"] == expected_pool
    assert {c["date"] for c in calls} == {"2024-01-02", "2024-01-03"}


def test_multistock_all_market_cn_hk_batch_calls(monkeypatch):
    """A+H 各一码、全市场：cn/hk 各按各自交易日列表各日一次批量调用。"""
    db = MagicMock()
    monkeypatch.setattr(br, "_get_trading_dates_cn", lambda _db, _s, _e: ["2024-01-02"])
    monkeypatch.setattr(br, "_get_trading_dates_hk", lambda _db, _s, _e: ["2024-01-04", "2024-01-05"])

    calls = []

    def fake_get_selection_results(self, date=None, stock_pool=None, market=None, **kwargs):
        calls.append(
            {
                "date": date,
                "stock_pool": list(stock_pool) if stock_pool else None,
                "market": market,
            }
        )
        return []

    monkeypatch.setattr(br.GMSFrontendInterface, "get_selection_results", fake_get_selection_results)

    br.run_gms_backtest(
        db,
        "2024-01-01",
        "2024-01-31",
        market="all",
        stock_pool=["000001", "00981"],
    )

    assert len(calls) == 3
    cn_pool = br._codes_for_market_from_pool(["000001", "00981"], "cn")
    hk_pool = br._codes_for_market_from_pool(["000001", "00981"], "hk")
    cn_calls = [c for c in calls if c["market"] == "cn"]
    hk_calls = [c for c in calls if c["market"] == "hk"]
    assert len(cn_calls) == 1 and cn_calls[0]["stock_pool"] == cn_pool
    assert len(hk_calls) == 2
    for c in hk_calls:
        assert c["stock_pool"] == hk_pool
