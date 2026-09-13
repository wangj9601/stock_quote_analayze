# -*- coding: utf-8 -*-
"""个股资金流上卷回填板块资金流：日期解析、冲突策略、SQL 聚合。"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest


def test_resolve_date_range_priority():
    from backend_core.data_collectors.akshare.board_fund_flow_aggregate_backfill import (
        resolve_date_range,
    )

    d, e = resolve_date_range(trade_date="2026-03-20")
    assert d == e == date(2026, 3, 20)

    d, e = resolve_date_range(start_date="2026-01-01", end_date="2026-01-10")
    assert d == date(2026, 1, 1)
    assert e == date(2026, 1, 10)

    with pytest.raises(ValueError):
        resolve_date_range(start_date="2026-01-01")

    d, e = resolve_date_range(days=3)
    assert e == datetime.now().date()
    assert d == e - timedelta(days=2)
    assert (e - d).days == 2


def test_should_write_policy():
    from backend_core.data_collectors.akshare.board_fund_flow_aggregate_backfill import (
        _should_write,
    )

    assert _should_write(None, force=False, force_all=False) is True
    assert (
        _should_write(
            {"source": "ths_fund_flow", "main_net_inflow": 1.0},
            force=False,
            force_all=False,
        )
        is False
    )
    assert (
        _should_write(
            {"source": "ths_fund_flow", "main_net_inflow": 1.0},
            force=True,
            force_all=False,
        )
        is False
    )
    assert (
        _should_write(
            {"source": "aggregate", "main_net_inflow": 1.0},
            force=True,
            force_all=False,
        )
        is True
    )
    assert (
        _should_write(
            {"source": "ths_fund_flow", "main_net_inflow": None},
            force=False,
            force_all=False,
        )
        is True
    )
    assert (
        _should_write(
            {"source": "ths_fund_flow", "main_net_inflow": 1.0},
            force=False,
            force_all=True,
        )
        is True
    )


def test_fetch_aggregate_rows_builds_and_filters():
    from backend_core.data_collectors.akshare.board_fund_flow_aggregate_backfill import (
        fetch_aggregate_rows,
    )

    session = MagicMock()
    # 第一次：聚合查询；第二次：已有行
    session.execute.side_effect = [
        MagicMock(
            fetchall=MagicMock(
                return_value=[
                    ("881001", "银行", "BK0475", "2026-03-20", 1e8, 5e7, 5e7, 3),
                    ("881002", "证券", None, "2026-03-20", 2e8, 1e8, 1e8, 2),
                ]
            )
        ),
        MagicMock(
            fetchall=MagicMock(
                return_value=[
                    ("881001", date(2026, 3, 20), "ths_fund_flow", 9e7),
                ]
            )
        ),
    ]

    rows, stats = fetch_aggregate_rows(
        session,
        board_kind="industry",
        start=date(2026, 3, 20),
        end=date(2026, 3, 20),
        force=False,
        force_all=False,
    )
    assert stats["candidates"] == 2
    assert stats["skipped_protected"] == 1
    assert len(rows) == 1
    assert rows[0]["board_code"] == "881002"
    assert rows[0]["main_net_inflow"] == 1e8
    assert rows[0]["inflow_amount"] == 2e8
    assert rows[0]["outflow_amount"] == 1e8
    assert rows[0]["source"] == "aggregate"


def test_backfill_dry_run_no_upsert():
    from backend_core.data_collectors.akshare.board_fund_flow_aggregate_backfill import (
        backfill_board_fund_flow_from_stocks,
    )

    fake_rows = [
        {
            "board_kind": "industry",
            "board_code": "881001",
            "board_name": "银行",
            "trade_date": date(2026, 3, 20),
            "main_net_inflow": 1.0,
            "source": "aggregate",
        }
    ]
    with patch(
        "backend_core.data_collectors.akshare.board_fund_flow_aggregate_backfill.SessionLocal"
    ) as sl, patch(
        "backend_core.data_collectors.akshare.board_fund_flow_aggregate_backfill.fetch_aggregate_rows",
        return_value=(fake_rows, {"candidates": 1, "written": 1, "skipped_protected": 0, "skipped_existing": 0}),
    ), patch(
        "backend_core.data_collectors.akshare.board_fund_flow_aggregate_backfill.upsert_aggregate_rows"
    ) as upsert:
        sl.return_value = MagicMock()
        result = backfill_board_fund_flow_from_stocks(
            trade_date="2026-03-20",
            board_kinds=["industry"],
            dry_run=True,
        )
        upsert.assert_not_called()
        assert result["success"] is True
        assert result["kinds"]["industry"]["would_upsert"] == 1
        assert result["total_upserted"] == 0
