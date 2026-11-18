# -*- coding: utf-8 -*-
"""概念指数分析：日 K 来源、身份隔离、广度、实时不改写 K。"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend_core.analysis.concept_index_analysis_bundle import (  # noqa: E402
    build_concept_index_analysis_bundle,
)
from backend_core.analysis.concept_index_bars import (  # noqa: E402
    load_concept_board_ohlc_asc,
)
from backend_core.analysis.index_analysis_bundle import (  # noqa: E402
    _compute_gann_from_bars,
)


def _bars(n: int = 40, close: float = 1600.0) -> List[Dict[str, Any]]:
    start = date(2025, 1, 2)
    out = []
    for i in range(n):
        c = close + i * 0.2
        out.append(
            {
                "date": (start + timedelta(days=i)).isoformat(),
                "open": c - 1,
                "high": c + 3,
                "low": c - 3,
                "close": c,
                "volume": 1000 + i,
                "amount": 5000 + i,
            }
        )
    return out


def test_load_ohlc_reads_concept_table_only():
    db = MagicMock()
    db.execute.return_value.fetchall.return_value = []
    load_concept_board_ohlc_asc(db, "885001", lookback=30)
    clause = db.execute.call_args[0][0]
    sql = str(clause)
    assert "concept_board_historical_quotes" in sql
    assert "industry_board_historical_quotes" not in sql
    assert "index_historical_quotes" not in sql
    assert "from historical_quotes" not in sql.lower()


def test_gann_short_bars_use_concept_label():
    out = _compute_gann_from_bars(
        [],
        code="885001",
        name="人工智能",
        asof=None,
        use_realtime=False,
        realtime_meta=None,
        asset_type="concept_index",
    )
    assert out["ok"] is False
    assert "概念指数" in (out.get("error") or "")


def test_no_daily_bars_fails():
    db = MagicMock()
    with patch(
        "backend_core.analysis.concept_index_analysis_bundle.resolve_concept_board_identity",
        return_value={"ok": True, "code": "885001", "name": "人工智能"},
    ), patch(
        "backend_core.analysis.concept_index_analysis_bundle.load_concept_board_ohlc_asc",
        return_value=[],
    ):
        result = build_concept_index_analysis_bundle(db, board_code="885001")
    assert result["success"] is False
    assert result["http_status"] == 404
    assert "concept_board_historical_quotes" in result["message"]


@patch("backend_core.analysis.concept_index_analysis_bundle._compute_gann_from_bars")
@patch("backend_core.analysis.concept_index_analysis_bundle._compute_swing_from_bars")
@patch("backend_core.analysis.concept_index_analysis_bundle._compute_pattern_from_bars")
@patch("backend_core.analysis.concept_index_analysis_bundle.load_concept_board_ohlc_asc")
@patch("backend_core.analysis.concept_index_analysis_bundle.resolve_concept_board_identity")
def test_bundle_breadth_identity_and_realtime_does_not_rewrite_bars(
    mock_ident, mock_bars, mock_pattern, mock_swing, mock_gann
):
    bars = _bars(40)
    snapshot = [(b["open"], b["high"], b["low"], b["close"]) for b in bars]
    mock_ident.return_value = {"ok": True, "code": "885001", "name": "人工智能"}
    mock_bars.return_value = bars
    mock_pattern.return_value = {"ok": True, "tactical": {"short_bias": "bullish"}, "payload": {}}
    mock_swing.return_value = {
        "ok": True,
        "data": {"market_structure": {"trend": "up"}},
        "payload": {},
    }
    mock_gann.return_value = {"ok": True, "data": {}, "payload": {}}

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
            captured["hist"] = kwargs.get("historical_data")
            captured["adjust"] = kwargs.get("price_adjust")
            return {
                "success": True,
                "data": {
                    "nearest_support": 1700.0,
                    "nearest_resistance": 1900.0,
                    "current_price": kwargs.get("anchor_price"),
                    "kde_ok": True,
                },
            }

    members = [
        ("600001", "甲", 10.0, 1.2, 100.0, "2026-11-16"),
        ("600002", "乙", 9.0, -0.5, 80.0, "2026-11-16"),
        ("600003", "丙", 8.0, 0.0, 50.0, "2026-11-16"),
        ("600004", "丁", 7.0, 3.0, 20.0, "2026-11-16"),
    ]

    def _execute(sql, params=None):
        text_sql = str(sql)
        result = MagicMock()
        if "concept_board_constituents" in text_sql:
            result.fetchall.return_value = [(m[0], m[1]) for m in members]
        elif "stock_realtime_quote" in text_sql:
            result.fetchall.return_value = members
        else:
            raise AssertionError(f"unexpected sql: {text_sql}")
        return result

    db = MagicMock()
    db.execute.side_effect = _execute

    with patch(
        "backend_api.stock.stock_analysis.StockAnalysisService",
        _Svc,
    ), patch(
        "backend_core.analysis.index_analysis_bundle.load_index_bars_with_realtime",
        side_effect=AssertionError("must not load index bars"),
    ), patch(
        "backend_core.analysis.index_bars.load_index_ohlc_asc",
        side_effect=AssertionError("must not load index ohlc"),
    ):
        result = build_concept_index_analysis_bundle(
            db, board_code="885001", use_realtime=True
        )

    assert result["success"] is True
    data = result["data"]
    last_close = bars[-1]["close"]
    prev_close = bars[-2]["close"]
    assert data["index"]["asset_type"] == "concept_index"
    assert data["index"]["current"] == pytest.approx(last_close)
    assert data["index"]["change_percent"] == pytest.approx(
        (last_close - prev_close) / prev_close * 100.0
    )
    assert data["sector_contrib"] is None
    assert data["realtime"]["merged"] is False
    assert "未改写当日K" in data["realtime"]["reason"]
    assert data["realtime"]["source"] == "concept_board_historical_quotes"
    assert [(b["open"], b["high"], b["low"], b["close"]) for b in bars] == snapshot
    assert captured["adjust"] == "none"
    assert captured["anchor"] == pytest.approx(last_close)
    assert captured["hist"]
    assert captured["code"] == "885001"
    breadth = data["breadth"]
    assert breadth["available"] is True
    assert breadth["up_count"] == 2
    assert breadth["down_count"] == 1
    assert breadth["flat_count"] == 1
    assert breadth["official_up_count"] is None
    assert breadth["official_down_count"] is None
    assert len(data["leaders"]["gainers"]) == 4
    mv = data["market_view"]
    assert mv["title"] == "概念环境研判"
    for key in ("entry", "stop", "target", "position", "action"):
        assert mv[key] is None
    mock_pattern.assert_called()
    assert mock_pattern.call_args.kwargs["asset_type"] == "concept_index"
    joined = " ".join(str(c[0][0]) for c in db.execute.call_args_list)
    assert "concept_board_constituents" in joined
    assert "stock_realtime_quote" in joined
    assert "industry_board_historical_quotes" not in joined
    assert "industry_board_realtime_quotes" not in joined
    assert "index_historical_quotes" not in joined
    assert "from historical_quotes" not in joined.lower()


def test_empty_constituents_breadth_unavailable():
    bars = _bars(25)
    db = MagicMock()
    empty = MagicMock()
    empty.fetchall.return_value = []
    db.execute.return_value = empty

    class _Svc:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get_key_levels_only(self, code, **kwargs):
            return {"success": True, "data": {"kde_ok": True, "nearest_support": 1}}

    with patch(
        "backend_core.analysis.concept_index_analysis_bundle.resolve_concept_board_identity",
        return_value={"ok": True, "code": "885000", "name": "空概念"},
    ), patch(
        "backend_core.analysis.concept_index_analysis_bundle.load_concept_board_ohlc_asc",
        return_value=bars,
    ), patch(
        "backend_core.analysis.concept_index_analysis_bundle._compute_pattern_from_bars",
        return_value={"ok": False, "error": "skip"},
    ), patch(
        "backend_core.analysis.concept_index_analysis_bundle._compute_swing_from_bars",
        return_value={"ok": False, "error": "skip"},
    ), patch(
        "backend_core.analysis.concept_index_analysis_bundle._compute_gann_from_bars",
        return_value={"ok": False, "error": "skip"},
    ), patch(
        "backend_api.stock.stock_analysis.StockAnalysisService",
        _Svc,
    ):
        result = build_concept_index_analysis_bundle(db, board_code="885000")

    assert result["success"] is True
    assert result["data"]["breadth"]["available"] is False
    assert "概念成分" in (result["data"]["breadth"].get("reason") or "")
    assert result["data"]["breadth"]["official_up_count"] is None
    assert result["data"]["sector_contrib"] is None
    assert result["data"]["index"]["asset_type"] == "concept_index"
