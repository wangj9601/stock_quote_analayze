# -*- coding: utf-8 -*-
"""回归：StockCodeTextPK 与整数比较时绑定为字符串，避免 PostgreSQL text = integer。"""

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from backend_api.models import StockBasicInfo


def test_stock_code_text_pk_bind_processor_coerces_int_to_str():
    col_type = StockBasicInfo.code.type
    dialect = postgresql.dialect()
    proc = col_type.bind_processor(dialect)
    assert proc is not None
    assert proc(601868) == "601868"
    assert proc(1) == "1"


@pytest.mark.skipif(
    __import__("importlib.util", fromlist=["find_spec"]).find_spec("numpy") is None,
    reason="numpy not installed",
)
def test_stock_code_text_pk_bind_processor_coerces_numpy_scalar():
    import numpy as np

    col_type = StockBasicInfo.code.type
    dialect = postgresql.dialect()
    proc = col_type.bind_processor(dialect)
    assert proc(np.int64(601868)) == "601868"


def test_stock_code_text_pk_coerce_compared_value_uses_decorator_for_int_literal():
    """编译 WHERE code == 601868 时，PostgreSQL 方言应生成 CAST，避免裸参数被当作 integer 与 text 列比较。"""
    stmt = select(StockBasicInfo).where(StockBasicInfo.code == 601868).limit(1)
    compiled = stmt.compile(dialect=postgresql.dialect())
    sql = str(compiled).lower()
    assert "stock_basic_info.code" in sql
    assert "cast(" in sql and "varchar" in sql
    # 绑定值可为 int，由 SQL 侧 CAST 转为与 text 列可比
    assert any(v == 601868 for v in compiled.params.values())


def test_stock_basic_info_code_column_is_stock_code_text_pk():
    assert StockBasicInfo.code.type.__class__.__name__ == "StockCodeTextPK"
