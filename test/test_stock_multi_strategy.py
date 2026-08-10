# -*- coding: utf-8 -*-
"""个股四策略聚合：汇总解析与路由签名冒烟。"""

import inspect

from backend_core.analysis.stock_multi_strategy import (
    _pick_score,
    _score_display,
    summarize_strategy_check,
)


def test_summarize_gms_hit_and_score():
    row = {
        "symbol": "600519",
        "score_total": 82.5,
        "buy_type": "左侧",
        "left_buy_signal": True,
    }
    out = summarize_strategy_check("gms", row, stock_code="600519")
    assert out["hit"] is True
    assert out["label"] == "左侧"
    assert out["score"] == 82.5
    assert "82.5" in out["score_display"]
    assert out["trace_url"] and "stock_gms_trace.html" in out["trace_url"]


def test_summarize_gms_miss_keeps_score():
    row = {"symbol": "600519", "score_total": 55.0, "left_buy_signal": False}
    out = summarize_strategy_check("gms", row, stock_code="600519")
    assert out["hit"] is False
    assert out["score"] == 55.0
    assert "未触发" in out["reason"]


def test_summarize_urt_hit():
    out = summarize_strategy_check(
        "urt", {"code": "000001", "buy_signal": True, "score_total": 70}, stock_code="000001"
    )
    assert out["hit"] is True
    assert out["label"] == "买点"


def test_summarize_sbbr_entry_and_watch():
    entry = summarize_strategy_check(
        "sbbr",
        {"code": "600000", "entry_signal": True, "size_ok": True, "volume_ratio": 1.8},
        stock_code="600000",
    )
    assert entry["hit"] is True
    assert entry["label"] == "入场"
    assert "量比" in entry["score_display"]

    watch = summarize_strategy_check(
        "sbbr",
        {"code": "600000", "entry_signal": False, "bottom_matched": True, "size_ok": False},
        stock_code="600000",
    )
    assert watch["hit"] is True
    assert watch["label"] == "筑底"


def test_summarize_sbbr_no_unified_score_when_empty():
    out = summarize_strategy_check("sbbr", None, stock_code="600000")
    assert out["hit"] is False
    assert out["score"] is None
    assert out["score_display"] == "--"


def test_summarize_rpe_lead_and_miss():
    hit = summarize_strategy_check(
        "rpe",
        {"code": "000001", "signal_type": "lead", "watch_only": True, "z_score": 1.25},
        stock_code="000001",
    )
    assert hit["hit"] is True
    assert hit["label"] == "领涨观察"
    assert hit["score"] == 1.25
    assert "Z=" in hit["score_display"]

    miss = summarize_strategy_check(
        "rpe", {"code": "000001", "signal_type": "none"}, stock_code="000001"
    )
    assert miss["hit"] is False


def test_summarize_error_and_message():
    err = summarize_strategy_check("gms", None, stock_code="1", error="timeout")
    assert err["hit"] is False
    assert err["error"] == "timeout"
    assert "失败" in err["reason"]

    msg = summarize_strategy_check(
        "rpe", None, stock_code="600519", message="无板块归属"
    )
    assert msg["hit"] is False
    assert "板块" in msg["reason"]


def test_pick_score_helpers():
    assert _pick_score("gms", {"score_total": "9"}) == 9.0
    assert _pick_score("sbbr", {"volume_ratio": 1.2}) == 1.2
    assert _pick_score("rpe", {"zscore": 0.5}) == 0.5
    assert _score_display("gms", None, None) == "--"
    assert "做小" in _score_display("sbbr", None, {"size_ok": False})


def test_route_registered():
    from backend_api.stock import board_analysis_routes as routes

    paths = {getattr(r, "path", None) for r in routes.router.routes}
    assert any(p and p.endswith("/multi-strategy-check") for p in paths)
    sig = inspect.signature(routes.get_multi_strategy_check)
    assert "code" in sig.parameters
    assert "date" in sig.parameters
    assert "strategies" in sig.parameters


def test_collect_importable():
    from backend_core.analysis.stock_multi_strategy import collect_stock_multi_strategy_check

    assert callable(collect_stock_multi_strategy_check)
