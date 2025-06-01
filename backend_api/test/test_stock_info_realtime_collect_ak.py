def test_get_stock_quote_on_weekend(monkeypatch):
    """测试周末从数据库获取行情数据"""
    import sqlite3
    from backend_api.config import DB_PATH
    from fastapi.testclient import TestClient
    from backend_api.stock.stock_manage import router, safe_float
    import datetime

    # 模拟今天是周六
    class FakeDate(datetime.date):
        @classmethod
        def today(cls):
            # 2024-06-15 是周六
            return cls(2024, 6, 15)
    monkeypatch.setattr(datetime, 'date', FakeDate)

    # 先从数据库取一只股票
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, current_price, change_percent, volume, amount, high, low, open, pre_close FROM stock_realtime_quote LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    assert row is not None, "数据库应有实时行情数据"
    code = row[0]

    # 用TestClient调用接口
    client = TestClient(router)
    response = client.post("/api/stock/quote", json={"codes": [code]})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["data"]) == 1
    # 校验返回内容与数据库一致
    quote = data["data"][0]
    assert quote["code"] == code
    assert safe_float(quote["current_price"]) == safe_float(row[1])
    assert safe_float(quote["change_percent"]) == safe_float(row[2])
    assert safe_float(quote["volume"]) == safe_float(row[3])
    assert safe_float(quote["turnover"]) == safe_float(row[4])
    assert safe_float(quote["high"]) == safe_float(row[5])
    assert safe_float(quote["low"]) == safe_float(row[6])
    assert safe_float(quote["open"]) == safe_float(row[7])
    assert safe_float(quote["yesterday_close"]) == safe_float(row[8])

import pytest
from httpx import AsyncClient
from backend_api.main import app

@pytest.mark.asyncio
async def test_realtime_quote_by_code_success():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.get("/api/stock/realtime_quote_by_code", params={"code": "000001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["code"] == "000001"
        assert "current_price" in data["data"]

@pytest.mark.asyncio
async def test_realtime_quote_by_code_not_found():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.get("/api/stock/realtime_quote_by_code", params={"code": "notexist"})
        assert resp.status_code == 404
        data = resp.json()
        assert data["success"] is False
        assert "未找到" in data["message"]

@pytest.mark.asyncio
async def test_realtime_quote_by_code_missing_param():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.get("/api/stock/realtime_quote_by_code")
        assert resp.status_code == 400
        data = resp.json()
        assert data["success"] is False
        assert "缺少" in data["message"]