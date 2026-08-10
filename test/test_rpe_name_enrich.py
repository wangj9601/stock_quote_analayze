"""RPE 选股结果名称补全：引擎未带 name 时 API 仍从 basic_info / fallback 补全。"""

from __future__ import annotations

from unittest.mock import MagicMock

from backend_api.stock import stock_screening_routes as routes


def test_enrich_rpe_rows_fills_empty_name_from_basic_info():
    db = MagicMock()

    class _R:
        def __init__(self, code, name):
            self.code = code
            self.name = name

    def _query(*_entities):
        m = MagicMock()
        m.filter.return_value = [
            _R("688256", "寒武纪"),
            _R("600171", "上海贝岭"),
            _R("300058", "蓝色光标"),
        ]
        return m

    db.query.side_effect = _query
    rows = [
        {"code": "688256", "name": None, "z_score": 1.0},
        {"code": "600171", "name": "", "z_score": -1.2},
        {"code": "300058", "stock_name": "", "name": None},
        {"code": "002364", "name": "中恒电气"},  # 已有名称不覆盖
    ]
    routes._enrich_rpe_rows_with_stock_names(db, rows)
    assert rows[0]["name"] == "寒武纪"
    assert rows[0]["stock_name"] == "寒武纪"
    assert rows[1]["name"] == "上海贝岭"
    assert rows[2]["name"] == "蓝色光标"
    assert rows[2]["stock_name"] == "蓝色光标"
    assert rows[3]["name"] == "中恒电气"
    assert rows[3]["stock_name"] == "中恒电气"


def test_enrich_rpe_rows_prefers_watchlist_fallback_before_db():
    db = MagicMock()
    rows = [{"code": "600201", "name": None}]
    routes._enrich_rpe_rows_with_stock_names(
        db,
        rows,
        fallback_name_map={"600201": "生物股份"},
    )
    assert rows[0]["name"] == "生物股份"
    assert rows[0]["stock_name"] == "生物股份"
    db.query.assert_not_called()


def test_enrich_rpe_rows_accepts_stock_name_field():
    db = MagicMock()
    rows = [{"code": "003007", "stock_name": "真真科技"}]
    routes._enrich_rpe_rows_with_stock_names(db, rows)
    assert rows[0]["name"] == "真真科技"
    assert rows[0]["stock_name"] == "真真科技"
    db.query.assert_not_called()


def test_enrich_rpe_rows_when_engine_omits_name():
    """引擎未带 name 时 API 补全路径（对应选股列表空白名称）。"""
    db = MagicMock()

    class _R:
        def __init__(self, code, name):
            self.code = code
            self.name = name

    def _query(*_entities):
        m = MagicMock()
        m.filter.return_value = [_R("300139", "晓程科技")]
        return m

    db.query.side_effect = _query
    rows = [
        {"code": "300139", "name": None, "close": 10.0},
        {"code": "002364", "name": "中恒电气", "close": 11.0},
    ]
    routes._enrich_rpe_rows_with_stock_names(db, rows)
    assert rows[0]["name"] == "晓程科技"
    assert rows[0]["stock_name"] == "晓程科技"
    assert rows[1]["name"] == "中恒电气"
