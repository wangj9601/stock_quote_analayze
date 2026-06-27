"""板块成分股管理单元测试"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import HTTPException

from backend_api.utils.bk_board_code import format_bk_board_code as _format_bk_board_code
from backend_api.admin.board_constituents import (
    DeleteBoardsBatchBody,
    SaveBoardInfoBody,
    SetBoardTradeObserveBody,
    _clear_all_concept_boards,
    _assert_concept_board_name_unique,
    _generate_next_concept_board_code,
    _industry_board_src_sql,
    _delete_industry_realtime_quotes,
    _resolve_delete_board_code,
    _normalize_board_code,
    _normalize_stock_code,
    _read_board_trade_observe_flag,
    _sync_concept_board_basic_from_import,
    _upsert_board_basic,
    _tables,
)


class TestBoardConstituentsHelpers:
    def test_normalize_board_code(self):
        assert _normalize_board_code(" bk0479 ") == "BK0479"
        assert _normalize_board_code("玻璃玻纤") == ""
        assert _normalize_board_code("IT服务") == ""
        assert _normalize_board_code("bk0428") == "BK0428"

    def test_delete_industry_realtime_quotes(self):
        deleted: list[str] = []

        class _DB:
            def execute(self, sql, params=None):
                if "industry_board_realtime_quotes" in str(sql):
                    deleted.append(params["code"])
                    return type("R", (), {"rowcount": 2})()
                return type("R", (), {"rowcount": 0})()

        n = _delete_industry_realtime_quotes(_DB(), ["医疗服务", "BK0420", ""])
        assert n == 4
        assert deleted == ["医疗服务", "BK0420"]

    def test_resolve_delete_board_code(self):
        assert _resolve_delete_board_code("industry", "BK0420") == "BK0420"
        assert _resolve_delete_board_code("industry", "医疗服务") == "医疗服务"
        assert _resolve_delete_board_code("concept", "BK0428") == "BK0428"
        assert _resolve_delete_board_code("concept", "医疗服务") == ""

    def test_normalize_stock_code(self):
        assert _normalize_stock_code("sz000001") == "000001"
        assert _normalize_stock_code("300668") == "300668"

    def test_tables_mapping(self):
        ind = _tables("industry")
        assert ind["constituents"] == "industry_board_constituents"
        con = _tables("concept")
        assert con["constituents"] == "concept_board_constituents"

    def test_industry_board_src_sql_basic_only(self):
        sql = _industry_board_src_sql(_tables("industry"))
        assert "industry_board_basic_info" in sql
        assert "industry_board_realtime_quotes" not in sql
        assert "UNION" not in sql.upper()

    def test_save_board_body_validation(self):
        body = SaveBoardInfoBody(board_type="concept", board_code="BK0428", board_name="电力")
        assert body.board_code == "BK0428"
        body = SaveBoardInfoBody(
            board_type="industry",
            board_name="电力",
        )
        assert body.board_code is None

    def test_set_board_trade_observe_body_validation(self):
        body = SetBoardTradeObserveBody(
            board_type="concept",
            board_code="BK0428",
            trade_observe_flag=True,
        )
        assert body.trade_observe_flag is True
        try:
            SetBoardTradeObserveBody(board_type="concept", board_code=" ", trade_observe_flag=False)
            assert False, "空代码应失败"
        except ValueError:
            pass

    def test_upsert_board_basic_preserves_flag_when_not_provided(self):
        executed: list[dict] = []

        class _DB:
            def execute(self, sql, params=None):
                executed.append({"sql": str(sql), "params": params or {}})

        now = __import__("datetime").datetime(2026, 6, 6, 12, 0, 0)
        _upsert_board_basic(_DB(), "concept", "BK0428", "电力", now)
        assert "trade_observe_flag" in executed[0]["sql"]
        assert executed[0]["params"]["board_code"] == "BK0428"

        executed.clear()
        _upsert_board_basic(_DB(), "concept", "BK0428", "电力", now, trade_observe_flag=True)
        assert executed[0]["params"]["trade_observe_flag"] is True

    def test_read_board_trade_observe_flag(self):
        class _DB:
            def execute(self, sql, params=None):
                return type("R", (), {"fetchone": lambda self: (True,)})()

        assert _read_board_trade_observe_flag(_DB(), "industry", "IT服务") is True

        class _DBEmpty:
            def execute(self, sql, params=None):
                return type("R", (), {"fetchone": lambda self: None})()

        assert _read_board_trade_observe_flag(_DBEmpty(), "industry", "IT服务") is False

    def test_delete_boards_batch_body_validation(self):
        body = DeleteBoardsBatchBody(
            board_type="concept",
            board_codes=["BK0428", " bk0429 ", "BK0428"],
        )
        assert body.board_codes == ["BK0428", "BK0429"]
        industry_body = DeleteBoardsBatchBody(
            board_type="industry",
            board_codes=["BK0420", " bk0421 "],
        )
        assert industry_body.board_codes == ["BK0420", "BK0421"]
        legacy = DeleteBoardsBatchBody(
            board_type="industry",
            board_codes=["医疗服务", "BK0420"],
        )
        assert legacy.board_codes == ["医疗服务", "BK0420"]
        SaveBoardInfoBody(
            board_type="industry",
            board_code="医疗服务",
            board_name="医疗服务",
        )
        try:
            DeleteBoardsBatchBody(board_type="concept", board_codes=["  "])
            assert False, "空代码应失败"
        except ValueError:
            pass

    def test_format_bk_board_code(self):
        assert _format_bk_board_code(428) == "BK0428"
        assert _format_bk_board_code(1253) == "BK1253"
        assert _format_bk_board_code(10000) == "BK10000"

    def test_generate_next_concept_board_code(self):
        class _Q:
            def __init__(self, rows):
                self._rows = rows

            def fetchall(self):
                return self._rows

        class _DB:
            def execute(self, *args, **kwargs):
                return _Q([("BK0428",), ("BK1253",), ("BK0999",)])

        db = _DB()
        assert _generate_next_concept_board_code(db) == "BK1254"
        assert _generate_next_concept_board_code(db, after_code="BK1254") == "BK1255"
        assert _generate_next_concept_board_code(db, after_code="BK1253") == "BK1254"

    def test_concept_board_name_unique(self):
        class _DB:
            def __init__(self, row):
                self._row = row

            def execute(self, *args, **kwargs):
                outer = self

                class _R:
                    def fetchone(inner):
                        return outer._row

                return _R()

        try:
            _assert_concept_board_name_unique(
                _DB(("BK1638",)),
                "华为海思概念",
            )
            assert False, "应拒绝重复名称"
        except HTTPException as e:
            assert e.status_code == 400
            assert "已存在" in str(e.detail)

        _assert_concept_board_name_unique(
            _DB(("BK1638",)),
            "华为海思概念",
            exclude_codes=["BK1638"],
        )
        _assert_concept_board_name_unique(_DB(None), "新板块")
        _assert_concept_board_name_unique(_DB(("BK1638",)), "  ")

    def test_sync_concept_board_basic_from_import(self):
        from datetime import datetime

        executed: list[dict] = []

        class _DB:
            def execute(self, sql, params=None):
                sql_s = str(sql)
                if "board_code <> :code" in sql_s:
                    return type("R", (), {"fetchone": lambda self: None})()
                return type("R", (), {"fetchone": lambda self: None})()

            def _record(self, params):
                executed.append(params)

        class _DBWrap:
            def __init__(self):
                self.inner = _DB()

            def execute(self, sql, params=None):
                sql_s = str(sql)
                if "INSERT INTO concept_board_basic_info" in sql_s:
                    executed.append(params)
                return self.inner.execute(sql, params)

        issues: list = []
        now = datetime(2026, 6, 6, 12, 0, 0)
        count = _sync_concept_board_basic_from_import(
            _DBWrap(),
            [
                {"board_code": "BK1641", "board_name": "苹果概念", "stock_code": "000001", "stock_name": "平安银行"},
                {"board_code": "BK1641", "board_name": "苹果概念", "stock_code": "000002", "stock_name": "万科A"},
                {"board_code": "BK1642", "board_name": "", "stock_code": "600519", "stock_name": "贵州茅台"},
            ],
            now,
            issues,
        )
        assert count == 2
        assert len(issues) == 0
        assert len(executed) == 2
        assert executed[0]["board_code"] == "BK1641"
        assert executed[0]["board_name"] == "苹果概念"
        assert executed[1]["board_code"] == "BK1642"
        assert executed[1]["board_name"] is None

    def test_clear_all_concept_boards(self):
        deleted: dict[str, int] = {"cons": 0, "basic": 0}

        class _Model:
            pass

        class _Q:
            def delete(self, synchronize_session=False):
                deleted["cons"] = 10
                return 10

        class _DB:
            def query(self, model):
                return _Q()

            def execute(self, sql, params=None):
                deleted["basic"] = 5
                return type("R", (), {"rowcount": 5})()

        cons, basic = _clear_all_concept_boards(_DB())
        assert cons == 10
        assert basic == 5
