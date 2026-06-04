"""行业板块成分股：列解析与归一化测试。"""
import pandas as pd

from backend_core.data_collectors.akshare.industry_board_constituents_ak import (
    normalize_stock_code,
    parse_cons_dataframe,
)
from backend_core.data_collectors.akshare.industry_board_normalize import (
    industry_board_to_english_df,
)


def test_normalize_stock_code():
    assert normalize_stock_code("1") == "000001"
    assert normalize_stock_code(600036) == "600036"
    assert normalize_stock_code(None) is None


def test_parse_cons_dataframe():
    df = pd.DataFrame({
        "代码": ["000001", "600036"],
        "名称": ["平安银行", "招商银行"],
        "涨跌幅": [1.0, 2.0],
    })
    rows = parse_cons_dataframe(df)
    assert len(rows) == 2
    assert rows[0] == ("000001", "平安银行")


def test_industry_board_to_english_leading_stock_columns():
    raw = pd.DataFrame({
        "板块代码": ["BK0001"],
        "板块名称": ["小金属"],
        "领涨股票": ["紫金矿业"],
        "领涨股票-涨跌幅": [3.5],
    })
    out = industry_board_to_english_df(raw)
    assert out.iloc[0]["leading_stock_name"] == "紫金矿业"
    assert float(out.iloc[0]["leading_stock_change_percent"]) == 3.5
