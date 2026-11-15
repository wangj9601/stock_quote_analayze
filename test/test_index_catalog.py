# -*- coding: utf-8 -*-
"""首页其他指数目录：匹配规则与「仅有实时行情也可进入详情」。"""

from sqlalchemy import bindparam, text
from sqlalchemy.dialects import postgresql

from backend_api.market_routes import (
    _A_INDEX_CATALOG_CTE,
    catalog_like_pattern,
    normalize_catalog_market,
)
from backend_core.analysis.index_bars import resolve_index_identity


def test_catalog_market_and_like():
    assert normalize_catalog_market("hk") == "hk"
    assert normalize_catalog_market("HK-stock") == "hk"
    assert normalize_catalog_market("") == "a"
    assert catalog_like_pattern("  中证500 ") == "%中证500%"
    assert catalog_like_pattern("%_") == ""
    assert catalog_like_pattern("") == ""


def test_catalog_sql_excludes_pinned_with_expanding_bind():
    stmt = text(
        _A_INDEX_CATALOG_CTE
        + " SELECT code FROM latest WHERE code NOT IN :pinned"
    ).bindparams(
        bindparam("pinned", value=["000001", "399001"], expanding=True)
    )
    compiled = str(
        stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"render_postcompile": True},
        )
    )
    assert "DISTINCT ON" in compiled
    assert "NOT IN (%(pinned_1)s, %(pinned_2)s)" in compiled


class _Result:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _Db:
    def __init__(self, realtime_name=None, has_hist=False):
        self.realtime_name = realtime_name
        self.has_hist = has_hist

    def execute(self, sql, params=None):
        sql_s = str(sql)
        if "FROM index_realtime_quotes" in sql_s:
            return _Result((self.realtime_name,) if self.realtime_name else None)
        if "FROM index_historical_quotes" in sql_s:
            return _Result((1,) if self.has_hist else None)
        return _Result(None)

    def rollback(self):
        return None


def test_realtime_only_index_can_open_detail():
    ident = resolve_index_identity(_Db(realtime_name="中证500"), "000905")
    assert ident["ok"] is True
    assert ident["name"] == "中证500"
    assert ident["code"] == "000905"


def test_unknown_index_without_quotes_stays_missing():
    ident = resolve_index_identity(_Db(), "000905")
    assert ident["ok"] is False


def test_known_index_still_opens_without_rows():
    ident = resolve_index_identity(_Db(), "000001")
    assert ident["ok"] is True
    assert ident["name"] == "上证指数"
