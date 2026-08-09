# -*- coding: utf-8 -*-
"""双底股票池解析。"""

from unittest.mock import MagicMock

from backend_core.strategies.double_bottom.universe import (
    normalize_code_list,
    resolve_stock_pool,
)


def test_normalize_code_list():
    codes = normalize_code_list(["600519", "000001", "2"])
    assert set(codes) == {"600519", "000001", "000002"}
    assert len(codes) == 3


def test_resolve_stocks_mode():
    db = MagicMock()
    out = resolve_stock_pool(
        db,
        stock_pool_mode="stocks",
        stock_codes=["600519", "000001"],
    )
    assert out["mode"] == "stocks"
    assert set(out["codes"]) == {"000001", "600519"}
    assert out["scope_meta"]["stock_count"] == 2


def test_resolve_industry_union(monkeypatch):
    def fake_industry(db, raw):
        return (
            ["881101", "881102"],
            ["600000", "600001", "600002"],
            {
                "600000": [{"board_code": "881101", "board_name": "板A"}],
                "600001": [
                    {"board_code": "881101", "board_name": "板A"},
                    {"board_code": "881102", "board_name": "板B"},
                ],
                "600002": [{"board_code": "881102", "board_name": "板B"}],
            },
        )

    monkeypatch.setattr(
        "backend_core.strategies.double_bottom.universe.resolve_industry_pool",
        fake_industry,
    )
    out = resolve_stock_pool(
        MagicMock(),
        stock_pool_mode="industry_board",
        industry_board_codes=["881101", "881102"],
    )
    assert out["mode"] == "industry_board"
    assert len(out["codes"]) == 3
    assert out["boards_by_code"]["600001"][0]["board_name"] == "板A"
