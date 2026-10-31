# -*- coding: utf-8 -*-
"""两融日采默认上一交易日（T+1），避免收盘后误采当日空表。"""

from datetime import date, datetime
from unittest.mock import MagicMock, patch

from backend_core.data_collectors.workflow.adapters import (
    _prev_cn_trade_date,
    exec_tushare_margin_daily,
)
from backend_core.data_collectors.workflow.context import WorkflowContext


def test_prev_cn_trade_date_weekday_fallback():
    with patch(
        "backend_core.data_collectors.tushare.moneyflow_daily.resolve_tushare_pro",
        return_value=None,
    ):
        # 周一 → 上周五
        assert _prev_cn_trade_date(datetime(2026, 10, 26, 18, 0, 0)) == "2026-10-23"
        # 周二 → 周一
        assert _prev_cn_trade_date(datetime(2026, 10, 27, 18, 0, 0)) == "2026-10-26"


def test_prev_cn_trade_date_uses_trade_cal_when_available():
    with patch(
        "backend_core.data_collectors.tushare.moneyflow_daily.resolve_tushare_pro",
        return_value=object(),
    ), patch(
        "backend_core.data_collectors.tushare.moneyflow_daily.list_open_trade_dates",
        return_value=["2026-10-27", "2026-10-28", "2026-10-29"],
    ):
        assert _prev_cn_trade_date(datetime(2026, 10, 30, 17, 0, 0)) == "2026-10-29"


def test_exec_margin_defaults_to_prev_trade_day_not_ctx_today():
    ctx = WorkflowContext(
        run_id="t1",
        workflow_id=1,
        trigger_source="cron",
        trade_date=date(2026, 10, 30),
    )
    with patch(
        "backend_core.data_collectors.workflow.adapters.cn_session_closed_today",
        return_value=False,
    ), patch(
        "backend_core.data_collectors.workflow.adapters._prev_cn_trade_date",
        return_value="2026-10-29",
    ) as prev, patch(
        "backend_core.data_collectors.tushare.margin.collect_margin_for_date",
        return_value={"success": True, "upserted": 100, "trade_date": "2026-10-29"},
    ) as collect:
        out = exec_tushare_margin_daily(ctx)
    assert out.success and not out.skipped
    prev.assert_called_once()
    collect.assert_called_once()
    assert collect.call_args.args[0] == "2026-10-29"
    assert out.data.get("date_policy") == "prev_trade_day"


def test_exec_margin_respects_explicit_trade_date():
    ctx = WorkflowContext(
        run_id="t2",
        workflow_id=1,
        trigger_source="manual",
        trade_date=date(2026, 10, 30),
        params={"trade_date": "2026-10-28"},
    )
    with patch(
        "backend_core.data_collectors.workflow.adapters.cn_session_closed_today",
        return_value=False,
    ), patch(
        "backend_core.data_collectors.tushare.margin.collect_margin_for_date",
        return_value={"success": True, "upserted": 50, "trade_date": "2026-10-28"},
    ) as collect:
        out = exec_tushare_margin_daily(ctx)
    assert out.success
    assert collect.call_args.args[0] == "2026-10-28"
    assert out.data.get("date_policy") == "explicit"
