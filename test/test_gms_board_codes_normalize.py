"""GMS 行业/概念板块多选代码解析。"""

from backend_api.stock.stock_screening_routes import _normalize_gms_board_codes


def test_normalize_gms_board_codes_empty():
    assert _normalize_gms_board_codes(None) == []
    assert _normalize_gms_board_codes([]) == []


def test_normalize_gms_board_codes_dedupe_and_split():
    assert _normalize_gms_board_codes(["IT服务", "半导体"]) == ["IT服务", "半导体"]
    assert _normalize_gms_board_codes(["IT服务,半导体", "IT服务"]) == ["IT服务", "半导体"]
    assert _normalize_gms_board_codes(["bk0428"], upper=True) == ["BK0428"]
