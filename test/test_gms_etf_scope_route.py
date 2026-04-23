"""
GMS 选股路由：ETF scope 最小回归测试
验证 /api/screening/gms-strategy?scope=etf 会进入 ETF 计算分支。
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


class _DummyDB:
    def query(self, *args, **kwargs):
        return _DummyQuery()


class _FakeConfigManager:
    def get_config(self):
        return {}


class _FakeSession:
    def close(self):
        return None


class _FakeGmsFrontendInterface:
    last_market = None

    def __init__(self, db, config):
        self.db = db
        self.config = config

    def set_selection_config(self, min_score=0, max_results=10000):
        return None

    def get_selection_results(self, date, stock_pool, market, trace_only=False, return_meta=False):
        _FakeGmsFrontendInterface.last_market = market
        rows = [{
            "symbol": "510300",
            "code": "510300",
            "date": date,
            "market_type": "ETF",
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
            "score_detail": {
                "score_total": 55.0,
                "ratio_d": -0.02,
                "avg_volume_20d": 100000.0,
                "current_volume": 70000.0,
            },
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
def test_gms_strategy_scope_etf_routes_to_etf_market():
    client = _make_client()
    resp = client.get("/api/screening/gms-strategy?scope=etf&date=2026-04-23")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)
    assert len(data["data"]) == 1
    assert data["data"][0]["symbol"] == "510300"
    assert _FakeGmsFrontendInterface.last_market == "etf"

