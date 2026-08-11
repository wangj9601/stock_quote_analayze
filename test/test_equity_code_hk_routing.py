# -*- coding: utf-8 -*-
"""5 位港股 / 6 位 A 股代码路由与行情加载单测。"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend_api"))


def test_normalize_equity_code_hk_and_cn():
    from backend_api.utils.equity_code import (
        infer_market_type,
        is_cn_equity_code,
        is_hk_equity_code,
        normalize_equity_code,
        partition_codes_by_market,
        quotes_table_for_code,
    )

    assert normalize_equity_code("700") == "00700"
    assert normalize_equity_code("0700") == "00700"
    assert normalize_equity_code("00700") == "00700"
    assert normalize_equity_code("HK00700") == "00700"
    assert normalize_equity_code("600519") == "600519"
    assert normalize_equity_code("SH600519") == "600519"
    assert normalize_equity_code("1") == "00001"

    assert is_hk_equity_code("00700")
    assert is_hk_equity_code("700")
    assert not is_hk_equity_code("600519")
    assert is_cn_equity_code("600519")
    assert not is_cn_equity_code("00700")

    assert infer_market_type("00700") == "HK"
    assert infer_market_type("600519") == "CN"
    assert quotes_table_for_code("00700") == "historical_quotes_hk"
    assert quotes_table_for_code("600519") == "historical_quotes"

    cn, hk = partition_codes_by_market(["600519", "700", "00700", "000001"])
    assert cn == ["600519", "000001"]
    assert hk == ["00700"]


def test_batch_load_ohlc_asc_routes_hk_to_hk_table():
    from backend_core.strategies.double_bottom import data_loader as dl

    db = MagicMock()
    hk_row = ("00700", "2024-01-02", 300.0, 290.0, 295.0, 1e6, "腾讯")
    cn_row = ("600519", "2024-01-02", 1800.0, 1790.0, 1795.0, 1e5, "贵州茅台")
    tables_seen = []

    def _execute(sql, params):
        result = MagicMock()
        sql_s = str(sql)
        codes = list(params.get("codes") or [])
        if "historical_quotes_hk" in sql_s:
            tables_seen.append("hk")
            assert codes == ["00700"]
            result.fetchall.return_value = [hk_row]
        else:
            tables_seen.append("cn")
            assert codes == ["600519"]
            result.fetchall.return_value = [cn_row]
        return result

    db.execute.side_effect = _execute

    out = dl.batch_load_ohlc_asc(db, ["00700", "600519"], lookback=60)
    assert set(out.keys()) == {"00700", "600519"}
    assert out["00700"][0]["close"] == 295.0
    assert out["600519"][0]["close"] == 1795.0
    assert tables_seen == ["cn", "hk"]


def test_batch_load_ohlc_asc_five_digit_only_hits_hk():
    from backend_core.strategies.double_bottom import data_loader as dl

    db = MagicMock()
    tables_seen = []

    def _execute(sql, params):
        result = MagicMock()
        sql_s = str(sql)
        if "historical_quotes_hk" in sql_s:
            tables_seen.append("hk")
            assert list(params.get("codes") or []) == ["00700"]
            result.fetchall.return_value = [
                ("00700", "2024-06-01", 380.0, 370.0, 375.0, 2e6, "腾讯控股")
            ]
        else:
            tables_seen.append("cn")
            result.fetchall.return_value = []
        return result

    db.execute.side_effect = _execute
    out = dl.batch_load_ohlc_asc(db, ["700"], lookback=60)
    assert list(out.keys()) == ["00700"]
    assert out["00700"][0]["close"] == 375.0
    # 仅 5 位码时不应查询 A 股表（cn 列表为空，_fetch 直接跳过）
    assert tables_seen == ["hk"]


def test_pattern_route_rejects_hk_qfq():
    import backend_api.permissions as perm_mod
    import backend_api.stock.stock_analysis_routes as levels_routes
    from backend_api.database import get_db
    from backend_api.stock.pattern_routes import router
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(router)

    def _fake_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = _fake_db
    client = TestClient(app)

    with patch.object(perm_mod, "user_has_permission", return_value=True), patch.object(
        levels_routes,
        "resolve_levels_stock_identifier",
        return_value={"status": "ok", "code": "00700", "name": "腾讯"},
    ):
        resp = client.get("/api/analysis/patterns/00700?adjust=qfq")

    assert resp.status_code == 400
    detail = resp.json().get("detail") or ""
    assert "港股" in str(detail)


def test_pattern_route_loads_hk_bars_for_five_digit():
    import backend_api.permissions as perm_mod
    import backend_api.stock.stock_analysis_routes as levels_routes
    import backend_core.analysis.chart_patterns.engine as engine_mod
    import backend_core.strategies.double_bottom.data_loader as dl
    from backend_api.database import get_db
    from backend_api.stock.pattern_routes import router
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(router)

    def _fake_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = _fake_db
    client = TestClient(app)

    bars = [
        {
            "date": f"2024-01-{i + 1:02d}",
            "open": 100,
            "high": 101,
            "low": 99,
            "close": 100,
            "volume": 1,
        }
        for i in range(31)
    ]

    with patch.object(perm_mod, "user_has_permission", return_value=True), patch.object(
        levels_routes,
        "resolve_levels_stock_identifier",
        return_value={"status": "ok", "code": "00700", "name": "腾讯"},
    ), patch.object(
        dl, "resolve_effective_trade_date", return_value="2024-01-31"
    ) as asof_mock, patch.object(
        dl, "batch_load_ohlc_asc", return_value={"00700": bars}
    ) as load_mock, patch.object(
        dl, "load_names", return_value={"00700": "腾讯"}
    ), patch.object(engine_mod, "detect_all", return_value=[]):
        resp = client.get("/api/analysis/patterns/00700?adjust=none")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["code"] == "00700"
    assert body["name"] == "腾讯"
    load_mock.assert_called()
    assert load_mock.call_args.args[1] == ["00700"]
    assert asof_mock.call_args.kwargs.get("market") == "HK"


def test_levels_resolve_five_digit_code():
    from backend_api.stock.stock_analysis_routes import resolve_levels_stock_identifier

    out = resolve_levels_stock_identifier(MagicMock(), "700")
    assert out["status"] == "ok"
    assert out["code"] == "00700"

    out2 = resolve_levels_stock_identifier(MagicMock(), "00700 腾讯")
    assert out2["status"] == "ok"
    assert out2["code"] == "00700"

    out3 = resolve_levels_stock_identifier(MagicMock(), "600519")
    assert out3["status"] == "ok"
    assert out3["code"] == "600519"
