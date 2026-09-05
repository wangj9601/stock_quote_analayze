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


def test_attach_extra_window_slope_fields():
    from backend_api.utils import industry_board_query as q

    item: dict = {}
    q._attach_extra_window_slope_fields(
        item,
        {
            120: {
                "BK1": {
                    "sector_slope": 0.0009,
                    "sector_slope_window": 120,
                    "slope_asof_date": "2026-09-02",
                }
            },
            20: {
                "BK1": {
                    "sector_slope": 0.0015,
                    "sector_slope_window": 20,
                    "slope_asof_date": "2026-09-02",
                }
            },
            5: {
                "BK1": {
                    "sector_slope": -0.01,
                    "sector_slope_window": 5,
                    "slope_asof_date": "2026-09-02",
                }
            },
        },
        board_code="BK1",
    )
    assert item["sector_slope_120"] == 0.0009
    assert item["board_env_120"] == "strong"
    assert item["sector_slope_20"] == 0.0015
    assert item["board_env_20"] == "strong"
    assert item["sector_slope_5"] == -0.01
    assert item["board_env_5"] == "weak"


def test_default_short_window_constant():
    from backend_core.board_metrics.sector_slope_store import (
        DEFAULT_SECTOR_SLOPE_SHORT_WINDOW,
        DEFAULT_SECTOR_SLOPE_WINDOW,
        DEFAULT_SLOPE_WINDOWS,
        resolve_slope_lookback,
        slope_strong_threshold_for_window,
    )

    assert DEFAULT_SECTOR_SLOPE_SHORT_WINDOW == 10
    assert DEFAULT_SECTOR_SLOPE_WINDOW == 60
    assert DEFAULT_SLOPE_WINDOWS == (120, 60, 20, 10, 5)
    assert resolve_slope_lookback(120, DEFAULT_SLOPE_WINDOWS) >= 140
    assert slope_strong_threshold_for_window(120) == 0.0008
    assert slope_strong_threshold_for_window(5) == 0.002
