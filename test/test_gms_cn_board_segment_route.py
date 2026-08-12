"""
GMS 选股路由：scope=cn 时 cn_board_segment 板块过滤回归测试
"""

import os
import sys
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
        return iter(())


class _DummyDB:
    def query(self, *args, **kwargs):
        return _DummyQuery()


class _FakeConfigManager:
    def get_config(self, config_id=None):
        return {"scoring": {"mechanism": "tiered_dual_max"}}

    def resolve_config_id(self, config_id):
        return config_id or 1

    def get_config_row(self, config_id):
        return None


class _FakeSession:
    def close(self):
        return None


class _FakeGmsFrontendInterface:
    last_market = None
    last_stock_pool = None

    def __init__(self, db, config, config_id=None):
        self.db = db
        self.config = config

    def set_selection_config(self, min_score=0, max_results=10000):
        return None

    def get_selection_results(self, date, stock_pool, market, trace_only=False, return_meta=False, exclude_st=False):
        _FakeGmsFrontendInterface.last_market = market
        _FakeGmsFrontendInterface.last_stock_pool = stock_pool
        rows = [{
            "symbol": "300001",
            "code": "300001",
            "date": date,
            "market_type": "CN",
            "score_total": 55.0,
            "score_accumulation": 55.0,
            "score_momentum": 0.0,
            "accumulation_grade": "",
            "momentum_grade": "",
            "left_buy_signal": True,
            "right_buy_signal": False,
            "sell_signal": False,
            "buy_type": "左侧",
            "signal_strength": 0.55,
            "delta": -0.05,
            "d": 1.0,
            "ratio_d20": -0.01,
            "ratio_d1": -0.01,
            "ratio_d": -0.02,
            "fz_ratio": 1.8,
            "rising_days": 9,
            "falling_days": 11,
            "avg_volume_20d": 100000.0,
            "current_volume": 70000.0,
            "score_detail": {"score_total": 55.0},
        }]
        meta = {
            "from_trace_count": 0,
            "computed_count": 1,
            "requested_count": 1,
            "trace_complete": False,
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
@patch.object(
    stock_screening_routes,
    "_gms_cn_stock_pool_by_board_segments",
    lambda db, target_date, board_segments: ["300001", "600000"],
)
def test_gms_strategy_scope_cn_cyb_passes_filtered_stock_pool():
    client = _make_client()
    resp = client.get("/api/screening/gms-strategy?scope=cn&cn_board_segment=CYB&date=2026-04-23")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert _FakeGmsFrontendInterface.last_market == "cn"
    assert _FakeGmsFrontendInterface.last_stock_pool == ["300001", "600000"]
    assert data["parameters"]["cn_board_segment"] == "CYB"
    assert data["parameters"]["cn_board_segments"] == ["CYB"]


@patch.object(stock_screening_routes, "GMS_AVAILABLE", True)
@patch.object(stock_screening_routes, "GMSConfigManagerCls", _FakeConfigManager)
@patch.object(stock_screening_routes, "GMSFrontendInterface", _FakeGmsFrontendInterface)
@patch.object(stock_screening_routes, "SessionLocal", lambda: _FakeSession())
@patch.object(
    stock_screening_routes,
    "_gms_cn_stock_pool_by_board_segments",
    lambda db, target_date, board_segments: ["430047", "920799"],
)
def test_gms_strategy_scope_cn_bj_passes_filtered_stock_pool():
    client = _make_client()
    resp = client.get("/api/screening/gms-strategy?scope=cn&cn_board_segment=BJ&date=2026-04-23")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert _FakeGmsFrontendInterface.last_market == "cn"
    assert _FakeGmsFrontendInterface.last_stock_pool == ["430047", "920799"]
    assert data["parameters"]["cn_board_segment"] == "BJ"
    assert data["parameters"]["cn_board_segments"] == ["BJ"]


@patch.object(stock_screening_routes, "GMS_AVAILABLE", True)
@patch.object(stock_screening_routes, "GMSConfigManagerCls", _FakeConfigManager)
@patch.object(stock_screening_routes, "GMSFrontendInterface", _FakeGmsFrontendInterface)
@patch.object(stock_screening_routes, "SessionLocal", lambda: _FakeSession())
def test_gms_strategy_scope_cn_invalid_segment_returns_400():
    client = _make_client()
    resp = client.get("/api/screening/gms-strategy?scope=cn&cn_board_segment=INVALID&date=2026-04-23")
    assert resp.status_code == 400


@patch.object(stock_screening_routes, "GMS_AVAILABLE", True)
@patch.object(stock_screening_routes, "GMSConfigManagerCls", _FakeConfigManager)
@patch.object(stock_screening_routes, "GMSFrontendInterface", _FakeGmsFrontendInterface)
@patch.object(stock_screening_routes, "SessionLocal", lambda: _FakeSession())
@patch.object(
    stock_screening_routes,
    "_gms_cn_stock_pool_by_board_segments",
    lambda db, target_date, board_segments: [],
)
def test_gms_strategy_scope_cn_empty_segment_pool_returns_empty():
    client = _make_client()
    resp = client.get("/api/screening/gms-strategy?scope=cn&cn_board_segment=KCB&date=2026-04-23")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"] == []
    assert data["cn_board_segment"] == "KCB"
    assert data["cn_board_segments"] == ["KCB"]


@patch.object(stock_screening_routes, "GMS_AVAILABLE", True)
@patch.object(stock_screening_routes, "GMSConfigManagerCls", _FakeConfigManager)
@patch.object(stock_screening_routes, "GMSFrontendInterface", _FakeGmsFrontendInterface)
@patch.object(stock_screening_routes, "SessionLocal", lambda: _FakeSession())
@patch.object(
    stock_screening_routes,
    "_gms_cn_stock_pool_by_board_segments",
    lambda db, target_date, board_segments: ["300001", "688001"],
)
def test_gms_strategy_scope_cn_multi_segments_union():
    client = _make_client()
    resp = client.get(
        "/api/screening/gms-strategy?scope=cn&cn_board_segment=CYB&cn_board_segment=KCB&date=2026-04-23"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert _FakeGmsFrontendInterface.last_stock_pool == ["300001", "688001"]
    assert data["parameters"]["cn_board_segment"] == "CYB,KCB"
    assert data["parameters"]["cn_board_segments"] == ["CYB", "KCB"]
