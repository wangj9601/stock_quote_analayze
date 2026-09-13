# -*- coding: utf-8 -*-
"""板块斜率历史序列：load_board_sector_slope_series。"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from backend_core.board_metrics.sector_slope_store import load_board_sector_slope_series


def test_load_board_sector_slope_series_empty_code():
    db = MagicMock()
    out = load_board_sector_slope_series(db, "", board_kind="industry")
    assert out["board_code"] == ""
    assert out["series"]["60"] == []
    db.execute.assert_not_called()


def test_load_board_sector_slope_series_groups_and_trims():
    from unittest.mock import patch

    db = MagicMock()
    rows = []
    for i, d in enumerate(
        [
            date(2026, 8, 1),
            date(2026, 8, 2),
            date(2026, 8, 3),
            date(2026, 8, 4),
            date(2026, 8, 5),
            date(2026, 8, 6),
        ]
    ):
        rows.append((d, 60, 0.001 * (i + 1), 0.5, "ths_index", 60, 20))
        rows.append((d, 5, 0.002 * (i + 1), 0.6, "equal_weight_return", 5, 20))

    db.execute.return_value.fetchall.return_value = rows

    with patch(
        "backend_core.board_metrics.sector_slope_store.ensure_board_daily_metrics_table"
    ):
        out = load_board_sector_slope_series(
            db,
            "881121",
            board_kind="industry",
            windows=[5, 60],
            days=5,
        )

    assert out["board_code"] == "881121"
    assert out["windows"] == [5, 60]
    assert len(out["series"]["60"]) == 5
    assert out["series"]["60"][0]["date"] == "2026-08-02"
    assert out["series"]["60"][-1]["date"] == "2026-08-06"
    assert abs(out["series"]["60"][-1]["sector_slope"] - 0.006) < 1e-9
    assert len(out["series"]["5"]) == 5
    assert out["series"]["5"][-1]["slope_source"] == "equal_weight_return"


def test_parse_slope_windows_query():
    from backend_api.market_routes import _parse_slope_windows_query
    from backend_core.board_metrics.sector_slope_store import DEFAULT_SLOPE_WINDOWS

    assert _parse_slope_windows_query("5,10,20") == [5, 10, 20]
    assert _parse_slope_windows_query("5，60，60,abc") == [5, 60]
    assert _parse_slope_windows_query(None) == list(DEFAULT_SLOPE_WINDOWS)
