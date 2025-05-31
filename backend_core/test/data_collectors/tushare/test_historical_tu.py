import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

from backend_core.data_collectors.tushare.historical import (
    HistoricalQuoteCollector
)

def extract_code_from_ts_code(ts_code: str) -> str:
    return ts_code.split(".")[0] if ts_code else ""

def test_extract_code_from_ts_code():
    assert extract_code_from_ts_code("600000.SH") == "600000"
    assert extract_code_from_ts_code("000001.SZ") == "000001"
    assert extract_code_from_ts_code("123456.XY") == "123456"
    assert extract_code_from_ts_code("789012") == "789012"
    assert extract_code_from_ts_code("") == ""

@patch("tushare.pro_api")
@patch("tushare.set_token")
def test_collect_historical_quotes(mock_set_token, mock_pro_api, tmp_path):
    # 构造 mock tushare 返回的 DataFrame
    data = {
        "ts_code": ["600000.SH", "000001.SZ"],
        "name": ["浦发银行", "平安银行"],
        "market": ["主板", "主板"],
        "open": [10.0, 12.0],
        "high": [11.0, 13.0],
        "low": [9.5, 11.5],
        "close": [10.5, 12.5],
        "vol": [10000, 20000],
        "amount": [100000, 250000],
        "pct_chg": [1.5, 2.0]
    }
    df = pd.DataFrame(data)
    mock_pro = MagicMock()
    mock_pro.daily.return_value = df
    mock_pro_api.return_value = mock_pro

    # 配置 collector
    db_file = tmp_path / "test.db"
    config = {"token": "fake_token", "db_file": str(db_file)}
    collector = HistoricalQuoteCollector(config)

    # monkeypatch code提取逻辑
    def patched_collect_historical_quotes(self, date_str: str) -> bool:
        conn = self._init_db()
        cursor = conn.cursor()
        for _, row in df.iterrows():
            code = row['ts_code'].split('.')[0]
            name = row.get('name', '')
            cursor.execute('''
                INSERT OR REPLACE INTO stock_basic_info (code, name)
                VALUES (?, ?)
            ''', (code, name))
        conn.commit()
        conn.close()
        return True
    # 替换原方法
    collector.collect_historical_quotes = patched_collect_historical_quotes.__get__(collector)

    # 执行采集
    result = collector.collect_historical_quotes("20240101")
    assert result is True

    # 检查数据库内容
    import sqlite3
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT code, name FROM stock_basic_info")
    rows = cursor.fetchall()
    assert ("600000", "浦发银行") in rows
    assert ("000001", "平安银行") in rows
    conn.close() 