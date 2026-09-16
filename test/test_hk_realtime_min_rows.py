"""港股实时采集：数据量低于 100 条判定失败。"""

import pandas as pd
import pytest

from backend_core.data_collectors.akshare.hk_realtime import (
    HK_REALTIME_MIN_ROWS,
    HKRealtimeInsufficientDataError,
    hk_realtime_insufficient_error,
    hk_realtime_row_count,
    hk_realtime_spot_insufficient,
)


def test_min_rows_threshold_is_100():
    assert HK_REALTIME_MIN_ROWS == 100


def test_spot_insufficient_none_and_empty():
    assert hk_realtime_spot_insufficient(None) is True
    assert hk_realtime_spot_insufficient(pd.DataFrame()) is True
    assert hk_realtime_row_count(None) == 0


def test_spot_insufficient_below_threshold():
    df = pd.DataFrame({"代码": [f"{i:05d}" for i in range(99)]})
    assert hk_realtime_spot_insufficient(df) is True


def test_spot_sufficient_at_threshold():
    df = pd.DataFrame({"代码": [f"{i:05d}" for i in range(100)]})
    assert hk_realtime_spot_insufficient(df) is False


def test_insufficient_error_message():
    err = hk_realtime_insufficient_error(12)
    assert isinstance(err, HKRealtimeInsufficientDataError)
    assert isinstance(err, RuntimeError)
    assert "12" in str(err)
    assert "100" in str(err)
    with pytest.raises(HKRealtimeInsufficientDataError):
        raise err


def test_file_fallback_used_when_api_insufficient(monkeypatch):
    from backend_core.data_collectors.akshare.hk_realtime import HKRealtimeQuoteCollector

    collector = HKRealtimeQuoteCollector({})
    monkeypatch.setattr(collector, "_init_db", lambda: True)
    monkeypatch.setattr(collector, "_retry_on_failure", lambda fn: pd.DataFrame({"代码": ["00700"]}))

    called = {}

    def _fake_file_collect(*args, **kwargs):
        called["ok"] = True
        called["allow_latest"] = kwargs.get("allow_latest")
        return {
            "success": True,
            "written": 200,
            "file": "backend_core/data/hk_fund_flow_20260914.xls",
        }

    monkeypatch.setattr(
        "backend_core.data_collectors.akshare.hk_fund_flow_from_file.collect_hk_realtime_quotes_from_file",
        _fake_file_collect,
    )

    class _Sess:
        def execute(self, *a, **k):
            return None

        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None

    monkeypatch.setattr(
        "backend_core.data_collectors.akshare.hk_realtime.SessionLocal",
        lambda: _Sess(),
    )
    assert collector.collect_quotes() is True
    assert called.get("ok") is True
    assert called.get("allow_latest") is False


def test_file_fallback_errors_when_today_file_missing(monkeypatch):
    from backend_core.data_collectors.akshare.hk_realtime import HKRealtimeQuoteCollector

    collector = HKRealtimeQuoteCollector({})
    monkeypatch.setattr(collector, "_init_db", lambda: True)
    monkeypatch.setattr(collector, "_retry_on_failure", lambda fn: pd.DataFrame({"代码": ["00700"]}))

    monkeypatch.setattr(
        "backend_core.data_collectors.akshare.hk_fund_flow_from_file.collect_hk_realtime_quotes_from_file",
        lambda *a, **k: {
            "success": False,
            "error": "未找到当日港股资金流向文件: backend_core/data/hk_fund_flow_20260915.*（接口无数据且当日文件不存在，按错误处理）",
            "written": 0,
        },
    )

    with pytest.raises(HKRealtimeInsufficientDataError) as ei:
        collector.collect_quotes()
    assert "当日港股资金流向文件" in str(ei.value)
