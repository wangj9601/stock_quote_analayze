import pytest
from httpx import AsyncClient
from backend_api.main import app  # 假设FastAPI主应用在这里

@pytest.mark.asyncio
async def test_get_stock_history():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.get("/api/stock/history", params={
            "code": "002539",
            "page": 1,
            "size": 10
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

@pytest.mark.asyncio
async def test_get_stock_history_with_date_filter():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.get("/api/stock/history", params={
            "code": "002539",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "page": 1,
            "size": 10
        })
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert "2024-01-01" <= item["date"] <= "2024-01-31"

@pytest.mark.asyncio
async def test_export_stock_history():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.get("/api/stock/history/export", params={
            "code": "002539",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31"
        })
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment" in resp.headers["content-disposition"] 