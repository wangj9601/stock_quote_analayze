"""行业板块 catalog 去重单元测试（同名不同来源可并存）。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_api.utils.industry_board_query import dedupe_industry_board_catalog


class TestIndustryBoardCatalog:
    def test_dedupe_same_name_same_source_prefers_bk(self):
        items = [
            {"board_code": "白色家电", "board_name": "白色家电", "board_code_source": "eastmoney"},
            {"board_code": "BK0420", "board_name": "白色家电", "board_code_source": "eastmoney"},
            {"board_code": "半导体", "board_name": "半导体", "board_code_source": "eastmoney"},
            {"board_code": "BK0421", "board_name": "半导体", "board_code_source": "eastmoney"},
        ]
        out = dedupe_industry_board_catalog(items)
        codes = {x["board_code"] for x in out}
        assert codes == {"BK0420", "BK0421"}
        assert len(out) == 2

    def test_same_name_different_source_kept(self):
        items = [
            {"board_code": "BK0420", "board_name": "白色家电", "board_code_source": "eastmoney"},
            {"board_code": "881180", "board_name": "白色家电", "board_code_source": "tonghuashun"},
        ]
        out = dedupe_industry_board_catalog(items)
        assert len(out) == 2
        sources = {x["board_code_source"] for x in out}
        assert sources == {"eastmoney", "tonghuashun"}
        assert all(x.get("board_code_source_label") for x in out)

    def test_ths_same_name_prefers_881_over_bk(self):
        """同花顺来源下误混入的 BK 码不应挤掉真·同花顺 881 码（行情页 92→91 根因）。"""
        items = [
            {
                "board_code": "BK1705",
                "board_name": "航天装备",
                "board_code_source": "tonghuashun",
                "stock_count": 10,
            },
            {
                "board_code": "881166",
                "board_name": "航天装备",
                "board_code_source": "tonghuashun",
                "stock_count": 88,
            },
        ]
        out = dedupe_industry_board_catalog(items)
        assert len(out) == 1
        assert out[0]["board_code"] == "881166"
        assert out[0]["stock_count"] == 88

    def test_dedupe_keeps_distinct_names(self):
        items = [
            {"board_code": "白酒", "board_name": "白酒", "board_code_source": "tonghuashun"},
            {"board_code": "BK1001", "board_name": "白酒II", "board_code_source": "eastmoney"},
            {"board_code": "BK1002", "board_name": "白酒III", "board_code_source": "eastmoney"},
        ]
        out = dedupe_industry_board_catalog(items)
        assert len(out) == 3

    def test_dedupe_uses_code_when_name_empty(self):
        items = [
            {"board_code": "BK0420", "board_name": None, "board_code_source": "eastmoney"},
            {"board_code": "BK0421", "board_name": "", "board_code_source": "eastmoney"},
        ]
        out = dedupe_industry_board_catalog(items)
        assert len(out) == 2

    def test_dedupe_merges_trade_observe_flag(self):
        items = [
            {
                "board_code": "IT服务",
                "board_name": "IT服务",
                "trade_observe_flag": True,
                "board_code_source": "eastmoney",
            },
            {
                "board_code": "BK1045",
                "board_name": "IT服务",
                "trade_observe_flag": False,
                "board_code_source": "eastmoney",
            },
        ]
        out = dedupe_industry_board_catalog(items)
        assert len(out) == 1
        assert out[0]["board_code"] == "BK1045"
        assert out[0]["trade_observe_flag"] is True

    def test_null_source_defaults_to_eastmoney_legacy(self):
        items = [
            {"board_code": "BK0420", "board_name": "白色家电", "board_code_source": None},
        ]
        out = dedupe_industry_board_catalog(items)
        assert out[0]["board_code_source"] == "eastmoney"
        assert out[0]["board_code_source_label"] == "东方财富"

    def test_dedupe_preserves_stock_count(self):
        items = [
            {
                "board_code": "BK0420",
                "board_name": "白色家电",
                "board_code_source": "tonghuashun",
                "stock_count": 128,
            },
            {
                "board_code": "881180",
                "board_name": "白色家电",
                "board_code_source": "tonghuashun",
                "member_count": 3,
            },
        ]
        out = dedupe_industry_board_catalog(items)
        assert len(out) == 1
        # 同花顺来源优先 881，非 BK；成分数取组内最大
        assert out[0]["board_code"] == "881180"
        assert out[0]["stock_count"] == 128
        assert out[0]["member_count"] == 128


def test_fetch_industry_board_catalog_filters_hidden():
    from backend_api.utils.industry_board_query import fetch_industry_board_catalog

    class _DB:
        def execute(self, sql, params=None):
            sql_s = str(sql)
            assert "frontend_visible_flag" in sql_s
            assert "COALESCE(b.frontend_visible_flag, TRUE) = TRUE" in sql_s
            assert "board_code_source" in sql_s
            assert "industry_board_constituents" in sql_s
            assert "stock_count" in sql_s
            return type("R", (), {"fetchall": lambda self: []})()

    assert fetch_industry_board_catalog(_DB()) == []


def test_fetch_industry_board_catalog_includes_member_count():
    from backend_api.utils.industry_board_query import fetch_industry_board_catalog

    class _DB:
        def execute(self, sql, params=None):
            return type(
                "R",
                (),
                {
                    "fetchall": lambda self: [
                        ("881101", "半导体", True, "tonghuashun", 128),
                        ("BK0477", "银行", False, "eastmoney", 40),
                    ]
                },
            )()

    out = fetch_industry_board_catalog(_DB())
    by_code = {x["board_code"]: x for x in out}
    assert by_code["881101"]["stock_count"] == 128
    assert by_code["881101"]["member_count"] == 128
    assert by_code["BK0477"]["stock_count"] == 40
