# -*- coding: utf-8 -*-
"""同花顺板块历史 OHLC 采集单元测试（不打外网）。"""

import pandas as pd

from backend_core.data_collectors.akshare.board_historical_ths import (
    BoardHistoricalThsCollector,
    normalize_ths_index_df,
)


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
