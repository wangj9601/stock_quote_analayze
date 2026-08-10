"""RPE：同花顺行业板口径 + 证券简称补全。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend_core.strategies.rpe.data_loader import RPEDataLoader, _norm_code
from backend_core.strategies.rpe.strategy_engine import RPEStrategyEngine


def test_rpe_loader_default_board_code_source_is_tonghuashun():
    loader = RPEDataLoader(db_session=MagicMock())
    assert loader.board_code_source == "tonghuashun"


def test_pick_primary_board_sql_filters_tonghuashun():
    """主板块 SQL 必须带 board_code_source 过滤，避免落到东财成分。"""
    mock_db = MagicMock()
    mock_db.execute.return_value.fetchone.return_value = ("881101", "半导体", 12)
    loader = RPEDataLoader(db_session=mock_db, board_code_source="tonghuashun")
    out = loader._pick_primary_board_among("000001", "industry")
    assert out is not None
    assert out["board_code"] == "881101"
    assert out["board_name"] == "半导体"
    assert out.get("board_code_source") == "tonghuashun"
    assert mock_db.execute.called
    sql_text = str(mock_db.execute.call_args[0][0])
    assert "board_code_source" in sql_text
    params = mock_db.execute.call_args[0][1]
    assert params["source"] == "tonghuashun"
    assert params["legacy"] == "eastmoney"


def test_list_industry_boards_filters_source():
    mock_db = MagicMock()
    mock_db.execute.return_value.fetchall.return_value = [("881101", "半导体")]
    loader = RPEDataLoader(db_session=mock_db, board_code_source="tonghuashun")
    rows = loader.list_industry_boards()
    assert rows == [{"board_code": "881101", "board_name": "半导体"}]
    sql_text = str(mock_db.execute.call_args[0][0])
    assert "board_code_source" in sql_text
    assert mock_db.execute.call_args[0][1]["source"] == "tonghuashun"


def test_find_boards_for_code_filters_source():
    mock_db = MagicMock()
    mock_db.execute.return_value.fetchall.return_value = [("881101", "半导体")]
    loader = RPEDataLoader(db_session=mock_db, board_code_source="tonghuashun")
    rows = loader.find_boards_for_code("000001", board_kind="industry")
    assert rows[0]["board_code"] == "881101"
    sql_text = str(mock_db.execute.call_args[0][0])
    assert "INNER JOIN" in sql_text.upper() or "inner join" in sql_text
    assert "board_code_source" in sql_text
    assert mock_db.execute.call_args[0][1]["source"] == "tonghuashun"


def test_load_board_members_fills_names_from_stock_basic_info():
    mock_db = MagicMock()
    mock_db.execute.return_value.fetchall.return_value = [("000001", ""), ("000002", "已有名")]
    loader = RPEDataLoader(db_session=mock_db)

    with patch.object(loader, "load_stock_names", return_value={"000001": "平安银行"}) as mocked:
        members = loader.load_board_members("881101", board_kind="industry")

    assert members[0]["code"] == "000001"
    assert members[0]["name"] == "平安银行"
    assert members[1]["name"] == "已有名"
    mocked.assert_called_once()
    assert "000001" in mocked.call_args[0][0]


def test_enrich_rpe_sector_names_prefer_ths_then_basic():
    from backend_api.stock import stock_screening_routes as routes

    rows = [
        {"code": "000001", "sector_id": "BK9999", "sector_name": "BK9999"},
        {"code": "000002", "sector_id": "X", "sector_name": ""},
        {"code": "000003", "sector_id": "Y", "sector_name": ""},
    ]
    db = MagicMock()
    fake_row_2 = MagicMock(code="000002", industry="房地产")
    fake_row_3 = MagicMock(code="000003", industry=None)
    q = MagicMock()
    q.filter.return_value.all.return_value = [fake_row_2, fake_row_3]
    db.query.return_value = q

    with patch(
        "backend_api.utils.industry_board_query.batch_industry_board_names_by_stock_codes",
        return_value={"000001": "银行"},
    ), patch.object(routes, "StockBasicInfo", MagicMock(), create=True):
        # enrich 内部 from backend_api.models import StockBasicInfo
        with patch(
            "backend_api.models.StockBasicInfo",
            MagicMock(),
        ):
            routes._enrich_rpe_rows_with_sector_names(
                db, rows, board_code_source="tonghuashun", prefer_ths_industry=True
            )

    assert rows[0]["sector_name"] == "银行"
    assert rows[0]["sector_name_source"] == "tonghuashun"
    assert rows[1]["sector_name"] == "房地产（基础信息）"
    assert rows[2]["sector_name"] == "--"


def test_enrich_rpe_sector_names_keep_cluster_when_explicit_board_scope():
    from backend_api.stock import stock_screening_routes as routes

    rows = [
        {"code": "000001", "sector_id": "881101", "sector_name": "半导体"},
    ]
    db = MagicMock()
    with patch(
        "backend_api.utils.industry_board_query.batch_industry_board_names_by_stock_codes",
        return_value={"000001": "银行"},
    ):
        routes._enrich_rpe_rows_with_sector_names(
            db, rows, board_code_source="tonghuashun", prefer_ths_industry=False
        )
    # 显式选板：保留建簇名，不被同花顺其它行业名覆盖
    assert rows[0]["sector_name"] == "半导体"


def test_enrich_rpe_stock_names_from_fallback_and_basic():
    from backend_api.stock.stock_screening_routes import _enrich_rpe_rows_with_stock_names

    rows = [
        {"code": "000001", "name": ""},
        {"code": "000002", "name": ""},
        {"code": "000003", "name": "已有"},
    ]
    db = MagicMock()
    with patch(
        "backend_api.stock.stock_screening_routes._batch_resolve_gms_stock_names",
        return_value={"000002": "万科A"},
    ):
        _enrich_rpe_rows_with_stock_names(
            db, rows, fallback_name_map={"000001": "平安银行"}
        )
    assert rows[0]["name"] == "平安银行"
    assert rows[1]["name"] == "万科A"
    assert rows[2]["name"] == "已有"


def test_engine_passes_board_code_source_to_loader():
    eng = RPEStrategyEngine(db_session=MagicMock(), board_code_source="tonghuashun")
    assert eng.loader.board_code_source == "tonghuashun"


def test_screen_board_fills_missing_name_via_load_stock_names():
    """成分缺名 / 自选并入时，screen_board 用 load_stock_names 补全。"""
    eng = RPEStrategyEngine(db_session=MagicMock())
    filled = {}

    class _L:
        board_code_source = "tonghuashun"

        def load_board_members(self, board_code, board_kind="industry"):
            return [{"code": f"{i:06d}", "name": ""} for i in range(1, 8)]

        def load_stock_names(self, codes):
            for c in codes:
                filled[_norm_code(c)] = f"名{_norm_code(c)}"
            return dict(filled)

        def load_sector_panel(self, codes, **kwargs):
            return {}

        def resolve_trade_date(self):
            return "2024-01-01"

    eng.loader = _L()
    # panel 为空 → 早退；但应已调用 load_stock_names
    out = eng.screen_board("881101", "半导体", include_no_signal=True)
    assert out == []
    assert "000001" in filled
