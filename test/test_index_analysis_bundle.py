# -*- coding: utf-8 -*-
"""指数分析 bundle：身份隔离、空态广度、市场环境无交易字段。"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend_core.analysis.index_bars import (  # noqa: E402
    merge_index_realtime_bar,
    normalize_index_display_code,
    to_index_ts_code,
)
from backend_core.analysis.index_analysis_bundle import (  # noqa: E402
    _build_market_view,
    _compute_breadth_and_leaders,
    _compute_sector_contrib,
    _uses_stock_historical_quotes,
    build_index_analysis_bundle,
    compute_index_key_levels,
)


def test_normalize_and_ts_code_mapping():
    assert normalize_index_display_code("sh000001") == "000001"
    assert normalize_index_display_code("000001.SH") == "000001"
    assert to_index_ts_code("000001") == "000001.SH"
    assert to_index_ts_code("399001") == "399001.SZ"
    assert to_index_ts_code("000300") == "000300.SH"


def test_never_uses_stock_historical_quotes_flag():
    assert _uses_stock_historical_quotes() is False


@patch("backend_core.analysis.index_analysis_bundle.load_index_bars_with_realtime")
@patch("backend_core.analysis.index_analysis_bundle.fetch_index_realtime_quote")
@patch("backend_core.analysis.index_analysis_bundle.resolve_index_identity")
def test_compute_index_key_levels_uses_index_anchor_not_stock(
    mock_ident, mock_quote, mock_bars
):
    """000001 指数关位必须以指数点位为锚，不能落到平安银行 ~11 元。"""
    mock_ident.return_value = {
        "ok": True,
        "code": "000001",
        "ts_code": "000001.SH",
        "name": "上证指数",
    }
    mock_quote.return_value = {
        "current_price": 3707.48,
        "change": -59.75,
        "change_percent": -1.59,
        "pre_close": 3767.23,
        "trade_date": "2026-10-15",
        "source": "index_realtime_quotes",
    }
    bars = _fake_bars(80)
    for b in bars:
        b["close"] = 3700 + (abs(hash(b["date"])) % 20)
        b["open"] = b["close"] - 1
        b["high"] = b["close"] + 5
        b["low"] = b["close"] - 5
    mock_bars.return_value = (bars, None, "2026-10-15")

    captured = {}

    class _Svc:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get_key_levels_only(self, code, **kwargs):
            captured["code"] = code
            captured["anchor"] = kwargs.get("anchor_price")
            captured["hist_len"] = len(kwargs.get("historical_data") or [])
            captured["adjust"] = kwargs.get("price_adjust")
            return {
                "success": True,
                "data": {
                    "current_price": kwargs.get("anchor_price"),
                    "nearest_support": 3600.0,
                    "nearest_resistance": 3800.0,
                    "support_levels": [3600.0],
                    "resistance_levels": [3800.0],
                    "kde_ok": True,
                    "classic_levels": {"ok": True},
                    "volume_profile": {"ok": True, "poc": 3700.0},
                },
            }

    with patch(
        "backend_api.stock.stock_analysis.StockAnalysisService",
        _Svc,
    ):
        db = MagicMock()
        out = compute_index_key_levels(db, code="000001", kde_lookback=46, vp_lookback=46)

    assert out["success"] is True
    assert captured["code"] == "000001"
    assert captured["adjust"] == "none"
    assert captured["anchor"] == pytest.approx(3707.48)
    assert captured["hist_len"] >= 20
    assert out["data"]["asset_type"] == "index"
    assert out["data"]["current_price"] == pytest.approx(3707.48)
    assert out["data"]["current_price"] > 100  # 绝非个股 11 元区间


def test_merge_index_realtime_bar():
    bars = [
        {
            "date": "2026-10-14",
            "open": 1,
            "high": 2,
            "low": 1,
            "close": 1.5,
            "volume": 10,
            "amount": 100,
        }
    ]
    quote = {
        "trade_date": "2026-10-15",
        "current_price": 3700.0,
        "open": 3690.0,
        "high": 3710.0,
        "low": 3680.0,
        "volume": 1,
        "amount": 2,
        "change_percent": -1.2,
        "source": "index_realtime_quotes",
        "update_time": "2026-10-15 10:00:00",
    }
    out, meta = merge_index_realtime_bar(bars, quote)
    assert meta and meta.get("merged") is True
    assert out[-1]["date"] == "2026-10-15"
    assert out[-1]["close"] == 3700.0
    assert len(out) == 2


def test_breadth_empty_and_with_members():
    b0, l0 = _compute_breadth_and_leaders([])
    assert b0["available"] is False
    assert l0["available"] is False

    members = [
        {"code": "600000", "name": "A", "change_percent": 2.0, "amount": 1e8},
        {"code": "600001", "name": "B", "change_percent": -1.0, "amount": 2e8},
        {"code": "600002", "name": "C", "change_percent": 0.0, "amount": 1e8},
    ]
    b1, l1 = _compute_breadth_and_leaders(members)
    assert b1["available"] is True
    assert b1["up_count"] == 1
    assert b1["down_count"] == 1
    assert b1["flat_count"] == 1
    assert l1["available"] is True
    assert l1["gainers"][0]["code"] == "600000"


def test_market_view_has_no_trade_fields():
    mv = _build_market_view(
        code="000300",
        name="沪深300",
        asof="2026-10-15",
        levels={"ok": True, "data": {"key_levels": {"nearest_support": 4000, "nearest_resistance": 4200}}},
        pattern={"ok": True, "tactical": {"short_bias": "bullish"}},
        swing={
            "ok": True,
            "data": {"market_structure": {"trend": "up"}},
        },
        gann={"ok": True, "data": {"gann_trend": {"verdict": {"bias": "bullish", "summary": "ok"}}}},
        breadth={"available": True, "up_ratio": 0.6},
    )
    assert mv["ok"] is True
    assert mv["title"] == "指数环境研判"
    assert mv["bias"] in ("bullish", "bearish", "neutral")
    assert mv["entry"] is None
    assert mv["stop"] is None
    assert mv["target"] is None
    assert mv["position"] is None
    assert mv["action"] is None


def test_sector_contrib_disclaimer_and_weighting():
    db = MagicMock()
    # stock -> industry board mapping
    db.execute.return_value.fetchall.return_value = [
        ("600000", "BK01", "银行"),
        ("600001", "BK02", "地产"),
    ]
    members = [
        {"code": "600000", "change_percent": 2.0, "amount": 100.0},
        {"code": "600001", "change_percent": -1.0, "amount": 300.0},
    ]
    out = _compute_sector_contrib(db, members)
    assert out["available"] is True
    disc = out.get("disclaimer") or ""
    assert "成交额" in disc or "近似" in disc
    assert len(out["items"]) >= 1
    # 成交额更大的地产应排在更前（按 |approx_contribution|）
    top = out["items"][0]
    assert top["board_code"] in ("BK01", "BK02")


def _fake_bars(n: int = 80) -> List[Dict[str, Any]]:
    bars = []
    px = 4000.0
    for i in range(n):
        d = f"2026-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}"
        o = px
        c = px + (1 if i % 3 else -1)
        bars.append(
            {
                "date": d,
                "open": o,
                "high": max(o, c) + 5,
                "low": min(o, c) - 5,
                "close": c,
                "volume": 1e6 + i,
                "amount": 1e9,
            }
        )
        px = c
    return bars


@patch("backend_core.analysis.index_analysis_bundle._load_constituent_quotes")
@patch("backend_core.analysis.index_analysis_bundle.load_index_bars_with_realtime")
@patch("backend_core.analysis.index_analysis_bundle.resolve_index_identity")
@patch("backend_core.analysis.index_analysis_bundle.fetch_index_realtime_quote")
def test_build_bundle_empty_constituents(
    mock_quote, mock_ident, mock_bars, mock_cons
):
    mock_ident.return_value = {
        "ok": True,
        "code": "000001",
        "ts_code": "000001.SH",
        "name": "上证指数",
    }
    mock_bars.return_value = (_fake_bars(100), None, "2026-10-15")
    mock_quote.return_value = {
        "current_price": 3700.0,
        "change": -10.0,
        "change_percent": -0.27,
    }
    mock_cons.return_value = ([], "暂无成分数据（index_board_constituents 无该指数）")

    db = MagicMock()
    # pattern/levels engines need real math — may still run; if too heavy, patch PA helpers
    with patch(
        "backend_core.analysis.index_analysis_bundle._compute_levels_from_bars",
        return_value={"ok": True, "data": {"nearest_support": 1}, "payload": {"ok": True, "data": {}}},
    ), patch(
        "backend_core.analysis.index_analysis_bundle._compute_pattern_from_bars",
        return_value={"ok": True, "items": [], "tactical": {}, "payload": {"items": [], "tactical": {}}},
    ), patch(
        "backend_core.analysis.index_analysis_bundle._compute_swing_from_bars",
        return_value={"ok": True, "data": {"market_structure": {"trend": "range"}}, "payload": {}},
    ), patch(
        "backend_core.analysis.index_analysis_bundle._compute_gann_from_bars",
        return_value={"ok": True, "data": {"gann_trend": {"ok": True, "verdict": {}}}, "payload": {}},
    ):
        result = build_index_analysis_bundle(db, code="000001")

    assert result["success"] is True
    data = result["data"]
    assert data["index"]["code"] == "000001"
    assert data["index"]["ts_code"] == "000001.SH"
    assert data["breadth"]["available"] is False
    assert "暂无成分" in (data["breadth"].get("reason") or "")
    assert data["market_view"]["entry"] is None
    assert data["market_view"]["action"] is None


@patch("backend_core.analysis.index_analysis_bundle._compute_sector_contrib")
@patch("backend_core.analysis.index_analysis_bundle._load_constituent_quotes")
@patch("backend_core.analysis.index_analysis_bundle.load_index_bars_with_realtime")
@patch("backend_core.analysis.index_analysis_bundle.resolve_index_identity")
@patch("backend_core.analysis.index_analysis_bundle.fetch_index_realtime_quote")
def test_build_bundle_with_constituents_000300(
    mock_quote, mock_ident, mock_bars, mock_cons, mock_sector
):
    mock_ident.return_value = {
        "ok": True,
        "code": "000300",
        "ts_code": "000300.SH",
        "name": "沪深300",
    }
    mock_bars.return_value = (_fake_bars(100), None, "2026-10-15")
    mock_quote.return_value = {"current_price": 4100.0, "change_percent": 0.5}
    members = [
        {"code": "600519", "name": "茅台", "change_percent": 3.0, "amount": 5e9},
        {"code": "000001", "name": "平安银行", "change_percent": -1.0, "amount": 1e9},
    ]
    mock_cons.return_value = (members, None)
    mock_sector.return_value = {
        "available": True,
        "disclaimer": "非官方权重，按成分股成交额加权近似贡献，仅供参考。",
        "items": [{"board_code": "BK01", "board_name": "白酒", "approx_contribution": 0.1}],
    }

    db = MagicMock()
    with patch(
        "backend_core.analysis.index_analysis_bundle._compute_levels_from_bars",
        return_value={"ok": True, "data": {}, "payload": {"ok": True, "data": {}}},
    ), patch(
        "backend_core.analysis.index_analysis_bundle._compute_pattern_from_bars",
        return_value={"ok": True, "items": [], "tactical": {}, "payload": {}},
    ), patch(
        "backend_core.analysis.index_analysis_bundle._compute_swing_from_bars",
        return_value={"ok": True, "data": {"market_structure": {}}, "payload": {}},
    ), patch(
        "backend_core.analysis.index_analysis_bundle._compute_gann_from_bars",
        return_value={"ok": True, "data": {"gann_trend": {}}, "payload": {}},
    ):
        result = build_index_analysis_bundle(db, code="000300")

    assert result["success"] is True
    data = result["data"]
    assert data["breadth"]["available"] is True
    assert data["breadth"]["up_count"] == 1
    assert data["leaders"]["available"] is True
    assert data["sector_contrib"]["available"] is True
    # 身份：指数 000300，成分里可有股票 000001（平安）——二者并存不冲突
    assert data["index"]["code"] == "000300"
    assert data["leaders"]["losers"][0]["code"] == "000001"
