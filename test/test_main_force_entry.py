# -*- coding: utf-8 -*-
"""主力入场判定引擎单测（合成序列，不连库）。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend_core.analysis.main_force_entry import (
    compute_main_force_entry,
    is_entry_day,
    vwap_from_bar,
)


def test_vwap_from_bar():
    # amount=1000000, volume=100手 → 1000000/100/100 = 100
    assert abs(vwap_from_bar({"amount": 1_000_000, "volume": 100}) - 100.0) < 1e-6
    assert vwap_from_bar({"amount": None, "volume": 10, "close": 12.5}) == 12.5


def test_is_entry_day():
    assert is_entry_day(3e6, 1e8, participation_min=0.03) is True  # 3%
    assert is_entry_day(1e6, 1e8, participation_min=0.03) is False
    assert is_entry_day(-1e6, 1e8) is False
    assert is_entry_day(1e6, None) is True


def _series(n: int, main_net: float, price: float = 10.0, vol: float = 10000):
    em = []
    quotes = []
    for i in range(n):
        d = f"2026-01-{i + 1:02d}"
        em.append({"trade_date": d, "main_net_inflow": main_net, "close_price": price})
        quotes.append(
            {
                "trade_date": d,
                "amount": price * vol * 100,
                "volume": vol,
                "high": price + 0.5,
                "low": price - 0.5,
                "close": price,
            }
        )
    return em, quotes


def test_insufficient_data():
    out = compute_main_force_entry(code="000001", em_rows=[], quote_rows=[])
    assert out["verdict"] == "insufficient_data"


def test_net_outflow():
    em, quotes = _series(10, main_net=-1e7)
    out = compute_main_force_entry(code="000001", em_rows=em, quote_rows=quotes)
    assert out["verdict"] == "net_outflow"
    assert out["latest_window"] is None


def test_pulse_single_day():
    em, quotes = _series(10, main_net=-1e6)
    # 仅第 8 日大额流入
    em[7]["main_net_inflow"] = 5e7
    out = compute_main_force_entry(code="000001", em_rows=em, quote_rows=quotes)
    assert out["verdict"] == "pulse"


def test_accumulating_streak():
    em, quotes = _series(12, main_net=-1e6, price=10.0)
    for i in range(5, 10):
        em[i]["main_net_inflow"] = 5e7
        quotes[i]["close"] = 10.0 + (i - 5) * 0.3
        quotes[i]["high"] = quotes[i]["close"] + 0.2
        quotes[i]["low"] = quotes[i]["close"] - 0.2
        quotes[i]["amount"] = quotes[i]["close"] * 20000 * 100
        quotes[i]["volume"] = 20000
    out = compute_main_force_entry(code="600519", em_rows=em, quote_rows=quotes)
    assert out["verdict"] in ("accumulating", "high_catch")
    assert out["latest_window"] is not None
    assert out["latest_window"]["cost_center"] is not None
    assert out["latest_window"]["start_date"] <= out["latest_window"]["end_date"]
    assert "disclaimer" in out


def test_high_catch():
    em, quotes = _series(10, main_net=5e7, price=20.0)
    # 末收盘远低于成本重心
    for i in range(10):
        quotes[i]["close"] = 20.0 - i * 0.5
        quotes[i]["high"] = quotes[i]["close"] + 0.3
        quotes[i]["low"] = quotes[i]["close"] - 0.3
        quotes[i]["amount"] = 20.0 * 15000 * 100
        quotes[i]["volume"] = 15000
    out = compute_main_force_entry(code="300750", em_rows=em, quote_rows=quotes)
    assert out["verdict"] == "high_catch"
    assert out["latest_window"]["cost_center"] is not None


def test_tushare_moneyflow_maps_wan_to_yuan_and_main_is_elg_plus_lg():
    from backend_core.data_collectors.tushare.moneyflow import moneyflow_record_to_em_row

    row = moneyflow_record_to_em_row(
        {
            "ts_code": "000001.SZ",
            "trade_date": "20190315",
            "buy_elg_amount": 200.0,
            "sell_elg_amount": 50.0,
            "buy_lg_amount": 80.0,
            "sell_lg_amount": 30.0,
            "buy_md_amount": 10.0,
            "sell_md_amount": 12.0,
            "buy_sm_amount": 5.0,
            "sell_sm_amount": 8.0,
        }
    )
    assert row is not None
    assert row["code"] == "000001"
    assert row["trade_date"] == "2019-03-15"
    assert row["source"] == "tushare"
    # (200-50)+(80-30) = 200 万元 → 2_000_000 元
    assert abs(row["main_net_inflow"] - 2_000_000.0) < 1e-6
    assert abs(row["super_large_net_inflow"] - 1_500_000.0) < 1e-6
    assert abs(row["large_net_inflow"] - 500_000.0) < 1e-6
    assert abs(row["mid_net_inflow"] - (-20_000.0)) < 1e-6


def test_import_em_csv_and_tushare_csv():
    from backend_core.data_collectors.akshare.em_stock_fund_flow_daily import (
        parse_import_table,
    )

    em_csv = "日期,主力净流入-净额\n2026-09-08,12345\n"
    em_rows = parse_import_table("600519", em_csv, amount_unit="yuan")
    assert len(em_rows) == 1
    assert em_rows[0]["main_net_inflow"] == 12345
    assert em_rows[0]["source"] == "manual"

    wan_rows = parse_import_table("600519", em_csv, amount_unit="wan")
    assert abs(wan_rows[0]["main_net_inflow"] - 123450000.0) < 1e-6

    ts_csv = (
        "ts_code,trade_date,buy_elg_amount,sell_elg_amount,"
        "buy_lg_amount,sell_lg_amount,buy_md_amount,sell_md_amount,"
        "buy_sm_amount,sell_sm_amount\n"
        "600519.SH,20260908,10,0,5,1,0,0,0,0\n"
    )
    ts_rows = parse_import_table("600519", ts_csv, amount_unit="auto")
    assert len(ts_rows) == 1
    # 10+4 万元 → 140000 元
    assert abs(ts_rows[0]["main_net_inflow"] - 140000.0) < 1e-6
    assert ts_rows[0]["trade_date"] == "2026-09-08"
