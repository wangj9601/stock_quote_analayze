from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
import akshare as ak
from ..database import get_db
from sqlalchemy.orm import Session
from fastapi import Depends
import traceback
import numpy as np

router = APIRouter(prefix="/api/stock", tags=["stock"])

def safe_float(value):
    try:
        if value in [None, '', '-']:
            return None
        return float(value)
    except (ValueError, TypeError):
        return None

@router.post("/quote")
async def get_stock_quote(request: Request):
    """
    批量获取股票实时行情
    前端应POST {"codes": ["000001", "600519", ...]}
    """
    try:
        data = await request.json()
        print(f"[stock_quote] 收到请求数据: {data}")
        codes = data.get("codes", [])
        if not codes:
            print("[stock_quote] 缺少股票代码")
            return JSONResponse({"success": False, "message": "缺少股票代码"}, status_code=400)
        result = []
        for code in codes:
            try:
                df = ak.stock_bid_ask_em(symbol=code)
                if df.empty:
                    continue
                data_dict = dict(zip(df['item'], df['value']))
                result.append({
                    "code": code,
                    "current_price": safe_float(data_dict.get("最新")),
                    "change_amount": safe_float(data_dict.get("涨跌")),
                    "change_percent": safe_float(data_dict.get("涨幅")),
                    "open": safe_float(data_dict.get("今开")),
                    "yesterday_close": safe_float(data_dict.get("昨收")),
                    "high": safe_float(data_dict.get("最高")),
                    "low": safe_float(data_dict.get("最低")),
                    "volume": safe_float(data_dict.get("总手")),
                    "turnover": safe_float(data_dict.get("金额")),
                })
            except Exception as e:
                print(f"[stock_quote] 获取 {code} 行情异常: {e}")
                continue
        print(f"[stock_quote] 返回数据: {result}")
        return JSONResponse({"success": True, "data": result})
    except Exception as e:
        print(f"[stock_quote] 异常: {e}")
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)

@router.get("/list")
async def get_stocks_list(request: Request, db: Session = Depends(get_db)):
    query = request.query_params.get('query', '').strip()
    limit = int(request.query_params.get('limit', 15))
    print(f"[stock_list] 收到请求: query={query}, limit={limit}")
    try:
        # SQLAlchemy 查询
        from ..models import StockBasicInfo
        q = db.query(StockBasicInfo)
        if query:
            q = q.filter(
                (StockBasicInfo.code.like(f"%{query}%")) |
                (StockBasicInfo.name.like(f"%{query}%"))
            )
        stocks = q.limit(limit).all()
        result = [{'code': s.code, 'name': s.name} for s in stocks]
        print(f"[stock_list] 返回数据: {result}")
        return JSONResponse({'success': True, 'data': result, 'total': len(result)})
    except Exception as e:
        print(f"[stock_list] 查询异常: {e}\n{traceback.format_exc()}")
        return JSONResponse({'success': False, 'message': str(e)}, status_code=500)

@router.get("/quote_board")
def get_quote_board(limit: int = Query(10, description="返回前N个涨幅最高的股票")):
    """获取沪深京A股最新行情，返回涨幅最高的前limit个股票"""
    try:
        print(f"📈 获取A股最新行情，limit={limit}")
        df = ak.stock_zh_a_spot_em()
        # 只保留主要字段并按涨跌幅降序排序
        df = df.sort_values(by='涨跌幅', ascending=False)
        # 统一将 NaN 转为 None
        df = df.replace({np.nan: None})
        # 字段映射
        field_map = {
            '代码': 'code',
            '名称': 'name',
            '最新价': 'current',
            '涨跌额': 'change',
            '涨跌幅': 'change_percent',
            '今开': 'open',
            '昨收': 'yesterday_close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume',
            '成交额': 'turnover',
            '换手率': 'turnover_rate',
            '市盈率-动态': 'pe_dynamic',
            '市净率': 'pb',
            '总市值': 'market_cap',
            '流通市值': 'circulating_market_cap',
        }
        expected_fields = list(field_map.keys())
        actual_fields = [f for f in expected_fields if f in df.columns]
        data = []
        for _, row in df[actual_fields].head(limit).iterrows():
            item = {}
            for k in actual_fields:
                item[field_map.get(k, k)] = row[k]
            data.append(item)
        print(f"✅ 成功获取 {len(data)} 条A股涨幅榜数据")
        return JSONResponse({'success': True, 'data': data})
    except Exception as e:
        print(f"❌ 获取A股涨幅榜数据失败: {str(e)}")
        tb = traceback.format_exc()
        print(tb)
        return JSONResponse({'success': False, 'message': '获取A股涨幅榜数据失败', 'error': str(e), 'traceback': tb}, status_code=500)