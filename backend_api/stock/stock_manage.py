from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
import akshare as ak
from ..database import get_db
from sqlalchemy.orm import Session
from fastapi import Depends
import traceback
import numpy as np
import time
from threading import Lock
import sqlite3
import datetime
from backend_api.config import DB_PATH

# 简单内存缓存实现,缓存120秒。
class DataFrameCache:
    def __init__(self, expire_seconds=120):
        self.data = None
        self.timestamp = 0
        self.expire = expire_seconds
        self.lock = Lock()
    def get(self):
        with self.lock:
            if self.data is not None and (time.time() - self.timestamp) < self.expire:
                return self.data
            return None
    def set(self, df):
        with self.lock:
            self.data = df
            self.timestamp = time.time()

# 创建一个全局缓存实例
stock_spot_cache = DataFrameCache(expire_seconds=60)

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
        today = datetime.date.today()
        # 如果是周六或周日，从数据库获取
        if today.weekday() in (5, 6):
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            for code in codes:
                cursor.execute(
                    "SELECT code, current_price, change_percent, volume, amount, high, low, open, pre_close FROM stock_realtime_quote WHERE code=?",
                    (code,)
                )
                row = cursor.fetchone()
                if row:
                    result.append({
                        "code": row[0],
                        "current_price": safe_float(row[1]),
                        "change_percent": safe_float(row[2]),
                        "volume": safe_float(row[3]),
                        "turnover": safe_float(row[4]),
                        "high": safe_float(row[5]),
                        "low": safe_float(row[6]),
                        "open": safe_float(row[7]),
                        "yesterday_close": safe_float(row[8]),
                    })
            conn.close()
        else:
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

# 获取股票列表
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
async def get_quote_board(limit: int = Query(10, description="返回前N个涨幅最高的股票")):
    """获取沪深京A股最新行情，返回涨幅最高的前limit个股票"""
    import datetime
    import sqlite3
    from backend_api.config import DB_PATH
    try:
        today = datetime.date.today()
        if today.weekday() in (5, 6):
            # 周末，从数据库取，联表查出name
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT q.code, b.name, q.current_price, q.change_percent, q.open, q.pre_close, q.high, q.low, q.volume, q.amount "
                "FROM stock_realtime_quote q LEFT JOIN stock_basic_info b ON q.code = b.code "
                "ORDER BY q.change_percent DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            conn.close()
            data = []
            for row in rows:
                data.append({
                    'code': row[0],
                    'name': row[1],  # 股票名称
                    'current': row[2],
                    'change_percent': row[3],
                    'open': row[4],
                    'yesterday_close': row[5],
                    'high': row[6],
                    'low': row[7],
                    'volume': row[8],
                    'turnover': row[9],
                })
            print(f"✅(DB) 成功获取 {len(data)} 条A股涨幅榜数据")
            return JSONResponse({'success': True, 'data': data})
        # 工作日，保持原有逻辑
        print(f"📈 获取A股最新行情，limit={limit}")
        df = stock_spot_cache.get()
        if df is None:
            df = ak.stock_zh_a_spot_em()
            stock_spot_cache.set(df)
        # 只保留主要字段并按涨跌幅降序排序
        df = df.sort_values(by='涨跌幅', ascending=False)
        df = df.replace({np.nan: None})
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
    
# 获取A股最新行情排行
@router.get("/quote_board_list")
def get_quote_board_list(
    ranking_type: str = Query('rise', description="排行类型: rise(涨幅榜), fall(跌幅榜), volume(成交量榜), turnover_rate(换手率榜)"),
    market: str = Query('all', description="市场类型: all(全部市场), sh(上交所), sz(深交所), bj(北交所), cy(创业板)"),
    page: int = Query(1, description="页码，从1开始"),
    page_size: int = Query(20, description="每页条数，默认20")
):
    """
    获取A股最新行情，支持多种排行类型、市场过滤和分页
    """
    try:
        print(f"📊 获取A股行情排行: type={ranking_type}, market={market}, page={page}, page_size={page_size}")
        df = stock_spot_cache.get()
        if df is None:
            df = ak.stock_zh_a_spot_em()
            stock_spot_cache.set(df)
        # 市场类型过滤
        if market != 'all':
            if market == 'sh':
                df = df[df['代码'].str.startswith('6')]
            elif market == 'sz':
                df = df[df['代码'].str.startswith('0')]
            elif market == 'cy':
                df = df[df['代码'].str.startswith('3')]
            elif market == 'bj':
                df = df[df['代码'].str.startswith('8')]
        # 排行类型排序
        if ranking_type == 'rise':
            df = df.sort_values(by='涨跌幅', ascending=False)
        elif ranking_type == 'fall':
            df = df.sort_values(by='涨跌幅', ascending=True)
        elif ranking_type == 'volume':
            df = df.sort_values(by='成交量', ascending=False)
        elif ranking_type == 'turnover_rate':
            df = df.sort_values(by='换手率', ascending=False)
        else:
            return JSONResponse({'success': False, 'message': '无效的排行类型'}, status_code=400)
        import numpy as np
        df = df.replace({np.nan: None})
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
        total = len(df)
        start = (page - 1) * page_size
        end = start + page_size
        df_page = df.iloc[start:end]
        data = []
        for _, row in df_page[actual_fields].iterrows():
            item = {}
            for k in actual_fields:
                item[field_map.get(k, k)] = row[k]
            data.append(item)
        print(f"✅ 成功获取 {len(data)} 条A股排行数据 (总数: {total})")
        return JSONResponse({'success': True, 'data': data, 'total': total, 'page': page, 'page_size': page_size})
    except Exception as e:
        print(f"❌ 获取A股排行数据失败: {str(e)}")
        tb = traceback.format_exc()
        print(tb)
        return JSONResponse({'success': False, 'message': '获取A股排行数据失败', 'error': str(e), 'traceback': tb}, status_code=500)

