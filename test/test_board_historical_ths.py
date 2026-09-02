# -*- coding: utf-8 -*-
"""同花顺板块历史 OHLC 采集单元测试（不打外网）。"""

import pandas as pd

from backend_core.data_collectors.akshare.board_historical_ths import (
    BoardHistoricalThsCollector,
    _parse_ths_line_payload,
    normalize_board_name,
    normalize_ths_index_df,
)


def test_normalize_board_name():
    assert normalize_board_name(" 电池化学 品 ") == "电池化学品"
    assert normalize_board_name("半导体设 备") == "半导体设备"
    assert normalize_board_name(" 微盘股") == "微盘股"


def test_parse_ths_line_payload():
    text = (
        'quotebridge_v4_line_bk_884218_01_2026({"data":'
        '"20260105,100,110,90,105,1000,50000.000,,,,0;'
        '20260106,105,120,100,115,2000,80000.000,,,,0;"})'
    )
    df = _parse_ths_line_payload(text)
    assert len(df) == 2
    assert float(df.iloc[0]["收盘价"]) == 105.0
    assert float(df.iloc[1]["成交量"]) == 2000.0


def test_normalize_ths_index_df():
    df = pd.DataFrame(
        [
            {
                "日期": "2026-01-02",
                "开盘价": 1000.0,
                "最高价": 1010.0,
                "最低价": 990.0,
                "收盘价": 1005.0,
                "成交量": 12345,
                "成交额": 999999.0,
            }
        ]
    )
    out = normalize_ths_index_df(df)
    assert len(out) == 1
    assert out.iloc[0]["_trade_date"].strftime("%Y-%m-%d") == "2026-01-02"


def test_board_historical_ths_upsert(monkeypatch):
    upserts = []

    class FakeSession:
        def execute(self, sql, params=None):
            if params and "board_code" in params:
                upserts.append(dict(params))
            return self

        def commit(self):
            pass

        def close(self):
            pass

        def fetchall(self):
            return []

    monkeypatch.setattr(
        "backend_core.data_collectors.akshare.board_historical_ths.SessionLocal",
        lambda: FakeSession(),
    )

    df = normalize_ths_index_df(
        pd.DataFrame(
            [
                {
                    "日期": "2026-01-02",
                    "开盘价": 100.0,
                    "最高价": 110.0,
                    "最低价": 90.0,
                    "收盘价": 105.0,
                    "成交量": 1000,
                    "成交额": 50000.0,
                }
            ]
        )
    )

    collector = BoardHistoricalThsCollector(request_interval=0)
    n = collector.upsert_rows("industry", "881101", "测试行业", df)
    assert n == 1
    assert upserts[0]["board_code"] == "881101"
    assert upserts[0]["close"] == 105.0
    assert upserts[0]["collected_source"] == "tonghuashun"


def test_collect_board_uses_code_first(monkeypatch):
    calls = {}

    def _fake_by_code(code, start, end):
        calls["by_code"] = (code, start, end)
        return normalize_ths_index_df(
            pd.DataFrame(
                [
                    {
                        "日期": "2026-09-01",
                        "开盘价": 1,
                        "最高价": 2,
                        "最低价": 1,
                        "收盘价": 1.5,
                        "成交量": 10,
                        "成交额": 100,
                    }
                ]
            )
        )

    monkeypatch.setattr(
        "backend_core.data_collectors.akshare.board_historical_ths.fetch_ths_board_index_by_code",
        _fake_by_code,
    )
    monkeypatch.setattr(
        "backend_core.data_collectors.akshare.board_historical_ths.BoardHistoricalThsCollector.upsert_rows",
        lambda self, *args, **kwargs: 1,
    )
    collector = BoardHistoricalThsCollector(request_interval=0)
    result = collector.collect_board(
        "industry", "884218", "机器人", "20260901", "20260902"
    )
    assert result["ok"] is True
    assert calls["by_code"][0] == "884218"


def test_load_boards_filters_tonghuashun(monkeypatch):
    class FakeRow:
        def __init__(self, board_code, board_name):
            self.board_code = board_code
            self.board_name = board_name

    class FakeResult:
        def __init__(self, rows):
            self._rows = rows

        def fetchall(self):
            return self._rows

    class FakeSession:
        def execute(self, sql, params=None):
            assert params["src"] == "tonghuashun"
            return FakeResult([FakeRow("881101", "半导体")])

        def close(self):
            pass

    monkeypatch.setattr(
        "backend_core.data_collectors.akshare.board_historical_ths.SessionLocal",
        lambda: FakeSession(),
    )

    boards = BoardHistoricalThsCollector().load_boards("industry")
    assert boards == [("881101", "半导体")]
