"""观察池请求路径不得再执行 ALTER TABLE。"""

from __future__ import annotations

import inspect

from backend_api.stock import board_fund_flow, board_gate_routes, board_observe_routes, stock_fund_flow
from backend_core.board_observe import compute_daily, storage


def test_market_read_endpoints_are_sync():
    fns = [
        stock_fund_flow.get_stock_fund_flow_rank,
        stock_fund_flow.get_stock_fund_flow_trend_series,
        board_fund_flow.get_board_fund_flow_rank,
        board_fund_flow.get_board_fund_flow_trend_series,
        board_fund_flow.get_board_constituent_fund_flow,
        board_gate_routes.list_board_gates,
        board_gate_routes.get_board_gate_daily,
        board_observe_routes.list_observe_candidates,
    ]
    for fn in fns:
        assert not inspect.iscoroutinefunction(fn), fn.__name__


def test_request_and_batch_do_not_call_ensure_ddl():
    sources = [
        inspect.getsource(board_observe_routes),
        inspect.getsource(compute_daily),
        inspect.getsource(storage.upsert_observe_candidates),
        inspect.getsource(storage.load_prior_eligibility),
        inspect.getsource(storage.apply_observe_flag),
    ]
    for src in sources:
        assert "ensure_board_observe_tables(" not in src
