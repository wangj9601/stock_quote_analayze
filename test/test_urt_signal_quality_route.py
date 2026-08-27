# -*- coding: utf-8 -*-
"""URT 选股 API 传递 signal_quality_mode。"""

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


class _DummyDB:
    def query(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return None

    def all(self):
        return []


class _FakeUrtFrontendInterface:
    last_kwargs = {}

    @staticmethod
    def screen(db, **kwargs):
        _FakeUrtFrontendInterface.last_kwargs = dict(kwargs)
        mode = kwargs.get("signal_quality_mode") or "standard"
        return {
            "success": True,
            "data": [],
            "total": 0,
            "search_date": "2026-08-12",
            "signal_quality_mode": mode,
            "signal_quality_mode_label": (
                "精选（近支撑≤2% + 排除弱项）"
                if mode == "premium"
                else "标准（排除均线多头分中段）"
            ),
        }


def _make_client():
    app = FastAPI()
    app.include_router(stock_screening_routes.router)

    def _override_db():
        yield _DummyDB()

    app.dependency_overrides[get_db] = _override_db
    return TestClient(app)


@patch.object(stock_screening_routes, "URT_AVAILABLE", True)
@patch.object(stock_screening_routes, "URTFrontendInterface", _FakeUrtFrontendInterface)
def test_urt_strategy_route_passes_signal_quality_mode():
    client = _make_client()
    resp = client.get(
        "/api/screening/urt-strategy",
        params={"scope": "cn", "limit": 10, "signal_quality_mode": "premium"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("signal_quality_mode") == "premium"
    assert _FakeUrtFrontendInterface.last_kwargs.get("signal_quality_mode") == "premium"
