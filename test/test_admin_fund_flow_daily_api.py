"""管理端 stock_fund_flow_daily 查询接口单测（mock DB）。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from backend_api.admin import quotes as quotes_mod


def test_get_stock_fund_flow_daily_defaults_latest_date(monkeypatch):
    row = SimpleNamespace(
        code="600519",
        trade_date="2026-09-08",
        name="贵州茅台",
        inflow_amount=1e8,
        outflow_amount=5e7,
        net_amount=5e7,
        turnover_amount=2e8,
        change_percent=1.2,
        turnover_rate=0.5,
        current_price=1700.0,
        source="ths",
        created_at=None,
        updated_at=None,
    )

    q = MagicMock()
    q.filter.return_value = q
    q.count.return_value = 1
    q.order_by.return_value = q
    q.offset.return_value = q
    q.limit.return_value = q
    q.all.return_value = [row]
    q.scalar.return_value = "2026-09-08"

    db = MagicMock()
    db.query.return_value = q

    import asyncio

    result = asyncio.get_event_loop().run_until_complete(
        quotes_mod.get_stock_fund_flow_daily(
            page=1,
            page_size=20,
            keyword=None,
            trade_date=None,
            sort_by="net_amount",
            sort_order="desc",
            current_user=object(),
            db=db,
        )
    )
    assert result["success"] is True
    assert result["total"] == 1
    assert result["trade_date"] == "2026-09-08"
    assert result["data"][0]["code"] == "600519"
    assert result["data"][0]["net_amount"] == 5e7
