# -*- coding: utf-8 -*-
"""CSB 回测：A股板块多选归一与过滤。"""

import pytest

from backend_api.admin.csb_admin_routes import (
    BacktestCreateBody,
    _apply_cn_board_segments,
    _resolve_cn_board_segments,
)


def test_resolve_multi_segments_from_list():
    segs = _resolve_cn_board_segments(["MAIN", "CYB"], None)
    assert segs == ["MAIN", "CYB"]


def test_resolve_from_legacy_single_field():
    assert _resolve_cn_board_segments(None, "KCB") == ["KCB"]


def test_resolve_empty_means_all():
    assert _resolve_cn_board_segments([], None) == []
    assert _resolve_cn_board_segments(None, None) == []
    assert _resolve_cn_board_segments(["ALL"], None) == []


def test_resolve_invalid_raises():
    with pytest.raises(Exception) as ei:
        _resolve_cn_board_segments(["NOPE"], None)
    assert ei.value.status_code == 400


def test_apply_multi_union_filter():
    codes = ["600000", "300001", "688001", "000001", "830001"]
    out = _apply_cn_board_segments(codes, ["MAIN", "CYB"])
    assert "600000" in out
    assert "000001" in out
    assert "300001" in out
    assert "688001" not in out
    assert "830001" not in out


def test_body_accepts_cn_board_segments():
    body = BacktestCreateBody(
        start_date="2024-01-01",
        end_date="2024-06-01",
        cn_board_segments=["MAIN", "KCB"],
    )
    assert body.cn_board_segments == ["MAIN", "KCB"]
