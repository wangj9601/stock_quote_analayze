# -*- coding: utf-8 -*-
"""用户站 GMS 选股 API：强制只读，忽略 trace_only=false，不写 snapshot。"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend_api.database import get_db
from backend_api.stock import stock_screening_routes


class _DummyQuery:
    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def scalar(self):
        return None

    def all(self):
        return []

    def first(self):
        return None

    def __iter__(self):
        return iter([])


class _DummyDB:
    def query(self, *args, **kwargs):
        return _DummyQuery()


class _FakeConfigManager:
    def get_config(self, config_id=None):
        return {"scoring": {}, "left_buy": {}, "right_buy": {}, "exit": {}}

    def get_config_by_id(self, config_id):
        return self.get_config(config_id)

    def resolve_config_id(self, config_id=None):
        return int(config_id) if config_id else 1

    def should_use_trace(self, config_id=None):
        return True

    def get_default_config_id(self):
        return 1

    def get_config_row(self, config_id):
        return SimpleNamespace(
            id=int(config_id or 1),
            name="default",
            is_default=True,
            is_active=True,
        )


class _FakeSession:
    def close(self):
        return None


class _FakeGmsFrontendInterface:
    last_trace_only = None
    last_kwargs = None
    call_trace_onlys = None
    empty_first_call = False

    def __init__(self, db, config, config_id=None):
        self.db = db
        self.config = config
        self.config_id = config_id

    def set_selection_config(self, min_score=0, max_results=10000):
        return None

    def get_selection_results(
        self,
        date,
        stock_pool,
        market,
        trace_only=False,
        return_meta=False,
        exclude_st=False,
        cn_board_segment=None,
    ):
        if _FakeGmsFrontendInterface.call_trace_onlys is None:
            _FakeGmsFrontendInterface.call_trace_onlys = []
        _FakeGmsFrontendInterface.call_trace_onlys.append(trace_only)
        _FakeGmsFrontendInterface.last_trace_only = trace_only
        _FakeGmsFrontendInterface.last_kwargs = {
            "date": date,
            "market": market,
            "trace_only": trace_only,
            "exclude_st": exclude_st,
        }
        call_n = len(_FakeGmsFrontendInterface.call_trace_onlys)
        if _FakeGmsFrontendInterface.empty_first_call and call_n == 1:
            rows = []
            meta = {
                "from_trace_count": 0,
                "computed_count": 0,
                "requested_count": 1,
                "trace_complete": False,
                "need_precompute": True,
                "trace_only": bool(trace_only),
            }
            return (rows, meta) if return_meta else rows
        rows = [
            {
                "symbol": "000001",
                "code": "000001",
                "date": date,
                "market_type": "CN",
                "score_total": 80.0,
                "score_accumulation": 40.0,
                "score_momentum": 40.0,
                "left_buy_signal": True,
                "right_buy_signal": False,
                "sell_signal": False,
                "buy_type": "左侧",
                "signal_strength": 0.8,
            }
        ]
        meta = {
            "from_trace_count": 1,
            "computed_count": 0 if trace_only else 1,
            "requested_count": 1,
            "trace_complete": bool(trace_only),
            "need_precompute": False,
            "trace_only": bool(trace_only),
        }
        return (rows, meta) if return_meta else rows


def _make_client():
    app = FastAPI()
    app.include_router(stock_screening_routes.router)

    def _override_db():
        yield _DummyDB()

    app.dependency_overrides[get_db] = _override_db
    return TestClient(app)


@patch.object(stock_screening_routes, "GMS_AVAILABLE", True)
@patch.object(stock_screening_routes, "GMSConfigManagerCls", _FakeConfigManager)
@patch.object(stock_screening_routes, "GMSFrontendInterface", _FakeGmsFrontendInterface)
@patch.object(stock_screening_routes, "SessionLocal", lambda: _FakeSession())
@patch.object(stock_screening_routes, "load_snapshot", return_value=None)
@patch.object(stock_screening_routes, "save_snapshot")
def test_gms_strategy_forces_trace_only_even_when_query_false(mock_save, mock_load):
    _FakeGmsFrontendInterface.last_trace_only = None
    _FakeGmsFrontendInterface.empty_first_call = False
    _FakeGmsFrontendInterface.call_trace_onlys = []
    client = _make_client()
    resp = client.get(
        "/api/screening/gms-strategy?scope=cn&date=2026-07-29&trace_only=false"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True
    assert _FakeGmsFrontendInterface.last_trace_only is True
    meta = data.get("gms_trace_meta") or {}
    assert meta.get("computed_count") == 0
    assert meta.get("trace_only") is True


@patch.object(stock_screening_routes, "GMS_AVAILABLE", True)
@patch.object(stock_screening_routes, "GMSConfigManagerCls", _FakeConfigManager)
@patch.object(stock_screening_routes, "GMSFrontendInterface", _FakeGmsFrontendInterface)
@patch.object(stock_screening_routes, "SessionLocal", lambda: _FakeSession())
@patch.object(stock_screening_routes, "load_snapshot", return_value=None)
@patch.object(stock_screening_routes, "save_snapshot")
def test_gms_strategy_does_not_save_snapshot_on_user_path(mock_save, mock_load):
    _FakeGmsFrontendInterface.empty_first_call = False
    _FakeGmsFrontendInterface.call_trace_onlys = []
    client = _make_client()
    resp = client.get(
        "/api/screening/gms-strategy?scope=cn&date=2026-07-29&trace_only=false&use_snapshot=true"
    )
    assert resp.status_code == 200
    mock_save.assert_not_called()


@patch.object(stock_screening_routes, "GMS_AVAILABLE", True)
@patch.object(stock_screening_routes, "GMSConfigManagerCls", _FakeConfigManager)
@patch.object(stock_screening_routes, "GMSFrontendInterface", _FakeGmsFrontendInterface)
@patch.object(stock_screening_routes, "SessionLocal", lambda: _FakeSession())
@patch.object(stock_screening_routes, "load_snapshot", return_value=None)
@patch.object(stock_screening_routes, "save_snapshot")
@patch.object(
    stock_screening_routes, "_resolve_gms_stock_code_from_input", return_value="000001"
)
def test_gms_strategy_date_fallback_also_forces_trace_only(
    mock_resolve, mock_save, mock_load
):
    """指定日期无结果回退最新指标日时，第二次 _run_gms 仍须 trace_only=True。"""
    _FakeGmsFrontendInterface.empty_first_call = True
    _FakeGmsFrontendInterface.call_trace_onlys = []

    class _DB(_DummyDB):
        def query(self, *args, **kwargs):
            q = _DummyQuery()
            # func.max(...).scalar() → 回退日期
            q.scalar = lambda: "2026-07-28"
            return q

    app = FastAPI()
    app.include_router(stock_screening_routes.router)

    def _override_db():
        yield _DB()

    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app)
    resp = client.get(
        "/api/screening/gms-strategy?code=000001&date=2026-07-29&trace_only=false"
    )
    assert resp.status_code == 200
    assert _FakeGmsFrontendInterface.call_trace_onlys == [True, True]
