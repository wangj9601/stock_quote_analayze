"""同花顺行业热力图：一票一格、面积回退、涨跌幅分档。"""

from backend_api.utils.market_heatmap import (
    build_market_heatmap,
    heat_color,
    tile_value,
)


def _member(code, board, name, circ, change, **extra):
    row = {
        "stock_code": code,
        "stock_name": extra.pop("stock_name", name),
        "board_code": board,
        "board_name": name,
        "change_percent": change,
        "circulating_market_value": circ,
        "total_market_value": extra.pop("total", None),
        "amount": extra.pop("amount", None),
        "current_price": extra.pop("price", 10),
    }
    row.update(extra)
    return row


def test_tile_value_falls_back_from_float_to_total_to_amount():
    assert tile_value(100, 50, 20) == 100
    assert tile_value(0, 50, 20) == 50
    assert tile_value(None, None, 20) == 20
    assert tile_value(None, 0, 0) is None
    assert tile_value("bad", None, None) is None


def test_heat_color_steps_red_up_green_down():
    assert heat_color(0) == "#2a3140"
    assert heat_color(0.004) == "#2a3140"
    assert heat_color(0.2) == "#5c2a32"
    assert heat_color(1) == "#8a2834"
    assert heat_color(2.9) == "#8a2834"
    assert heat_color(3) == "#b42330"
    assert heat_color(5) == "#d61f28"
    assert heat_color(7) == "#f0342c"
    assert heat_color(-0.2) == "#1a4a38"
    assert heat_color(-1) == "#0e6644"
    assert heat_color(-3) == "#0b8550"
    assert heat_color(-5) == "#0f9d5c"
    assert heat_color(-8) == "#14b86a"
    assert heat_color(None) == "#2a3140"


def test_stock_in_multiple_boards_goes_to_larger_circulating_sum():
    rows = [
        _member("600001", "881001", "半导体", 30, 1.2, stock_name="大票"),
        _member("600001", "881002", "银行", 30, 1.2, stock_name="大票"),
        _member("600002", "881002", "银行", 100, -2.0, stock_name="银行乙"),
        _member("600003", "881001", "半导体", 10, 4.0, stock_name="芯片"),
    ]
    payload = build_market_heatmap("2026-11-13", rows, {"881001": 3.5, "881002": -1.1})
    by_board = {item["board_code"]: item for item in payload["boards"]}
    semi_codes = [stock["code"] for stock in by_board["881001"]["stocks"]]
    bank_codes = [stock["code"] for stock in by_board["881002"]["stocks"]]
    assert semi_codes == ["600003"]
    assert bank_codes == ["600002", "600001"]
    assert payload["stock_count"] == 3
    assert by_board["881002"]["change_percent"] == -1.1
    assert by_board["881001"]["change_percent"] == 3.5


def test_concept_keeps_a_stock_in_every_concept():
    rows = [
        _member("600001", "885001", "人工智能", 30, 1.2, stock_name="大票"),
        _member("600001", "885002", "机器人", 80, 1.2, stock_name="大票"),
    ]
    payload = build_market_heatmap(
        "2026-11-13", rows, {"885001": 2.0}, board_kind="concept"
    )
    by_board = {item["board_code"]: item for item in payload["boards"]}
    assert [stock["code"] for stock in by_board["885001"]["stocks"]] == ["600001"]
    assert [stock["code"] for stock in by_board["885002"]["stocks"]] == ["600001"]
    assert payload["stock_count"] == 2
    assert payload["unique_stock_count"] == 1
    assert payload["board_kind"] == "concept"


def test_tie_on_circulating_sum_picks_smaller_board_code():
    rows = [
        _member("1", "881010", "乙", 20, 0.5),
        _member("000001", "881002", "甲", 20, 0.5),
    ]
    payload = build_market_heatmap("2026-11-13", rows, {})
    assert payload["stock_count"] == 1
    assert payload["boards"][0]["board_code"] == "881002"
    assert payload["boards"][0]["stocks"][0]["code"] == "000001"


def test_area_uses_total_then_amount_when_float_missing():
    rows = [
        _member("600010", "881003", "医药", None, 1.5, total=80, amount=10, stock_name="总市值票"),
        _member("600011", "881003", "医药", None, -6.0, total=None, amount=15, stock_name="成交额票"),
        _member("600012", "881003", "医药", None, 2.0, total=None, amount=None, stock_name="无面积"),
    ]
    payload = build_market_heatmap("2026-11-13", rows, {})
    stocks = payload["boards"][0]["stocks"]
    assert [item["code"] for item in stocks] == ["600010", "600011"]
    assert stocks[0]["value"] == 80
    assert stocks[1]["value"] == 15
    assert stocks[1]["color"] == heat_color(-6)


def test_duplicate_membership_does_not_double_count():
    row = _member("600020", "881008", "通信", 40, 0.8, stock_name="重复")
    payload = build_market_heatmap("2026-11-13", [row, dict(row)], {})
    assert payload["stock_count"] == 1
    assert len(payload["boards"][0]["stocks"]) == 1


def test_empty_snapshot():
    payload = build_market_heatmap(None, [], {})
    assert payload["trade_date"] is None
    assert payload["boards"] == []
    assert payload["stock_count"] == 0
    assert payload["board_code_source"] == "tonghuashun"