# 根据股票代码获取实时行情
@router.get("/realtime_quote_by_code")
async def get_realtime_quote_by_code(code: str = Query(None, description="股票代码")):
    print(f"[realtime_quote_by_code] 输入参数: code={code}")
    if not code:
        print("[realtime_quote_by_code] 缺少参数")
        return JSONResponse({"success": False, "message": "缺少股票代码参数code"}, status_code=400)
    try:
        df = ak.stock_bid_ask_em(symbol=code)
        if df.empty:
            print(f"[realtime_quote_by_code] 未找到股票代码: {code}")
            return JSONResponse({"success": False, "message": f"未找到股票代码: {code}"}, status_code=404)
        data_dict = dict(zip(df['item'], df['value']))
        def fmt(val):
            try:
                if val is None:
                    return None
                return f"{float(val):.2f}"
            except Exception:
                return None
        # 增加均价字段
        avg_price = None
        try:
            # 优先用akshare返回的均价字段
            avg_price = data_dict.get("均价") or data_dict.get("成交均价")
            if avg_price is None and data_dict.get("金额") and data_dict.get("总手") and float(data_dict.get("总手")) != 0:
                avg_price = float(data_dict.get("金额")) / float(data_dict.get("总手"))
        except Exception:
            avg_price = None
        result = {
            "code": code,
            "current_price": fmt(data_dict.get("最新")),
            "change_amount": fmt(data_dict.get("涨跌")),
            "change_percent": fmt(data_dict.get("涨幅")),
            "open": fmt(data_dict.get("今开")),
            "yesterday_close": fmt(data_dict.get("昨收")),
            "high": fmt(data_dict.get("最高")),
            "low": fmt(data_dict.get("最低")),
            "volume": fmt(data_dict.get("总手")),
            "turnover": fmt(data_dict.get("金额")),
            "turnover_rate": fmt(data_dict.get("换手")),
            "pe_dynamic": fmt(data_dict.get("市盈率-动态")),
            "average_price": fmt(avg_price),
        }
        print(f"[realtime_quote_by_code] 输出数据: {result}")
        return JSONResponse({"success": True, "data": result})
    except Exception as e:
        print(f"[realtime_quote_by_code] 异常: {e}")
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)

@router.get("/minute_data_by_code")
async def get_minute_data_by_code(code: str = Query(None, description="股票代码")):
    """
    获取指定股票代码的当日分时数据（分时线），非交易日返回最近一个交易日的分钟数据
    """
    print(f"[minute_data_by_code] 输入参数: code={code}")
    if not code:
        print(f"[minute_data_by_code] 缺少参数code")
        return JSONResponse({"success": False, "message": "缺少股票代码参数code"}, status_code=400)
    try:
        today = datetime.date.today()
        trade_dates = ak.tool_trade_date_hist_sina()['trade_date'].tolist()
        is_trading_day = today.strftime('%Y-%m-%d') in trade_dates
        print(f"[minute_data_by_code] 今日是否交易日: {is_trading_day}")
        result = []
        if is_trading_day:
            df = ak.stock_intraday_em(symbol=code)
            if df is None or df.empty:
                print(f"[minute_data_by_code] 未找到股票代码: {code}")
                return JSONResponse({"success": False, "message": f"未找到股票代码: {code}"}, status_code=404)
            for _, row in df.iterrows():
                result.append({
                    "time": row.get("时间"),
                    "price": row.get("最新价"),
                    "volume": row.get("成交量"),
                    "avg_price": row.get("均价"),
                    "amount": row.get("成交额"),
                    "change_percent": row.get("涨跌幅"),
                    "change": row.get("涨跌额"),
                })
            print(f"[minute_data_by_code] 交易日，返回{len(result)}条分时数据")
        else:
            # 非交易日，取最近一个交易日的分钟数据
            df = ak.stock_zh_a_hist_pre_min_em(symbol=code, start_time="09:00:00", end_time="15:40:00")
            if df is None or df.empty:
                print(f"[minute_data_by_code] 非交易日未找到股票代码: {code}")
                return JSONResponse({"success": False, "message": f"未找到股票代码: {code}"}, status_code=404)
            # 取最近一个交易日
            #df['日期'] = df['时间'].str[:10]
            last_date = df['时间'].max()
            #df_last = df[df['日期'] == last_date]
            for _, row in df.iterrows():
                result.append({
                    "time": row.get("时间"),
                    "price": row.get("最新价"),
                    "open": row.get("开盘"),
                    "close": row.get("收盘"),
                    "high": row.get("最高"),
                    "low": row.get("最低"),
                    #"avg_price": row.get("均价"),
                    "volume": row.get("成交量"),
                    "amount": row.get("成交额"),
                    #"change_percent": row.get("涨跌幅"),
                    #"change": row.get("涨跌额"),
                })
            print(f"[minute_data_by_code] 非交易日，返回{len(result)}条分时数据，日期: {last_date}")
        if result:
            print(f"[minute_data_by_code] 前3条数据: {result[:3]}")
        return JSONResponse({"success": True, "data": result})
    except Exception as e:
        print(f"[minute_data_by_code] 异常: {e}")
        import traceback
        print(traceback.format_exc())
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)