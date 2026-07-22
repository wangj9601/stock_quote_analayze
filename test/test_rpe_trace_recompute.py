# -*- coding: utf-8 -*-
"""RPE 强制重算相关单测（不依赖真实行情库）。"""

from backend_core.strategies.rpe.signal_storage import _panel_as_of


def test_panel_as_of_truncates_by_date():
    panel = {
        "000001": [
            {"date": "2024-01-01", "close": 1.0, "volume": 1},
            {"date": "2024-01-02", "close": 2.0, "volume": 1},
            {"date": "2024-01-03", "close": 3.0, "volume": 1},
        ],
        "000002": [
            {"date": "2024-01-02", "close": 9.0, "volume": 1},
            {"date": "2024-01-04", "close": 10.0, "volume": 1},
        ],
    }
    out = _panel_as_of(panel, "2024-01-02")
    assert list(out.keys()) == ["000001", "000002"]
    assert [b["date"] for b in out["000001"]] == ["2024-01-01", "2024-01-02"]
    assert [b["date"] for b in out["000002"]] == ["2024-01-02"]


def test_recompute_helpers_importable():
    from backend_core.strategies.rpe.signal_storage import (
        delete_traces_for_code_config,
        recompute_trace_for_stock,
    )

    assert callable(delete_traces_for_code_config)
    assert callable(recompute_trace_for_stock)


def test_recompute_doc_mentions_primary_board():
    from backend_core.strategies.rpe import signal_storage as ss

    assert "主板块" in (ss.recompute_trace_for_stock.__doc__ or "")
