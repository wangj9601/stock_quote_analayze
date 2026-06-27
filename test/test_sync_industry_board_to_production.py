"""行业板块生产迁移脚本单元测试"""

import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from migrations.sync_industry_board_to_production import (
    _mask_db_url,
    _parse_ts,
    _serialize_value,
    dump_to_file,
    load_from_file,
    upsert_basic_rows,
)


class _Conn:
    def __init__(self):
        self.sqls: list = []

    def execute(self, sql, params=None):
        self.sqls.append((str(sql), params or {}))


def test_mask_db_url():
    u = "postgresql+psycopg2://postgres:secret@localhost:5432/stock_analysis"
    assert _mask_db_url(u) == "postgresql+psycopg2://postgres:***@localhost:5432/stock_analysis"


def test_serialize_and_parse_ts():
    dt = datetime(2026, 6, 6, 12, 30, 0)
    s = _serialize_value(dt)
    assert _parse_ts(s) == dt


def test_upsert_basic_dry_run():
    conn = _Conn()
    n = upsert_basic_rows(
        conn,
        [{"board_code": "BK0428", "board_name": "电力", "trade_observe_flag": True}],
        dry_run=True,
    )
    assert n == 1
    assert conn.sqls == []


def test_dump_and_load_roundtrip():
    class _Q:
        def __init__(self, rows):
            self._rows = rows

        def fetchall(self):
            return self._rows

        def scalar(self):
            return len(self._rows)

    class _Src:
        def execute(self, sql, params=None):
            sql_s = str(sql)
            if "COUNT(*)" in sql_s:
                return _Q([(1,)])
            if "industry_board_basic_info" in sql_s:
                return _Q([("BK0428", "电力", datetime(2026, 6, 6), False)])
            if "industry_board_constituents" in sql_s:
                return _Q([("BK0428", "000001", "平安银行", datetime(2026, 6, 6))])
            return _Q([])

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    class _Engine:
        def connect(self):
            return _Src()

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "board.json"
        stats = dump_to_file(path, _Engine(), batch_size=100)
        assert stats["basic"] == 1
        assert stats["constituents"] == 1
        basic, cons = load_from_file(path)
        assert basic[0]["board_code"] == "BK0428"
        assert cons[0]["stock_code"] == "000001"
