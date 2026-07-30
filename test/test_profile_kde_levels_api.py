"""「我的」频道支撑/压力：轻量 get_key_levels_only 与 levels 路由包装。"""

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend_api"))

from stock.stock_analysis import KeyLevels, StockAnalysisService  # noqa: E402


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
