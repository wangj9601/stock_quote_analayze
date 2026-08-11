"""「我的」频道支撑/压力：轻量 get_key_levels_only 与 levels 路由包装。"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend_api"))

from stock.stock_analysis import KeyLevels, StockAnalysisService  # noqa: E402
from stock.stock_analysis_routes import resolve_levels_stock_identifier  # noqa: E402


def _fake_bars(n=80, seed=7):
    import random

    random.seed(seed)
    bars = []
    for i in range(n):
        cluster = [13.0, 15.0, 17.0][i % 3]
        px = cluster + random.uniform(-0.15, 0.15)
        bars.append(
            {
                "code": "600519",
                "name": "贵州茅台",
                "close": round(px, 2),
                "volume": 1_000_000 + (i % 3) * 500_000,
            }
        )
    return bars


def test_get_key_levels_only_success():
    bars = _fake_bars()
    svc = StockAnalysisService.__new__(StockAnalysisService)
    with patch.object(svc, "_get_historical_data", return_value=bars), patch.object(
        svc, "_get_current_price", return_value=15.0
    ):
        result = svc.get_key_levels_only("600519", max_levels=8)

    assert result["success"] is True
    data = result["data"]
    assert data["stock_code"] == "600519"
    assert data["stock_name"] == "贵州茅台"
    assert data["method"] == "kde_volume_weighted"
    assert data["current_price"] == 15.0
    assert data["current_price_source"] == "realtime"
    assert "description" in data
    assert data["kde_lookback_initial"] == KeyLevels.KDE_LOOKBACK_DAYS
    assert isinstance(data["support_levels"], list)
    assert isinstance(data["resistance_levels"], list)


def test_get_key_levels_only_fallback_daily_close():
    """实时表无有效价时，现价回退日K最新收盘，并标注 daily_close。"""
    bars = _fake_bars()
    last_close = float(bars[-1]["close"])
    svc = StockAnalysisService.__new__(StockAnalysisService)
    with patch.object(svc, "_get_historical_data", return_value=bars), patch.object(
        svc, "_get_current_price", return_value=None
    ):
        result = svc.get_key_levels_only("600519", max_levels=8)

    assert result["success"] is True
    data = result["data"]
    assert data["current_price"] == last_close
    assert data["current_price_source"] == "daily_close"


def test_get_key_levels_only_rejects_zero_realtime():
    """实时表 current_price=0 视为无效，回退日K。"""
    bars = _fake_bars()
    last_close = float(bars[-1]["close"])
    svc = StockAnalysisService.__new__(StockAnalysisService)
    # _resolve_anchor_price 经 _valid_price；直接测 resolve
    with patch.object(svc, "_get_current_price", return_value=None):
        px, src = svc._resolve_anchor_price("600519", bars)
    assert px == last_close
    assert src == "daily_close"
    assert StockAnalysisService._valid_price(0) is None
    assert StockAnalysisService._valid_price(0.0) is None
    assert StockAnalysisService._valid_price(None) is None
    assert StockAnalysisService._valid_price(12.3) == 12.3


def test_get_current_price_uses_a_share_realtime_table():
    """A 股从 stock_realtime_quote 按 trade_date 降序取 current_price。"""
    row = MagicMock()
    row.current_price = 18.66
    q = MagicMock()
    q.filter.return_value = q
    q.order_by.return_value = q
    q.first.return_value = row

    svc = StockAnalysisService.__new__(StockAnalysisService)
    svc.db = MagicMock()
    svc.db.query.return_value = q
    with patch.object(svc, "_is_hk_stock", return_value=False):
        assert svc._get_current_price("600519") == 18.66
    from models import StockRealtimeQuote

    svc.db.query.assert_called_with(StockRealtimeQuote)


def test_get_current_price_uses_hk_realtime_table():
    """港股从 stock_realtime_quote_hk 取有效现价。"""
    row = MagicMock()
    row.current_price = 88.5
    q = MagicMock()
    q.filter.return_value = q
    q.order_by.return_value = q
    q.first.return_value = row

    svc = StockAnalysisService.__new__(StockAnalysisService)
    svc.db = MagicMock()
    svc.db.query.return_value = q
    with patch.object(svc, "_is_hk_stock", return_value=True):
        assert svc._get_current_price("00700") == 88.5
    from models import StockRealtimeQuoteHK

    svc.db.query.assert_called_with(StockRealtimeQuoteHK)


def test_get_key_levels_only_no_history():
    svc = StockAnalysisService.__new__(StockAnalysisService)
    with patch.object(svc, "_get_historical_data", return_value=[]):
        result = svc.get_key_levels_only("600519")

    assert result["success"] is False
    assert result["data"]["kde_reason"] == "no_historical_data"
    assert result["data"]["support_levels"] == []


def test_resolve_levels_stock_identifier_by_code():
    db = MagicMock()
    out = resolve_levels_stock_identifier(db, "600519")
    assert out["status"] == "ok"
    assert out["code"] == "600519"
    db.query.assert_not_called()


def test_resolve_levels_stock_identifier_code_name_combo():
    db = MagicMock()
    out = resolve_levels_stock_identifier(db, "600519 贵州茅台")
    assert out["status"] == "ok"
    assert out["code"] == "600519"


def test_resolve_levels_stock_identifier_exact_name():
    row = MagicMock()
    row.code = "600519"
    row.name = "贵州茅台"

    db = MagicMock()
    # A 股 exact 命中一次；港股 exact 为空；不会走到 fuzzy
    call_count = {"n": 0}

    def _query(model):
        call_count["n"] += 1
        q = MagicMock()
        q.filter.return_value = q
        q.limit.return_value = q
        # 第 1 次 StockBasicInfo exact
        if call_count["n"] == 1:
            q.all.return_value = [row]
        else:
            q.all.return_value = []
        return q

    db.query.side_effect = _query
    out = resolve_levels_stock_identifier(db, "贵州茅台")
    assert out["status"] == "ok"
    assert out["code"] == "600519"
    assert out["name"] == "贵州茅台"


def test_resolve_levels_stock_identifier_ambiguous():
    r1 = MagicMock(code="000001", name="平安银行")
    r2 = MagicMock(code="601318", name="中国平安")

    db = MagicMock()
    call_count = {"n": 0}

    def _query(model):
        call_count["n"] += 1
        q = MagicMock()
        q.filter.return_value = q
        q.limit.return_value = q
        # exact 全空，fuzzy 返回多条（A 股 like）
        if call_count["n"] <= 2:
            q.all.return_value = []
        elif call_count["n"] == 3:
            q.all.return_value = [r1, r2]
        else:
            q.all.return_value = []
        return q

    db.query.side_effect = _query
    out = resolve_levels_stock_identifier(db, "平安")
    assert out["status"] == "ambiguous"
    assert len(out["candidates"]) >= 2
    codes = {c["code"] for c in out["candidates"]}
    assert "000001" in codes
    assert "601318" in codes


def test_resolve_levels_stock_identifier_not_found():
    db = MagicMock()
    q = MagicMock()
    q.filter.return_value = q
    q.limit.return_value = q
    q.all.return_value = []
    db.query.return_value = q
    out = resolve_levels_stock_identifier(db, "不存在的股票XYZ")
    assert out["status"] == "not_found"
    assert "未找到" in out["message"]


def test_levels_route_uses_lightweight_method():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from stock.stock_analysis_routes import router

    app = FastAPI()
    app.include_router(router)

    def _fake_db():
        yield None

    app.dependency_overrides[get_db] = _fake_db
    client = TestClient(app)

    fake = {
        "success": True,
        "data": {
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "support_levels": [14.5],
            "resistance_levels": [16.2],
            "nearest_support": 14.5,
            "nearest_resistance": 16.2,
            "current_price": 15.0,
            "method": "kde_volume_weighted",
            "kde_ok": True,
            "kde_reason": "ok",
            "kde_lookback_used": 250,
            "kde_lookback_expanded": False,
            "description": "test",
        },
    }

    with patch("stock.stock_analysis_routes.StockAnalysisService") as Cls:
        Cls.return_value.get_key_levels_only.return_value = fake
        resp = client.get("/api/analysis/levels/600519?max_levels=8")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["nearest_support"] == 14.5
    kwargs = Cls.return_value.get_key_levels_only.call_args
    assert kwargs.args[0] == "600519"
    assert kwargs.kwargs.get("max_levels") == 8
    assert kwargs.kwargs.get("price_adjust") == "none"


def test_levels_route_accepts_name_via_query():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from stock.stock_analysis_routes import router

    app = FastAPI()
    app.include_router(router)

    def _fake_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = _fake_db
    client = TestClient(app)

    fake = {
        "success": True,
        "data": {
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "support_levels": [14.5],
            "resistance_levels": [16.2],
            "nearest_support": 14.5,
            "nearest_resistance": 16.2,
            "current_price": 15.0,
            "method": "kde_volume_weighted",
            "kde_ok": True,
            "kde_reason": "ok",
            "kde_lookback_used": 250,
            "kde_lookback_expanded": False,
            "description": "test",
        },
    }

    resolved = {
        "status": "ok",
        "code": "600519",
        "name": "贵州茅台",
        "candidates": [{"code": "600519", "name": "贵州茅台"}],
    }
    with patch("stock.stock_analysis_routes.resolve_levels_stock_identifier", return_value=resolved), patch(
        "stock.stock_analysis_routes.StockAnalysisService"
    ) as Cls:
        Cls.return_value.get_key_levels_only.return_value = fake
        resp = client.get("/api/analysis/levels?q=%E8%B4%B5%E5%B7%9E%E8%8C%85%E5%8F%B0&max_levels=8")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["stock_code"] == "600519"
    kwargs = Cls.return_value.get_key_levels_only.call_args
    assert kwargs.args[0] == "600519"
    assert kwargs.kwargs.get("max_levels") == 8
    assert kwargs.kwargs.get("price_adjust") == "none"


def test_levels_route_qfq_applies_factors():
    from datetime import date

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from stock.stock_analysis_routes import router

    app = FastAPI()
    app.include_router(router)

    def _fake_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = _fake_db
    client = TestClient(app)

    resolved = {"status": "ok", "code": "600519", "name": "贵州茅台", "candidates": []}
    bars = [
        {"date": "2024-01-02", "close": 10.0, "volume": 1, "name": "贵州茅台"},
        {"date": "2024-01-03", "close": 20.0, "volume": 1, "name": "贵州茅台"},
    ]
    ensured = {
        "factors": [(date(2024, 1, 2), 1.0), (date(2024, 1, 3), 2.0)],
        "factor_fetched": True,
        "source": "akshare_sina_qfq",
        "adj_factor_asof": "2024-01-03",
    }
    fake_result = {
        "success": True,
        "data": {
            "stock_code": "600519",
            "price_adjust": "qfq",
            "support_levels": [],
            "resistance_levels": [],
        },
    }

    with patch("stock.stock_analysis_routes.resolve_levels_stock_identifier", return_value=resolved), patch(
        "stock.stock_analysis_routes.StockAnalysisService"
    ) as Cls, patch(
        "backend_api.utils.adj_quotes.ensure_adj_factors", return_value=ensured
    ), patch(
        "utils.adj_quotes.ensure_adj_factors", return_value=ensured
    ):
        svc = Cls.return_value.__enter__.return_value
        svc._get_historical_data.return_value = bars
        svc.get_key_levels_only.return_value = fake_result
        resp = client.get("/api/analysis/levels/600519?adjust=qfq&max_levels=8")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    call_kw = svc.get_key_levels_only.call_args.kwargs
    assert call_kw.get("price_adjust") == "qfq"
    assert call_kw.get("historical_data") is not None
    assert call_kw["historical_data"][0]["close"] == pytest.approx(5.0)
    assert call_kw["adj_meta"]["factor_fetched"] is True


def test_levels_route_qfq_allows_hk():
    """港股 levels adjust=qfq：走 ensure_adj_factors + apply，不再硬拒绝。"""
    from datetime import date

    import pytest
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from stock.stock_analysis_routes import router

    app = FastAPI()
    app.include_router(router)

    def _fake_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = _fake_db
    client = TestClient(app)

    resolved = {"status": "ok", "code": "00700", "name": "腾讯", "candidates": []}
    ensured = {
        "factors": [(date(2024, 1, 2), 0.5), (date(2024, 1, 3), 1.0)],
        "factor_fetched": True,
        "source": "akshare_sina_hk_qfq",
        "adj_factor_asof": "2024-01-03",
        "factor_source": "auto",
        "from_db": False,
    }
    raw_bars = [
        {"date": "2024-01-02", "open": 10, "high": 11, "low": 9, "close": 10, "volume": 1},
        {"date": "2024-01-03", "open": 20, "high": 21, "low": 19, "close": 20, "volume": 1},
    ]

    with patch(
        "stock.stock_analysis_routes.resolve_levels_stock_identifier", return_value=resolved
    ), patch(
        "stock.stock_analysis_routes.StockAnalysisService"
    ) as Cls, patch(
        "backend_api.utils.adj_quotes.ensure_adj_factors", return_value=ensured
    ), patch(
        "utils.adj_quotes.ensure_adj_factors", return_value=ensured
    ):
        svc = Cls.return_value.__enter__.return_value
        svc._get_historical_data.return_value = raw_bars
        svc.get_key_levels_only.return_value = {
            "success": True,
            "data": {
                "nearest_support": 5.0,
                "price_adjust": "qfq",
                "adj_meta": {"source": "akshare_sina_hk_qfq"},
            },
        }
        resp = client.get("/api/analysis/levels/00700?adjust=qfq")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    call_kw = svc.get_key_levels_only.call_args.kwargs
    assert call_kw.get("price_adjust") == "qfq"
    assert call_kw.get("historical_data") is not None
    assert call_kw["historical_data"][0]["close"] == pytest.approx(5.0)
    assert call_kw["adj_meta"]["source"] == "akshare_sina_hk_qfq"


def test_levels_route_ambiguous_candidates():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from stock.stock_analysis_routes import router

    app = FastAPI()
    app.include_router(router)

    def _fake_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = _fake_db
    client = TestClient(app)

    resolved = {
        "status": "ambiguous",
        "message": "「平安」匹配到多只股票，请选择其一或输入完整名称/代码",
        "candidates": [
            {"code": "000001", "name": "平安银行"},
            {"code": "601318", "name": "中国平安"},
        ],
    }
    with patch("stock.stock_analysis_routes.resolve_levels_stock_identifier", return_value=resolved):
        resp = client.get("/api/analysis/levels/%E5%B9%B3%E5%AE%89")

    assert resp.status_code == 400
    body = resp.json()
    assert body["success"] is False
    assert len(body["candidates"]) == 2


def test_levels_route_name_not_found():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from stock.stock_analysis_routes import router

    app = FastAPI()
    app.include_router(router)

    def _fake_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = _fake_db
    client = TestClient(app)

    resolved = {
        "status": "not_found",
        "message": "未找到股票「不存在」，请检查代码或名称",
        "candidates": [],
    }
    with patch("stock.stock_analysis_routes.resolve_levels_stock_identifier", return_value=resolved):
        resp = client.get("/api/analysis/levels/%E4%B8%8D%E5%AD%98%E5%9C%A8")

    assert resp.status_code == 400
    body = resp.json()
    assert body["success"] is False
    assert "未找到" in body["message"]


def _fake_bars_with_dates(n=80, seed=7):
    from datetime import date, timedelta
    import random

    random.seed(seed)
    start = date(2025, 1, 2)
    bars = []
    for i in range(n):
        cluster = [13.0, 15.0, 17.0][i % 3]
        px = cluster + random.uniform(-0.15, 0.15)
        bars.append(
            {
                "code": "600519",
                "name": "贵州茅台",
                "date": (start + timedelta(days=i)).isoformat(),
                "close": round(px, 2),
                "high": round(px + 0.2, 2),
                "low": round(px - 0.2, 2),
                "volume": 1_000_000 + (i % 3) * 500_000,
            }
        )
    return bars


def test_vp_lookback_custom_days():
    bars = _fake_bars_with_dates()
    svc = StockAnalysisService.__new__(StockAnalysisService)
    with patch.object(svc, "_get_historical_data", return_value=bars), patch.object(
        svc, "_get_current_price", return_value=15.0
    ):
        result = svc.get_key_levels_only("600519", max_levels=8, vp_lookback=40)

    assert result["success"] is True
    vp = result["data"]["volume_profile"]
    assert vp["lookback"] == 40
    assert vp.get("bars_used") == 40


def test_vp_lookback_from_date():
    bars = _fake_bars_with_dates(n=100)
    svc = StockAnalysisService.__new__(StockAnalysisService)
    from_date = bars[-30]["date"]
    with patch.object(svc, "_get_historical_data", return_value=bars), patch.object(
        svc, "_get_current_price", return_value=15.0
    ):
        result = svc.get_key_levels_only(
            "600519", max_levels=8, vp_from_date=from_date
        )

    assert result["success"] is True
    vp = result["data"]["volume_profile"]
    assert vp.get("from_date") == from_date
    assert vp["lookback"] == 30
    assert vp.get("window_start") == from_date
