"""AkShare 财务映射与同比计算单元测试（不打外网）。"""

import pandas as pd

from backend_core.data_collectors.akshare.fina_indicator import (
    attach_yoy,
    normalize_end_date,
    records_from_ths_df,
    _yoy_pct,
)


def test_normalize_end_date():
    assert normalize_end_date("2024-03-31") == "20240331"
    assert normalize_end_date("20240331") == "20240331"
    assert normalize_end_date("2024年一季报") == "20240331"
    assert normalize_end_date("2023年报") == "20231231"
    assert normalize_end_date(None) is None


def test_yoy_pct():
    assert abs(_yoy_pct(1.25, 1.0) - 25.0) < 1e-9
    assert _yoy_pct(1.0, 0) is None
    assert _yoy_pct(None, 1.0) is None


def test_records_and_attach_yoy_quarter():
    df = pd.DataFrame(
        [
            {"报告期": "2024-03-31", "基本每股收益": 0.20, "净利润": 100, "营业总收入": 500},
            {"报告期": "2025-03-31", "基本每股收益": 0.30, "净利润": 150, "营业总收入": 600},
            {"报告期": "2023-12-31", "基本每股收益": 1.00, "净利润": 400, "营业总收入": 2000, "净资产收益率": 18.0},
            {"报告期": "2024-12-31", "基本每股收益": 1.25, "净利润": 500, "营业总收入": 2500, "净资产收益率": 20.0},
        ]
    )
    by_end = records_from_ths_df(df, code="600000", kind="report")
    rows = attach_yoy(by_end)
    by = {r["end_date"]: r for r in rows}
    assert by["20250331"]["q_eps_yoy"] is not None
    assert abs(by["20250331"]["q_eps_yoy"] - 50.0) < 1e-6
    assert abs(by["20250331"]["q_profit_yoy"] - 50.0) < 1e-6
    assert abs(by["20250331"]["q_sales_yoy"] - 20.0) < 1e-6
    assert abs(by["20241231"]["basic_eps_yoy"] - 25.0) < 1e-6
    assert by["20241231"]["roe"] == 20.0


def test_auto_fina_uses_akshare_without_token(monkeypatch):
    import backend_core.data_collectors.tushare.fina_indicator as mod

    monkeypatch.setattr(mod, "_tushare_token_available", lambda: False)
    called = {}

    def _fake_ak(**kwargs):
        called["ak"] = True
        return {"success": True, "source": "akshare", "rows": 1, "ok": 1, "fail": 0, "stocks": 1}

    monkeypatch.setattr(
        "backend_core.data_collectors.akshare.fina_indicator.run_akshare_fina_indicator_collect",
        _fake_ak,
    )
    monkeypatch.setenv("CANSLIM_FINA_SOURCE", "auto")
    out = mod.run_fina_indicator_collect_auto(max_stocks=1)
    assert called.get("ak") is True
    assert out["source"] == "akshare"


def test_auto_fina_force_akshare(monkeypatch):
    import backend_core.data_collectors.tushare.fina_indicator as mod

    monkeypatch.setenv("CANSLIM_FINA_SOURCE", "akshare")
    monkeypatch.setattr(
        "backend_core.data_collectors.akshare.fina_indicator.run_akshare_fina_indicator_collect",
        lambda **k: {"success": True, "source": "akshare", "rows": 2},
    )
    out = mod.run_fina_indicator_collect_auto()
    assert out["source"] == "akshare"


def test_is_tushare_access_denied():
    from backend_core.data_collectors.tushare.fina_indicator import _is_tushare_access_denied

    assert _is_tushare_access_denied(
        Exception("抱歉，您没有接口(fina_indicator)访问权限，权限的具体详情访问：https://tushare.pro/document/1?doc_id=108。")
    )
    assert not _is_tushare_access_denied(Exception("network timeout"))


