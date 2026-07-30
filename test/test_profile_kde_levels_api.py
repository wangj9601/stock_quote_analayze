"""「我的」频道支撑/压力：轻量 get_key_levels_only 与 levels 路由包装。"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

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
    assert "description" in data
    assert data["kde_lookback_initial"] == KeyLevels.KDE_LOOKBACK_DAYS
    assert isinstance(data["support_levels"], list)
    assert isinstance(data["resistance_levels"], list)


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
    Cls.return_value.get_key_levels_only.assert_called_once_with("600519", max_levels=8)


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
    Cls.return_value.get_key_levels_only.assert_called_once_with("600519", max_levels=8)


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
