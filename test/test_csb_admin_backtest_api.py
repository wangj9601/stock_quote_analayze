# -*- coding: utf-8 -*-
"""CSB admin 回测 API 基础导入与创建体校验（不依赖真实跑批）。"""

from backend_api.admin.csb_admin_routes import BacktestCreateBody, router


def test_csb_admin_router_prefix():
    assert router.prefix == "/api/admin/csb"


def test_backtest_create_body_defaults():
    body = BacktestCreateBody(start_date="2024-01-01", end_date="2024-06-01")
    assert body.exit_mode == "hit_rate"
    assert body.use_trace is True
    assert body.stock_pool_mode in (None, "all") or body.stock_pool_mode == "all"