def test_tushare_collect_aborts_on_permission(monkeypatch):
    """权限错误应立即中止，不得扫完全市场。"""
    from backend_core.data_collectors.tushare.fina_indicator import FinaIndicatorCollector

    coll = FinaIndicatorCollector.__new__(FinaIndicatorCollector)
    coll.logger = __import__("logging").getLogger("test")
    coll.sleep_sec = 0
    coll.ensure_table = lambda: None  # type: ignore
    coll._list_codes = lambda session, codes=None: ["000001", "000002", "000003"]  # type: ignore

    def _boom(code, start_date, end_date=None):
        raise Exception("抱歉，您没有接口(fina_indicator)访问权限，权限的具体详情访问：https://tushare.pro/document/1?doc_id=108。")

    coll.collect_one = _boom  # type: ignore
    calls = {"n": 0}
    real_list = coll._list_codes

    def _list(session, codes=None):
        calls["n"] += 1
        return real_list(session, codes)

    coll._list_codes = _list  # type: ignore

    # SessionLocal only used in _list_codes path via collect - mock list without session
    import backend_core.data_collectors.tushare.fina_indicator as mod

    class _Sess:
        def close(self):
            pass

    monkeypatch.setattr(mod, "SessionLocal", lambda: _Sess())
    out = coll.collect(years_back=1)
    assert out["success"] is False
    assert out["aborted_permission"] is True
    assert out["fail"] == 1  # 只试了第一只就中止


def test_auto_fina_fallback_on_permission(monkeypatch):
    import backend_core.data_collectors.tushare.fina_indicator as mod

    monkeypatch.setenv("CANSLIM_FINA_SOURCE", "auto")
    monkeypatch.setattr(mod, "_tushare_token_available", lambda: True)
    monkeypatch.setattr(
        mod,
        "run_fina_indicator_collect",
        lambda **k: {
            "success": False,
            "source": "tushare",
            "aborted_permission": True,
            "error": "抱歉，您没有接口(fina_indicator)访问权限",
            "ok": 0,
            "fail": 1,
            "rows": 0,
        },
    )
    monkeypatch.setattr(
        "backend_core.data_collectors.akshare.fina_indicator.run_akshare_fina_indicator_collect",
        lambda **k: {"success": True, "source": "akshare", "rows": 5, "ok": 5, "fail": 0},
    )
    out = mod.run_fina_indicator_collect_auto()
    assert out["source"] == "akshare"
    assert out.get("fallback_from") == "tushare"
    assert out["rows"] == 5


def test_auto_index_prefers_akshare(monkeypatch):
    import backend_core.data_collectors.tushare.index_daily as mod

    monkeypatch.setenv("CANSLIM_INDEX_SOURCE", "auto")
    called = {}

    def _fake_ak(**k):
        called["ak"] = True
        return {"success": True, "source": "akshare", "rows": 10}

    def _fake_ts(**k):
        called["ts"] = True
        return {"success": True, "source": "tushare", "rows": 1}

    monkeypatch.setattr(
        "backend_core.data_collectors.akshare.index_daily.run_akshare_index_daily_collect",
        _fake_ak,
    )
    monkeypatch.setattr(mod, "run_index_daily_collect", _fake_ts)
    out = mod.run_index_daily_collect_auto()
    assert called.get("ak") is True
    assert called.get("ts") is None
    assert out["source"] == "akshare"
    assert out["rows"] == 10


def test_auto_index_fallback_to_tushare(monkeypatch):
    import backend_core.data_collectors.tushare.index_daily as mod

    monkeypatch.setenv("CANSLIM_INDEX_SOURCE", "auto")
    monkeypatch.setattr(mod, "_tushare_token_available", lambda: True)
    monkeypatch.setattr(
        "backend_core.data_collectors.akshare.index_daily.run_akshare_index_daily_collect",
        lambda **k: (_ for _ in ()).throw(RuntimeError("akshare down")),
    )
    monkeypatch.setattr(
        mod,
        "run_index_daily_collect",
        lambda **k: {"success": True, "source": "tushare", "rows": 8},
    )
    out = mod.run_index_daily_collect_auto()
    assert out["source"] == "tushare"
    assert out["rows"] == 8
