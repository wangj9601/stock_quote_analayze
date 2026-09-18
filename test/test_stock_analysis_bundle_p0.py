# -*- coding: utf-8 -*-
"""bundle P0：策略读缓存参数、共享 bars、战术层复用策略摘要。"""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock, patch

from backend_core.analysis.stock_analysis_bundle import (
    _prepare_shared_bars,
    _strategy_snapshots_from_data,
    build_stock_analysis_bundle,
)
from backend_core.analysis.stock_multi_strategy import (
    _fetch_urt_raw,
)


def test_urt_fetch_defaults_prefer_cache():
    """默认应 prefer_cache=True、force_realtime=False（读 trace）。"""
    db = MagicMock()
    from backend_core.strategies.urt import frontend_interface as urt_fi

    with patch.object(
        urt_fi.URTFrontendInterface,
        "screen",
        return_value={"data": [{"code": "600519", "buy_signal": True, "score_total": 70}]},
    ) as screen:
        row = _fetch_urt_raw(db, "600519", "2026-09-17")
    assert row and row["code"] == "600519"
    kwargs = screen.call_args.kwargs
    assert kwargs.get("prefer_cache") is True
    assert kwargs.get("force_realtime") is False


def test_urt_fetch_force_realtime_when_requested():
    db = MagicMock()
    from backend_core.strategies.urt import frontend_interface as urt_fi

    with patch.object(
        urt_fi.URTFrontendInterface,
        "screen",
        return_value={"data": []},
    ) as screen:
        _fetch_urt_raw(db, "600519", "2026-09-17", force_realtime=True, prefer_cache=True)
    kwargs = screen.call_args.kwargs
    assert kwargs.get("force_realtime") is True
    assert kwargs.get("prefer_cache") is False


def test_strategy_snapshots_from_results():
    snaps = _strategy_snapshots_from_data(
        {
            "results": [
                {"strategy": "gms", "score": 80, "hit": True},
                {"strategy": "rpe", "score": 1.2, "hit": False},
                {"strategy": "urt", "score": 1},
            ]
        }
    )
    assert snaps["gms"]["score"] == 80
    assert snaps["rpe"]["score"] == 1.2
    assert "urt" not in snaps


def test_tactical_enrichment_uses_snapshots_without_eval():
    from backend_api.stock.pattern_routes import _tactical_enrichment

    bars = [
        {"date": f"2026-01-{i:02d}", "high": 10 + i, "low": 9, "close": 10, "volume": 100}
        for i in range(1, 40)
    ]
    db = MagicMock()
    snaps = {
        "gms": {"score": 88.0, "hit": True, "label": "左侧", "detail": {"score_total": 88}},
        "rpe": {"score": 1.5, "label": "lead", "detail": {"signal_type": "lead", "z_score": 1.5}},
    }
    with patch(
        "backend_core.analysis.stock_multi_strategy._eval_gms"
    ) as eg, patch(
        "backend_core.analysis.stock_multi_strategy._eval_rpe"
    ) as er:
        vp, conf, rpe, gms, classic = _tactical_enrichment(
            db, bars, "600519", "2026-09-17", strategy_snapshots=snaps
        )
    eg.assert_not_called()
    er.assert_not_called()
    assert gms is not None and float(gms["score"]) == 88.0
    assert rpe is not None and rpe.get("signal_type") == "lead"


def test_prepare_shared_bars_called_in_bundle():
    db = MagicMock()
    strategy = {
        "stock": {"code": "600519", "name": "贵州茅台"},
        "trade_date": "2026-09-17",
        "results": [
            {"strategy": "gms", "score": 70, "hit": False},
            {"strategy": "rpe", "score": 0.1, "hit": False},
        ],
        "hit_count": 0,
        "any_hit": False,
    }
    shared = {
        "code": "600519",
        "name": "贵州茅台",
        "asof": "2026-09-17",
        "adjust": "qfq",
        "bars_raw": [{"date": "2026-09-01", "high": 1, "low": 1, "close": 1, "volume": 1}],
        "bars": [{"date": "2026-09-01", "high": 1, "low": 1, "close": 1, "volume": 1}],
        "adj_meta": None,
        "realtime_meta": None,
        "lookback": 750,
    }

    captured = {}

    def fake_run(fn, label):
        # 捕获闭包是否把 shared 传进 levels/pattern/gann
        captured[label] = True
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
        if label == "levels":
            return {
                "ok": True,
                "data": {"nearest_support": 1},
                "error": None,
                "payload": {"ok": True, "data": {}},
            }
        if label == "gann":
            return {
                "ok": True,
                "data": {"gann_trend": {"ok": True}},
                "code": "600519",
                "name": "贵州茅台",
                "asof": "2026-09-17",
                "error": None,
                "payload": {},
            }
        if label == "swing":
            return {
                "ok": True,
                "data": {"market_structure": {"ok": True}},
                "code": "600519",
                "name": "贵州茅台",
                "asof": "2026-09-17",
                "error": None,
                "payload": {},
            }
        if label == "rs":
            return {"ok": True, "data": {"rs_rating": 90}, "error": None, "payload": {}}
        if label == "fund_flow":
            return {"ok": True, "data": {"series": []}, "error": None, "payload": {}}
        return {"ok": False, "error": label, "payload": None}

    with patch(
        "backend_core.analysis.stock_analysis_bundle._resolve_stock",
        return_value={"status": "ok", "code": "600519", "name": "贵州茅台", "market": "CN"},
    ), patch(
        "backend_core.analysis.stock_multi_strategy.collect_stock_multi_strategy_check",
        return_value=strategy,
    ), patch(
        "backend_core.analysis.stock_analysis_bundle._prepare_shared_bars",
        return_value=shared,
    ) as prep, patch(
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
    prep.assert_called_once()
    assert "pattern" in captured and "levels" in captured


def test_prepare_shared_bars_signature():
    sig = inspect.signature(_prepare_shared_bars)
    assert "use_realtime" in sig.parameters
    assert "lookback" in sig.parameters


def test_realtime_quote_cache_roundtrip():
    from backend_core.analysis import realtime_bars as rb

    rb.clear_realtime_quote_cache()
    rb._quote_cache_set("600519", {"code": "600519", "current_price": 100.0})
    hit = rb._quote_cache_get("600519")
    assert hit and hit["current_price"] == 100.0
    rb.clear_realtime_quote_cache("600519")
    assert rb._quote_cache_get("600519") is None


def test_kline_hist_no_cast_on_date_filter():
    """源码冒烟：日线查询不再对 HistoricalQuotes.date 做 func.cast。"""
    import pathlib

    src = pathlib.Path("backend_api/stock/stock_manage.py").read_text(encoding="utf-8")
    assert "func.cast(HistoricalQuotes.date" not in src
    assert "HistoricalQuotes.date >=" in src
