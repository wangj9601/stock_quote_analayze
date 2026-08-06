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
    SetBoardFrontendVisibleBody,
    EXPORT_ALL_COLUMNS,
    BOARD_LIST_SORT_FIELDS,
    _clear_all_concept_boards,
    _clear_all_industry_boards,
    _assert_board_name_source_unique,
    _assert_concept_board_name_unique,
    _board_list_order_clause,
    _export_all_board_src_sql,
    _format_export_board_code_source,
    _generate_next_concept_board_code,
    _industry_board_src_sql,
    _industry_board_list_src_sql,
    _board_list_filtered_cte,
    _board_list_src_sql,
    _delete_industry_realtime_quotes,
    _resolve_delete_board_code,
    _normalize_board_code,
    _normalize_stock_code,
    _read_board_trade_observe_flag,
    _sync_concept_board_basic_from_import,
    _sync_industry_board_basic_from_import,
    _upsert_board_basic,
    _resolve_stock_lookup_codes,
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
        assert _resolve_delete_board_code("industry", "881001") == "881001"
        assert _resolve_delete_board_code("concept", "BK0428") == "BK0428"
        assert _resolve_delete_board_code("concept", "881001") == "881001"
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

    def test_industry_board_list_src_sql_uses_not_exists(self):
        sql = _industry_board_list_src_sql(_tables("industry"))
        assert "NOT EXISTS" in sql
        assert "NOT IN" not in sql.upper()

    def test_board_list_filtered_cte_structure(self):
        src = _board_list_src_sql("industry", _tables("industry"))
        cte = _board_list_filtered_cte(src, "")
        assert "WITH src AS" in cte
        assert "filtered AS" in cte
        assert "GROUP BY board_code" in cte

    def test_board_list_filtered_cte_accepts_source_filter(self):
        src = _board_list_src_sql("concept", _tables("concept"))
        flt = (
            "AND COALESCE(NULLIF(TRIM(src.board_code_source), ''), :legacy_source)"
            " = :board_code_source"
        )
        cte = _board_list_filtered_cte(src, flt)
        assert "board_code_source" in cte
        assert ":board_code_source" in cte

    def test_board_list_order_clause_defaults_and_source_priority(self):
        assert "create_date" in BOARD_LIST_SORT_FIELDS
        assert "board_code_source" in BOARD_LIST_SORT_FIELDS
        default = _board_list_order_clause()
        assert "create_date DESC NULLS LAST" in default
        assert "board_code ASC" in default

        src_asc = _board_list_order_clause("board_code_source", "asc", alias="page")
        assert "tonghuashun" in src_asc
        assert "page.board_code_source" in src_asc
        assert "ASC" in src_asc

        src_desc = _board_list_order_clause("board_code_source", "desc")
        assert "DESC" in src_desc

        by_name = _board_list_order_clause("board_name", "asc")
        assert "board_name ASC" in by_name

        # 非法字段回退 create_date
        fallback = _board_list_order_clause("unknown_field", "asc")
        assert "create_date ASC" in fallback

    def test_board_list_src_sql_concept_basic_only(self):
        sql = _board_list_src_sql("concept", _tables("concept"))
        assert "concept_board_basic_info" in sql
        assert "UNION" not in sql.upper()

    def test_save_board_body_validation(self):
        body = SaveBoardInfoBody(board_type="concept", board_code="BK0428", board_name="电力")
        assert body.board_code == "BK0428"
        body = SaveBoardInfoBody(
            board_type="industry",
            board_name="电力",
        )
        assert body.board_code is None
        # 概念板新增可传自定义数字编码
        custom = SaveBoardInfoBody(
            board_type="concept",
            board_code="900001",
            board_name="自定义概念",
            board_code_source="manual",
        )
        assert custom.board_code == "900001"
        assert custom.board_code_source == "manual"
        src_body = SaveBoardInfoBody(
            board_type="industry",
            board_code="BK0428",
            board_name="电力",
            board_code_source="tonghuashun",
        )
        assert src_body.board_code_source == "tonghuashun"
        try:
            SaveBoardInfoBody(
                board_type="concept",
                board_code="BK0428",
                board_code_source="invalid_source",
            )
            assert False, "无效来源应失败"
        except ValueError:
            pass

    def test_export_all_includes_board_code_source(self):
        assert "board_code_source" in EXPORT_ALL_COLUMNS
        assert EXPORT_ALL_COLUMNS.index("board_code_source") == 2
        ind_sql = _export_all_board_src_sql("industry", _tables("industry"))
        con_sql = _export_all_board_src_sql("concept", _tables("concept"))
        assert "board_code_source" in ind_sql
        assert "board_code_source" in con_sql
        assert "industry_board_basic_info" in ind_sql
        assert "concept_board_basic_info" in con_sql
        # 与列表「代码来源」一致：导出中文标签
        assert _format_export_board_code_source("eastmoney") == "东方财富"
        assert _format_export_board_code_source("manual") == "手动维护"
        assert _format_export_board_code_source(None) == "东方财富"
        assert _format_export_board_code_source("tonghuashun") == "同花顺"
    def test_save_board_body_rename_keeps_codes(self):
        body = SaveBoardInfoBody(
            board_type="concept",
            board_code="BK0500",
            board_name="电力",
            original_board_code="BK0428",
        )
        assert body.board_code == "BK0500"
        assert body.original_board_code == "BK0428"
        industry = SaveBoardInfoBody(
            board_type="industry",
            board_code="BK1028",
            board_name="半导体",
            original_board_code="医疗服务",
        )
        assert industry.board_code == "BK1028"
        assert industry.original_board_code == "医疗服务"

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

    def test_set_board_frontend_visible_body_validation(self):
        body = SetBoardFrontendVisibleBody(
            board_type="concept",
            board_code="BK0428",
            frontend_visible_flag=False,
        )
        assert body.frontend_visible_flag is False

    def test_upsert_board_basic_preserves_flag_when_not_provided(self):
        executed: list[dict] = []

        class _R:
            def __init__(self, row=None, scalar_val=None):
                self._row = row
                self._scalar = scalar_val

            def fetchone(self):
                return self._row

            def scalar(self):
                return self._scalar

        class _DB:
            def execute(self, sql, params=None):
                executed.append({"sql": str(sql), "params": params or {}})
                sql_s = str(sql)
                if "SELECT trade_observe_flag" in sql_s:
                    return _R(row=None)
                if "SELECT 1 FROM" in sql_s:
                    return _R(scalar_val=None)
                if "SELECT board_code_source" in sql_s:
                    return _R(row=None)
                return _R()

        now = __import__("datetime").datetime(2026, 6, 6, 12, 0, 0)
        _upsert_board_basic(_DB(), "concept", "BK0428", "电力", now)
        assert "trade_observe_flag" in executed[-1]["sql"]
        assert "frontend_visible_flag" in executed[-1]["sql"]
        assert "board_code_source" in executed[-1]["sql"]
        assert executed[-1]["params"]["board_code"] == "BK0428"
        assert executed[-1]["params"]["frontend_visible_flag"] is True
        assert executed[-1]["params"]["board_code_source"] == "tonghuashun"

        executed.clear()
        _upsert_board_basic(_DB(), "concept", "BK0428", "电力", now, trade_observe_flag=True)
        assert executed[-1]["params"]["trade_observe_flag"] is True

        executed.clear()
        _upsert_board_basic(
            _DB(), "concept", "BK0428", "电力", now, board_code_source="manual"
        )
        assert executed[-1]["params"]["board_code_source"] == "manual"

    def test_read_board_trade_observe_flag(self):
        class _DB:
            def execute(self, sql, params=None):
                return type("R", (), {"fetchone": lambda self: (True, False)})()

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
        assert _format_bk_board_code(428) == "0428"
        assert _format_bk_board_code(1253) == "1253"
        assert _format_bk_board_code(10000) == "10000"

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
        assert _generate_next_concept_board_code(db) == "1254"
        assert _generate_next_concept_board_code(db, after_code="BK1254") == "1255"
        assert _generate_next_concept_board_code(db, after_code="BK1253") == "1254"

    def test_board_name_source_unique_allows_same_name_diff_source(self):
        """同名不同代码来源应放行；同名同来源才拒绝。"""

        class _DB:
            def __init__(self, row):
                self._row = row
                self.last_params = None

            def execute(self, *args, **kwargs):
                self.last_params = kwargs.get("params") or (args[1] if len(args) > 1 else None)
                outer = self

                class _R:
                    def fetchone(inner):
                        return outer._row

                return _R()

        # 同名 + 同来源 → 拒绝
        try:
            _assert_board_name_source_unique(
                _DB(("BK1638",)),
                "concept",
                "华为海思概念",
                "manual",
            )
            assert False, "同名同来源应拒绝"
        except HTTPException as e:
            assert e.status_code == 400
            assert "已存在" in str(e.detail)
            assert "手动维护" in str(e.detail)

        # 排除自身代码 → 放行
        _assert_board_name_source_unique(
            _DB(("BK1638",)),
            "concept",
            "华为海思概念",
            "manual",
            exclude_codes=["BK1638"],
        )
        # 库中无冲突 → 放行（同名不同来源由查询条件保证）
        _assert_board_name_source_unique(_DB(None), "industry", "电力", "tonghuashun")
        _assert_board_name_source_unique(_DB(("BK1638",)), "concept", "  ", "manual")

        # 兼容旧函数：默认按 manual 维度校验
        try:
            _assert_concept_board_name_unique(_DB(("BK1638",)), "华为海思概念")
            assert False, "应拒绝"
        except HTTPException as e:
            assert e.status_code == 400

    def _make_import_sync_db(self, executed, *, dup_code=None, existing_source=None):
        """构造导入 sync 用的假 DB：可模拟同名同来源冲突与已有来源。"""

        class _R:
            def __init__(self, row=None, scalar_val=None):
                self._row = row
                self._scalar = scalar_val

            def fetchone(self):
                return self._row

            def scalar(self):
                return self._scalar

        class _DB:
            def execute(self, sql, params=None):
                sql_s = str(sql)
                if "INSERT INTO" in sql_s:
                    executed.append(params)
                    return _R()
                if "board_code <> :code" in sql_s:
                    return _R(row=(dup_code,) if dup_code else None)
                if "SELECT board_code_source" in sql_s:
                    if existing_source is None:
                        return _R(row=None)
                    return _R(row=(existing_source,))
                if "SELECT 1 FROM" in sql_s:
                    return _R(scalar_val=1 if existing_source is not None else None)
                if "SELECT trade_observe_flag" in sql_s:
                    return _R(row=None)
                if "ADD COLUMN" in sql_s or "information_schema" in sql_s:
                    return _R()
                return _R(row=None)

        return _DB()

    def test_sync_concept_board_basic_from_import(self):
        from datetime import datetime

        executed: list[dict] = []
        issues: list = []
        now = datetime(2026, 6, 6, 12, 0, 0)
        count = _sync_concept_board_basic_from_import(
            self._make_import_sync_db(executed),
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
        assert executed[0]["board_code_source"] == "tonghuashun"
        assert executed[1]["board_code"] == "BK1642"
        assert executed[1]["board_name"] is None

    def test_sync_concept_import_respects_file_board_code_source(self):
        """全量导入应保留文件中的东财/同花顺来源，不能全部落成默认同花顺。"""
        from datetime import datetime

        executed: list[dict] = []
        issues: list = []
        now = datetime(2026, 6, 6, 12, 0, 0)
        count = _sync_concept_board_basic_from_import(
            self._make_import_sync_db(executed),
            [
                {
                    "board_code": "BK1641",
                    "board_name": "苹果概念",
                    "board_code_source": "东方财富",
                    "stock_code": "000001",
                    "stock_name": "平安银行",
                },
                {
                    "board_code": "1680",
                    "board_name": "储能",
                    "board_code_source": "同花顺",
                    "stock_code": "000002",
                    "stock_name": "万科A",
                },
            ],
            now,
            issues,
        )
        assert count == 2
        assert len(issues) == 0
        by_code = {e["board_code"]: e for e in executed}
        assert by_code["BK1641"]["board_code_source"] == "eastmoney"
        assert by_code["1680"]["board_code_source"] == "tonghuashun"

    def test_sync_concept_keeps_name_on_duplicate(self):
        """同名不再清空 board_name；同名同来源仅告警。"""
        from datetime import datetime

        executed: list[dict] = []
        issues: list = []
        now = datetime(2026, 6, 6, 12, 0, 0)
        count = _sync_concept_board_basic_from_import(
            self._make_import_sync_db(executed, dup_code="BK1000"),
            [
                {"board_code": "BK1641", "board_name": "苹果概念", "stock_code": "000001", "stock_name": "平安银行"},
            ],
            now,
            issues,
        )
        assert count == 1
        assert executed[0]["board_name"] == "苹果概念"
        assert executed[0]["board_code_source"] == "tonghuashun"
        assert len(issues) == 1
        assert "同名且同代码来源" in issues[0]["message"]
        assert "仅写入板块代码" not in issues[0]["message"]

    def test_sync_industry_import_defaults_tonghuashun_source(self):
        from datetime import datetime

        executed: list[dict] = []
        issues: list = []
        now = datetime(2026, 6, 6, 12, 0, 0)
        count = _sync_industry_board_basic_from_import(
            self._make_import_sync_db(executed),
            [
                {"board_code": "881001", "board_name": "银行", "stock_code": "000001", "stock_name": "平安银行"},
                {"board_code": "881002", "board_name": "银行", "stock_code": "600036", "stock_name": "招商银行"},
            ],
            now,
            issues,
        )
        assert count == 2
        assert all(e["board_name"] == "银行" for e in executed)
        assert all(e["board_code_source"] == "tonghuashun" for e in executed)

    def test_sync_industry_preserves_existing_source(self):
        from datetime import datetime

        executed: list[dict] = []
        issues: list = []
        now = datetime(2026, 6, 6, 12, 0, 0)
        count = _sync_industry_board_basic_from_import(
            self._make_import_sync_db(executed, existing_source="eastmoney"),
            [
                {"board_code": "BK0420", "board_name": "医疗服务", "stock_code": "000001", "stock_name": "平安银行"},
            ],
            now,
            issues,
        )
        assert count == 1
        assert executed[0]["board_code_source"] == "eastmoney"
        assert executed[0]["board_name"] == "医疗服务"

    def test_sync_industry_board_basic_keeps_name_on_duplicate(self):
        """同名冲突时仍写入名称；跳过「名称当代码」的别名行。"""
        from datetime import datetime

        executed: list[dict] = []
        existing_names = {"种植业与林业": "旧板块"}

        class _DBWrap:
            def execute(self, sql, params=None):
                sql_s = str(sql)
                params = params or {}
                if "INSERT INTO industry_board_basic_info" in sql_s:
                    executed.append(dict(params))
                    return type("R", (), {"fetchone": lambda self: None})()
                if "board_code <> :code" in sql_s:
                    name = params.get("name")
                    code = params.get("code")
                    owner = existing_names.get(name)
                    if owner and owner != code:
                        return type("R", (), {"fetchone": lambda self: (owner,)})()
                    return type("R", (), {"fetchone": lambda self: None})()
                return type("R", (), {"fetchone": lambda self: None})()

        issues: list = []
        now = datetime(2026, 6, 6, 12, 0, 0)
        count = _sync_industry_board_basic_from_import(
            _DBWrap(),
            [
                {"board_code": "881101", "board_name": "种植业与林业", "stock_code": "", "stock_name": ""},
                {"board_code": "种植业与林业", "board_name": "种植业与林业", "stock_code": "", "stock_name": ""},
                {"board_code": "81180", "board_name": "石油加工贸易", "stock_code": "", "stock_name": ""},
            ],
            now,
            issues,
        )
        codes = {e["board_code"] for e in executed}
        assert "881101" in codes
        assert "81180" in codes
        assert "种植业与林业" not in codes  # 别名行跳过
        row_881101 = next(e for e in executed if e["board_code"] == "881101")
        assert row_881101["board_name"] == "种植业与林业"  # 同名冲突仍保留名称
        assert row_881101["board_code_source"] == "tonghuashun"
        assert count == 2
        assert any("仍写入名称" in (i.get("message") or "") for i in issues)
        assert any("跳过别名板块" in (i.get("message") or "") for i in issues)

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

    def test_clear_all_industry_boards(self):
        deleted: dict[str, int] = {"cons": 0, "basic": 0, "realtime": 0}

        class _Q:
            def delete(self, synchronize_session=False):
                deleted["cons"] = 12
                return 12

        class _DB:
            def query(self, model):
                return _Q()

            def execute(self, sql, params=None):
                sql_text = str(sql)
                if "industry_board_basic_info" in sql_text:
                    deleted["basic"] = 6
                    return type("R", (), {"rowcount": 6})()
                if "industry_board_realtime_quotes" in sql_text:
                    deleted["realtime"] = 3
                    return type("R", (), {"rowcount": 3})()
                return type("R", (), {"rowcount": 0})()

        cons, basic, realtime = _clear_all_industry_boards(_DB())
        assert cons == 12
        assert basic == 6
        assert realtime == 3

    def test_resolve_stock_lookup_codes_by_code(self):
        class _DB:
            def execute(self, sql, params=None):
                if "stock_basic_info" in str(sql):
                    return type("R", (), {"fetchone": lambda self: ("深圳机场",)})()
                return type("R", (), {"fetchall": lambda self: []})()

        codes, names, err = _resolve_stock_lookup_codes(_DB(), "000089")
        assert err is None
        assert codes == ["000089"]
        assert names == ["深圳机场"]

    def test_resolve_stock_lookup_codes_empty(self):
        codes, names, err = _resolve_stock_lookup_codes(object(), "   ")
        assert codes == []
        assert err == "请输入股票代码或名称"

    def test_resolve_stock_lookup_codes_by_name(self):
        class _DB:
            def execute(self, sql, params=None):
                if "stock_basic_info" in str(sql):
                    return type("R", (), {
                        "fetchall": lambda self: [("000089", "深圳机场")],
                    })()
                return type("R", (), {"fetchall": lambda self: []})()

        codes, names, err = _resolve_stock_lookup_codes(_DB(), "深圳机场")
        assert err is None
        assert codes == ["000089"]
        assert "深圳机场" in names
