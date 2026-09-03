# -*- coding: utf-8 -*-
"""短线板块斜率字段单测。"""


def test_attach_short_slope_fields():
    from backend_api.utils import industry_board_query as q

    item: dict = {}
    q._attach_short_slope_fields(
        item,
        {
            "sector_slope": 0.002,
            "sector_slope_window": 10,
            "slope_asof_date": "2026-09-02",
        },
    )
    assert item["sector_slope_short"] == 0.002
    assert item["sector_slope_short_window"] == 10
    assert item["board_env_short"] == "strong"
    assert item["board_strong_short"] is True

    empty: dict = {}
    q._attach_short_slope_fields(empty, None)
    assert empty["sector_slope_short"] is None
    assert empty["board_env_short"] == "unknown"


def test_default_short_window_constant():
    from backend_core.board_metrics.sector_slope_store import (
        DEFAULT_SECTOR_SLOPE_SHORT_WINDOW,
        DEFAULT_SECTOR_SLOPE_WINDOW,
        DEFAULT_SLOPE_WINDOWS,
    )

    assert DEFAULT_SECTOR_SLOPE_SHORT_WINDOW == 10
    assert DEFAULT_SECTOR_SLOPE_WINDOW == 60
    assert DEFAULT_SLOPE_WINDOWS == (60, 10)
