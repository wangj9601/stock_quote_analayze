import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
import pytest
from httpx import AsyncClient
from backend_api.main import app

@pytest.mark.asyncio
async def test_get_fund_flow_history_success():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.get("/api/stock_fund_flow/history", params={"code": "300223"})
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

@pytest.mark.asyncio
async def test_get_fund_flow_history_missing_code():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.get("/api/stock_fund_flow/history")
        assert resp.status_code == 400 or resp.status_code == 422

@pytest.mark.asyncio
async def test_get_fund_flow_history_with_date_filter():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.get("/api/stock_fund_flow/history", params={
            "code": "300223",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31"
        })
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert "2024-01-01" <= item["date"] <= "2024-01-31"

@pytest.mark.asyncio
async def test_get_fund_flow_history_code_not_exist():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.get("/api/stock_fund_flow/history", params={"code": "notexist"})
        assert resp.status_code in (200, 404)
        data = resp.json()
        if resp.status_code == 200:
            assert data["total"] == 0
        else:
            assert data["success"] is False

@pytest.mark.asyncio
async def test_fund_flow_history_method_not_allowed():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.post("/api/stock_fund_flow/history", json={"code": "300223"})
        assert resp.status_code == 405

# 如有导出CSV接口
@pytest.mark.asyncio
async def test_fund_flow_history_export_csv():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.get("/api/stock_fund_flow/history/export", params={"code": "300223"})
        # 允许未实现时404，已实现时应为200且Content-Type为csv
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            assert resp.headers["content-type"].startswith("text/csv") 