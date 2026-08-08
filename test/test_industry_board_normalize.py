"""行业板块列名归一化单元测试。"""
import pandas as pd

from backend_core.data_collectors.akshare.industry_board_normalize import (
    enrich_leading_stock_codes,
    industry_board_to_english_df,
    normalize_ths_industry_df,
)


def test_em_new_column_names():
    raw = pd.DataFrame(
        {
            "板块代码": ["BK0001"],
            "板块名称": ["小金属"],
            "最新价": [100.0],
            "涨跌幅": [1.2],
            "上涨家数": [10],
            "下跌家数": [5],
            "领涨股票": ["紫金矿业"],
            "领涨股票-涨跌幅": [3.5],
        }
    )
    out = industry_board_to_english_df(raw)
    assert out.iloc[0]["leading_stock_name"] == "紫金矿业"
    assert float(out.iloc[0]["leading_stock_change_percent"]) == 3.5
    assert int(out.iloc[0]["up_count"]) == 10


def test_legacy_column_names():
    raw = pd.DataFrame(
        {
            "板块代码": ["BK0002"],
            "板块名称": ["银行"],
            "领涨股": ["招商银行"],
            "领涨股涨跌幅": [2.1],
            "领涨股代码": ["600036"],
        }
    )
    out = industry_board_to_english_df(raw)
    assert out.iloc[0]["leading_stock_code"] == "600036"


def test_enrich_leading_stock_code_from_map():
    raw = industry_board_to_english_df(
        pd.DataFrame(
            {
                "板块代码": ["BK0003"],
                "板块名称": ["测试"],
                "领涨股票": ["测试股份"],
            }
        )
    )
    out = enrich_leading_stock_codes(raw, {"测试股份": "000001"})
    assert out.iloc[0]["leading_stock_code"] == "000001"


def test_normalize_ths():
    raw = pd.DataFrame(
        {
            "板块": ["半导体"],
            "涨跌幅": [1.0],
            "均价": [82.81],
            "上涨家数": [8],
            "下跌家数": [2],
            "领涨股": ["中芯国际"],
            "领涨股-涨跌幅": [5.0],
        }
    )
    ths = normalize_ths_industry_df(raw)
    out = industry_board_to_english_df(ths)
    assert out.iloc[0]["board_name"] == "半导体"
    assert out.iloc[0]["leading_stock_name"] == "中芯国际"
    # 均价不得映射为板块指数 latest_price
    assert out.iloc[0]["latest_price"] is None or pd.isna(out.iloc[0]["latest_price"])
    assert "均价" not in ths.columns or ths.iloc[0].get("最新价") is None
