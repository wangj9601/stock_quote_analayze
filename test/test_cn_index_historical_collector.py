# -*- coding: utf-8 -*-
"""A股指数实时→历史归档单元测试（不打外网）。"""

from backend_core.data_collectors.akshare.cn_index_historical_collector import (
    CNIndexHistoricalCollector,
    code_to_ts_code,
)


def test_code_to_ts_code():
    assert code_to_ts_code("sh000300") == "000300.SH"
    assert code_to_ts_code("sz399001") == "399001.SZ"
    assert code_to_ts_code("000300") == "000300.SH"
    assert code_to_ts_code("399006") == "399006.SZ"


def test_cn_index_historical_archive(monkeypatch):
    captured = {}

    class FakeRow:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    class FakeResult:
        def __init__(self, rows):
            self._rows = rows

        def fetchall(self):
            return self._rows

    class FakeSession:
        def execute(self, sql, params=None):
            sql_s = str(sql)
            if "FROM index_realtime_quotes" in sql_s:
                return FakeResult(
                    [
                        FakeRow(
                            code="sh000300",
                            name="沪深300",
                            price=3500.0,
                            change=10.0,
                            pct_chg=0.3,
                            open=3490.0,
                            pre_close=3490.0,
                            high=3510.0,
                            low=3480.0,
                            volume=1e9,
                            amount=2e9,
                            update_time="2026-01-02 15:00:00",
                        )
                    ]
                )
            captured.setdefault("upserts", []).append(params or {})
            return FakeResult([])

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(
        "backend_core.data_collectors.akshare.cn_index_historical_collector.SessionLocal",
        lambda: FakeSession(),
    )

    result = CNIndexHistoricalCollector().collect_daily_to_historical("2026-01-02")
    assert result["success"] == 1
    assert captured["upserts"][0]["ts_code"] == "000300.SH"
    assert captured["upserts"][0]["close"] == 3500.0
