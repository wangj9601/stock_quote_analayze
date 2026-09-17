# -*- coding: utf-8 -*-
"""个股分析统一 bundle：编排容错与路由签名冒烟。"""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock, patch

from backend_core.analysis.stock_analysis_bundle import (
    build_stock_analysis_bundle,
    _err_section,
)


def test_err_section_shape():
    out = _err_section("boom")
    assert out["ok"] is False
    assert out["error"] == "boom"
    assert out["payload"] is None


def test_build_bundle_empty_code():
    db = MagicMock()
    out = build_stock_analysis_bundle(db, code="")
    assert out["success"] is False
    assert out["http_status"] == 400


def test_build_bundle_ambiguous():
    db = MagicMock()
    with patch(
        "backend_core.analysis.stock_analysis_bundle._resolve_stock",
        return_value={
            "status": "ambiguous",
            "message": "匹配到多只",
            "candidates": [{"code": "600000"}, {"code": "600001"}],
        },
    ):
        out = build_stock_analysis_bundle(db, code="浦发")
    assert out["success"] is False
    assert out["http_status"] == 400
    assert len(out["candidates"]) == 2


def test_build_bundle_not_found():
    db = MagicMock()
    with patch(
        "backend_core.analysis.stock_analysis_bundle._resolve_stock",
        return_value={"status": "not_found", "message": "未找到"},
    ):
        out = build_stock_analysis_bundle(db, code="999999")
    assert out["success"] is False
    assert out["http_status"] == 404


def test_build_bundle_partial_detail_errors():
    """明细模块失败时仍返回 success，并带区块 error；trade_plan 仍尝试合成。"""
    db = MagicMock()

    strategy = {
        "stock": {"code": "600519", "name": "贵州茅台"},
        "trade_date": "2026-09-17",
        "results": [],
        "hit_count": 0,
        "any_hit": False,
    }

    def fake_run(fn, label):
        if label == "rs":
            return {"ok": False, "data": None, "error": "rs down", "payload": None}
        if label == "fund_flow":
            return {"ok": True, "data": {"code": "600519", "series": []}, "error": None, "payload": {}}
        if label == "levels":
            return {
                "ok": True,
                "data": {"nearest_support": 100.0, "nearest_resistance": 110.0},
                "error": None,
                "payload": {"ok": True, "data": {"nearest_support": 100.0}},
            }
        if label == "pattern":
            return {
                "ok": True,
                "items": [],
                "invalidated_count": 0,
                "code": "600519",
                "name": "贵州茅台",
                "asof": "2026-09-17",
                "price_adjust": "qfq",
                "tactical": {"short_bias": "neutral"},
                "error": None,
                "payload": {"items": [], "tactical": {"short_bias": "neutral"}},
            }
        if label == "gann":
            return _err_section("gann down")
        if label == "swing":
            return {
                "ok": True,
                "data": {"market_structure": {"ok": True, "trend": "up"}},
                "code": "600519",
                "name": "贵州茅台",
                "asof": "2026-09-17",
                "error": None,
                "payload": {"market_structure": {"ok": True}},
            }
        return _err_section(label)

    with patch(
        "backend_core.analysis.stock_analysis_bundle._resolve_stock",
        return_value={"status": "ok", "code": "600519", "name": "贵州茅台", "market": "CN"},
    ), patch(
        "backend_core.analysis.stock_multi_strategy.collect_stock_multi_strategy_check",
        return_value=strategy,
    ), patch(
        "backend_core.analysis.stock_analysis_bundle._run_with_own_session",
        side_effect=fake_run,
    ), patch(
        "backend_core.analysis.stock_analysis_bundle._build_trade_plan",
        return_value={
            "ok": True,
            "plan": {"short_term": {"summary": "ok"}},
            "code": "600519",
            "name": "贵州茅台",
            "trade_date": "2026-09-17",
            "error": None,
        },
    ):
        out = build_stock_analysis_bundle(db, code="600519", date="2026-09-17")

    assert out["success"] is True
    data = out["data"]
    assert data["strategy"]["stock"]["code"] == "600519"
    assert data["rs"]["ok"] is False
    assert "rs" in (data["rs"]["error"] or "")
    assert data["fund_flow"]["ok"] is True
    assert data["levels"]["ok"] is True
    assert data["pattern"]["ok"] is True
    assert data["gann"]["ok"] is False
    assert data["swing"]["ok"] is True
    assert data["trade_plan"]["ok"] is True
    assert data["trade_plan"]["plan"]["short_term"]["summary"] == "ok"


def test_route_registered():
    from backend_api.stock import board_analysis_routes as routes

    paths = {getattr(r, "path", None) for r in routes.router.routes}
    assert any(p and p.endswith("/stock-analysis-bundle") for p in paths)
    sig = inspect.signature(routes.get_stock_analysis_bundle)
    assert "code" in sig.parameters
    assert "date" in sig.parameters
    assert "use_realtime" in sig.parameters
    assert "strategies" in sig.parameters


def test_build_importable():
    from backend_core.analysis.stock_analysis_bundle import build_stock_analysis_bundle as fn

    assert callable(fn)
