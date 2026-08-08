"""个股所属行业/概念板块：同花顺口径、分组与去重。"""

from __future__ import annotations

from unittest.mock import MagicMock

from backend_api.utils.industry_board_query import (
    _dedupe_membership_boards,
    get_boards_by_stock_code,
    get_stock_membership_boards,
)


def test_dedupe_membership_boards_by_code_and_name():
    rows = [
        {"board_type": "industry", "board_code": "881101", "board_name": "化学制药"},
        {"board_type": "industry", "board_code": "881101", "board_name": "化学制药"},
        {"board_type": "industry", "board_code": "881199", "board_name": "化学制药"},
        {"board_type": "concept", "board_code": "885001", "board_name": "CRO概念"},
        {"board_type": "concept", "board_code": "885002", "board_name": "CRO概念"},
        {"board_type": "concept", "board_code": "885003", "board_name": "PCB概念"},
    ]
    out = _dedupe_membership_boards(rows)
    assert [b["board_code"] for b in out] == ["881101", "885001", "885003"]


def test_get_boards_by_stock_code_filters_tonghuashun_and_dedupes():
    db = MagicMock()
    # (board_code, board_name, updated_at, board_type, board_code_source)
    db.execute.return_value.fetchall.return_value = [
        ("881101", "化学制药", None, "industry", "tonghuashun"),
        ("881101", "化学制药", None, "industry", "tonghuashun"),
        ("885001", "CRO概念", None, "concept", "tonghuashun"),
        ("885010", "PCB概念", None, "concept", "tonghuashun"),
    ]
    boards = get_boards_by_stock_code(db, "300759", board_code_source="tonghuashun")
    assert len(boards) == 3
    assert boards[0]["board_type"] == "industry"
    assert boards[0]["board_code_source"] == "tonghuashun"
    assert boards[0]["board_code_source_label"] == "同花顺"
    assert {b["board_name"] for b in boards if b["board_type"] == "concept"} == {
        "CRO概念",
        "PCB概念",
    }
    # 校验 SQL 使用了来源过滤参数
    args, kwargs = db.execute.call_args
    params = args[1] if len(args) > 1 else kwargs.get("parameters") or kwargs
    assert params["stock_code"] == "300759"
    assert params["source"] == "tonghuashun"


def test_get_stock_membership_boards_groups_industry_and_concept():
    db = MagicMock()
    db.execute.return_value.fetchall.return_value = [
        ("881101", "化学制药", None, "industry", "tonghuashun"),
        ("885001", "CRO概念", None, "concept", "tonghuashun"),
        ("885010", "PCB概念", None, "concept", "tonghuashun"),
    ]
    data = get_stock_membership_boards(db, "300759", board_code_source="tonghuashun")
    assert data["stock_code"] == "300759"
    assert data["board_code_source"] == "tonghuashun"
    assert data["board_code_source_label"] == "同花顺"
    assert len(data["industry_boards"]) == 1
    assert data["industry_boards"][0]["board_name"] == "化学制药"
    assert [b["board_name"] for b in data["concept_boards"]] == ["CRO概念", "PCB概念"]
    assert len(data["boards"]) == 3


def test_get_boards_by_stock_code_none_source_skips_filter():
    db = MagicMock()
    db.execute.return_value.fetchall.return_value = [
        ("BK0475", "化学制药", None, "industry", "eastmoney"),
    ]
    boards = get_boards_by_stock_code(db, "300759", board_code_source=None)
    assert len(boards) == 1
    assert boards[0]["board_code_source"] == "eastmoney"
    params = db.execute.call_args[0][1]
    assert "source" not in params
    assert params["stock_code"] == "300759"
