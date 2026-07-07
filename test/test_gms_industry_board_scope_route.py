"""
GMS 选股路由：行业板块 scope 最小回归测试
验证 /api/screening/gms-strategy?scope=industry_board&industry_board_code=IT服务
会按成分股池计算且 market=cn。
"""

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
from backend_api.models import IndustryBoardConstituent
from backend_api.stock import stock_screening_routes


class _DummyQuery:
    def __init__(self, rows=None):
        self._rows = rows or []

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def scalar(self):
        return None

    def all(self):
        return self._rows

    def first(self):
        return None


class _IndustryBoardDB:
    def query(self, *args, **kwargs):
        if not args:
            return _DummyQuery()
        if args[0] is IndustryBoardConstituent:
            return _DummyQuery([
                SimpleNamespace(stock_code="000001"),
                SimpleNamespace(stock_code="688158"),
            ])
        return _DummyQuery()


class _FakeConfigManager:
    def resolve_config_id(self, config_id):
        return config_id or 1

    def get_config(self, config_id=None):
        return {}

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
            "symbol": stock_pool[0] if stock_pool else "000001",
            "code": stock_pool[0] if stock_pool else "000001",
            "date": date,
            "market_type": "CN",
            "score_total": 60.0,
            "score_accumulation": 60.0,
            "score_momentum": 0.0,
            "accumulation_grade": "A",
            "momentum_grade": "",
            "left_buy_signal": True,
            "right_buy_signal": False,
            "sell_signal": False,
            "buy_type": "左侧",
            "signal_strength": 0.6,
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
            "score_detail": {"score_total": 60.0},
        }]
        meta = {
            "from_trace_count": 0,
            "computed_count": 1,
            "requested_count": len(stock_pool or []),
            "trace_complete": False,
        }
        return (rows, meta) if return_meta else rows


def _make_client():
    app = FastAPI()
    app.include_router(stock_screening_routes.router)

    def _override_db():
        yield _IndustryBoardDB()

    app.dependency_overrides[get_db] = _override_db
    return TestClient(app)


@patch.object(stock_screening_routes, "GMS_AVAILABLE", True)
@patch.object(stock_screening_routes, "GMSConfigManagerCls", _FakeConfigManager)
@patch.object(stock_screening_routes, "GMSFrontendInterface", _FakeGmsFrontendInterface)
@patch.object(stock_screening_routes, "SessionLocal", lambda: _FakeSession())
def test_gms_strategy_scope_industry_board_requires_code():
    client = _make_client()
    resp = client.get("/api/screening/gms-strategy?scope=industry_board&date=2026-04-23")
    assert resp.status_code == 400


def _fake_resolve_industry_board_codes(_db, codes):
    mapping = {"IT服务": "BK9001", "半导体": "BK9002"}
    out = []
    for c in codes:
        v = mapping.get(c, c)
        if v and v not in out:
            out.append(v)
    return out


@patch(
    "backend_api.utils.bk_board_code.resolve_industry_board_codes",
    side_effect=_fake_resolve_industry_board_codes,
)
@patch.object(stock_screening_routes, "GMS_AVAILABLE", True)
@patch.object(stock_screening_routes, "GMSConfigManagerCls", _FakeConfigManager)
@patch.object(stock_screening_routes, "GMSFrontendInterface", _FakeGmsFrontendInterface)
@patch.object(stock_screening_routes, "SessionLocal", lambda: _FakeSession())
def test_gms_strategy_scope_industry_board_uses_constituents(_mock_resolve):
    client = _make_client()
    resp = client.get(
        "/api/screening/gms-strategy"
        "?scope=industry_board&industry_board_code=IT%E6%9C%8D%E5%8A%A1&date=2026-04-23"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert _FakeGmsFrontendInterface.last_market == "cn"
    assert _FakeGmsFrontendInterface.last_stock_pool == ["000001", "688158"]
    assert isinstance(data["data"], list)
    assert len(data["data"]) == 1
    assert data["parameters"]["industry_board_codes"] == ["BK9001"]


@patch(
    "backend_api.utils.bk_board_code.resolve_industry_board_codes",
    side_effect=_fake_resolve_industry_board_codes,
)
@patch.object(stock_screening_routes, "GMS_AVAILABLE", True)
@patch.object(stock_screening_routes, "GMSConfigManagerCls", _FakeConfigManager)
@patch.object(stock_screening_routes, "GMSFrontendInterface", _FakeGmsFrontendInterface)
@patch.object(stock_screening_routes, "SessionLocal", lambda: _FakeSession())
def test_gms_strategy_scope_industry_board_accepts_multiple_codes(_mock_resolve):
    client = _make_client()
    resp = client.get(
        "/api/screening/gms-strategy"
        "?scope=industry_board"
        "&industry_board_code=IT%E6%9C%8D%E5%8A%A1"
        "&industry_board_code=%E5%8D%8A%E5%AF%BC%E4%BD%93"
        "&date=2026-04-23"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["parameters"]["industry_board_codes"] == ["BK9001", "BK9002"]


@patch(
    "backend_api.utils.bk_board_code.resolve_industry_board_codes",
    side_effect=_fake_resolve_industry_board_codes,
)
@patch.object(stock_screening_routes, "GMS_AVAILABLE", True)
@patch.object(stock_screening_routes, "GMSConfigManagerCls", _FakeConfigManager)
@patch.object(stock_screening_routes, "GMSFrontendInterface", _FakeGmsFrontendInterface)
@patch.object(stock_screening_routes, "SessionLocal", lambda: _FakeSession())
def test_gms_strategy_scope_industry_board_filters_by_cn_board_segment(_mock_resolve):
    client = _make_client()
    resp = client.get(
        "/api/screening/gms-strategy"
        "?scope=industry_board&industry_board_code=IT%E6%9C%8D%E5%8A%A1"
        "&cn_board_segment=KCB&date=2026-04-23"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert _FakeGmsFrontendInterface.last_stock_pool == ["688158"]
    assert data["parameters"]["cn_board_segment"] == "KCB"


@patch(
    "backend_api.utils.bk_board_code.resolve_industry_board_codes",
    side_effect=_fake_resolve_industry_board_codes,
)
@patch.object(stock_screening_routes, "GMS_AVAILABLE", True)
@patch.object(stock_screening_routes, "GMSConfigManagerCls", _FakeConfigManager)
@patch.object(stock_screening_routes, "GMSFrontendInterface", _FakeGmsFrontendInterface)
@patch.object(stock_screening_routes, "SessionLocal", lambda: _FakeSession())
def test_gms_strategy_scope_industry_board_segment_empty_pool(_mock_resolve):
    client = _make_client()
    resp = client.get(
        "/api/screening/gms-strategy"
        "?scope=industry_board&industry_board_code=IT%E6%9C%8D%E5%8A%A1"
        "&cn_board_segment=CYB&date=2026-04-23"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"] == []
    assert "创业板" in data["message"]
