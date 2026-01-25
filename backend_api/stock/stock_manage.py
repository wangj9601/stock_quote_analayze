from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
import akshare as ak
from backend_api.database import get_db
from sqlalchemy.orm import Session
from sqlalchemy import text, func, desc, cast, Date as SQLDate
from fastapi import Depends
import traceback
import numpy as np
import time
from threading import Lock
import datetime
import pandas as pd
import math
from backend_api.models import StockRealtimeQuote, StockBasicInfo, StockRealtimeQuoteHK, StockBasicInfoHK, HistoricalQuotes, MACDIndicators, KDJIndicators, RSIIndicators, MAIndicators, BOLLIndicators

# 简单内存缓存实现,缓存600秒。
class DataFrameCache:
    def __init__(self, expire_seconds=600):
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
stock_spot_cache = DataFrameCache(expire_seconds=600)

router = APIRouter(prefix="/api/stock", tags=["stock"])

def is_hk_stock(code: str, db: Session) -> bool:
    """
    判断股票代码是否为港股
    先查询 stock_basic_info_hk 表，如果不存在，再查询 stock_basic_info 表
    
    Args:
        code: 股票代码
        db: 数据库会话
        
    Returns:
        bool: True表示港股，False表示A股
    """
    if not code:
        return False
    
    code_str = str(code).strip()
    
    # 先查询港股表
    hk_stock = db.query(StockBasicInfoHK).filter(StockBasicInfoHK.code == code_str).first()
    if hk_stock:
        return True
    
    # 再查询A股表
    a_stock = db.query(StockBasicInfo).filter(StockBasicInfo.code == code_str).first()
    if a_stock:
        return False
    
    # 如果两个表都没有，默认返回False（A股）
    return False

def safe_float(value):
    try:
        if value in [None, '', '-']:
            return None
        return float(value)
    except (ValueError, TypeError):
        return None

def normalize_code(raw_code: str):
    if raw_code is None:
        return None
    code = str(raw_code).strip()
    if '.' in code:
        code = code.split('.')[0]
    return code

def get_cached_spot_df():
    try:
        df = stock_spot_cache.get()
        if df is None:
            df = ak.stock_zh_a_spot_em()
            if df is not None:
                stock_spot_cache.set(df)
        if df is not None and hasattr(df, 'copy'):
            return df.copy()
    except Exception as e:
        print(f"⚠️ 获取AkShare行情失败: {e}")
    return None

def prepare_spot_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    rename_map = {
        '代码': 'code',
        '名称': 'name',
        '最新价': 'current',
        '涨跌额': 'change',
        '涨跌幅': 'change_percent',
        '成交量': 'volume',
        '成交额': 'turnover',
        '换手率': 'rate',
    }
    available_cols = [col for col in rename_map.keys() if col in df.columns]
    if not available_cols:
        return pd.DataFrame()
    df_prepared = df[available_cols].rename(columns=rename_map)
    df_prepared['code'] = df_prepared['code'].apply(normalize_code)
    
    def to_float(series):
        return pd.to_numeric(series, errors='coerce')
    
    df_prepared['current'] = to_float(df_prepared.get('current'))
    df_prepared['change'] = to_float(df_prepared.get('change'))
    df_prepared['change_percent'] = pd.to_numeric(
        df_prepared.get('change_percent', '').astype(str).str.replace('%', ''), errors='coerce'
    )
    df_prepared['volume'] = to_float(df_prepared.get('volume'))
    df_prepared['turnover'] = to_float(df_prepared.get('turnover'))
    df_prepared['rate'] = pd.to_numeric(
        df_prepared.get('rate', '').astype(str).str.replace('%', ''), errors='coerce'
    )
    return df_prepared

# 获取所有股票的基本信息（代码和名称），用于前端登录后全局缓存
@router.get("/stock_basic_info_all")
async def get_stock_basic_info_all(db: Session = Depends(get_db)):
    """获取所有股票的基本信息（代码和名称），用于前端登录后全局缓存"""
    print(f"[stock_basic_info_all] 收到请求: 获取所有股票信息")
    try:
        from models import StockBasicInfo
        stocks = db.query(StockBasicInfo).all()
        result = [{'code': str(s.code), 'name': s.name} for s in stocks]
        print(f"[stock_basic_info_all] 返回数据: 共{len(result)}条股票信息")
        return JSONResponse({'success': True, 'data': result, 'total': len(result)})
    except Exception as e:
        print(f"[stock_basic_info_all] 查询异常: {e}\n{traceback.format_exc()}")
        return JSONResponse({'success': False, 'message': str(e)}, status_code=500)

# 获取股票列表（支持A股和港股）
@router.get("/list")
async def get_stocks_list(request: Request, db: Session = Depends(get_db)):
    query = request.query_params.get('query', '').strip()
    limit = int(request.query_params.get('limit', 15))
    print(f"[stock_list] 收到请求: query={query}, limit={limit}")
    try:
        from models import StockBasicInfo, StockBasicInfoHK, StockRealtimeQuoteHK
        result = []
        seen_codes = set()  # 用于去重
        
        # 1. 先查询A股基础信息表
        q_a = db.query(StockBasicInfo)
        if query:
            q_a = q_a.filter(
                (StockBasicInfo.code.like(f"%{query}%")) |
                (StockBasicInfo.name.like(f"%{query}%"))
            )
        stocks_a = q_a.limit(limit).all()
        for s in stocks_a:
            code_str = str(s.code)
            if code_str not in seen_codes:
                result.append({'code': code_str, 'name': s.name})
                seen_codes.add(code_str)
        
        # 2. 如果A股结果不足，查询港股基础信息表
        if len(result) < limit:
            remaining_limit = limit - len(result)
            try:
                q_hk = db.query(StockBasicInfoHK)
                if query:
                    q_hk = q_hk.filter(
                        (StockBasicInfoHK.code.like(f"%{query}%")) |
                        (StockBasicInfoHK.name.like(f"%{query}%"))
                    )
                stocks_hk = q_hk.limit(remaining_limit).all()
                for s in stocks_hk:
                    code_str = str(s.code)
                    if code_str not in seen_codes:
                        result.append({'code': code_str, 'name': s.name})
                        seen_codes.add(code_str)
            except Exception as e_hk:
                print(f"[stock_list] 查询港股基础信息表失败: {e_hk}")
        
        # 3. 如果结果仍不足，从港股实时行情表查询（作为后备）
        if len(result) < limit:
            remaining_limit = limit - len(result)
            try:
                # 获取最新交易日期
                latest_date = db.query(func.max(StockRealtimeQuoteHK.trade_date)).scalar()
                if latest_date:
                    q_hk_quote = db.query(StockRealtimeQuoteHK.code, StockRealtimeQuoteHK.name).filter(
                        StockRealtimeQuoteHK.trade_date == latest_date
                    )
                    if query:
                        q_hk_quote = q_hk_quote.filter(
                            (StockRealtimeQuoteHK.code.like(f"%{query}%")) |
                            (StockRealtimeQuoteHK.name.like(f"%{query}%")) |
                            (StockRealtimeQuoteHK.english_name.like(f"%{query}%"))
                        )
                    stocks_hk_quote = q_hk_quote.distinct().limit(remaining_limit).all()
                    for row in stocks_hk_quote:
                        code_str = str(row.code)
                        if code_str not in seen_codes:
                            result.append({'code': code_str, 'name': row.name or code_str})
                            seen_codes.add(code_str)
            except Exception as e_hk_quote:
                print(f"[stock_list] 查询港股实时行情表失败: {e_hk_quote}")
        
        print(f"[stock_list] 返回数据: {result}, 总数: {len(result)}")
        return JSONResponse({'success': True, 'data': result, 'total': len(result)})
    except Exception as e:
        print(f"[stock_list] 查询异常: {e}\n{traceback.format_exc()}")
        return JSONResponse({'success': False, 'message': str(e)}, status_code=500)


@router.get("/quote_board")
async def get_quote_board(limit: int = Query(10, description="返回前N个涨幅最高的股票")):
    """获取沪深京A股最新行情，返回涨幅最高的前limit个股票（始终从stock_realtime_quote表读取，不联表）"""
    try:
        # 获取最新交易日期的实时行情数据
        db = next(get_db())
        
        # 首先获取最新的交易日期
        latest_date_result = pd.read_sql_query("""
            SELECT MAX(trade_date) as latest_date 
            FROM stock_realtime_quote 
            WHERE change_percent IS NOT NULL AND change_percent != 0
        """, db.bind)
        
        if latest_date_result.empty or latest_date_result.iloc[0]['latest_date'] is None:
            db.close()
            return JSONResponse({'success': False, 'message': '暂无行情数据'}, status_code=404)
        
        latest_trade_date = latest_date_result.iloc[0]['latest_date']
        print(f"📅 首页涨幅榜使用最新交易日期: {latest_trade_date}")
        
        # 获取最新交易日期的数据
        df = pd.read_sql_query(f"""
            SELECT * FROM stock_realtime_quote 
            WHERE change_percent IS NOT NULL AND change_percent != 0 AND trade_date = '{latest_trade_date}'
            ORDER BY change_percent DESC
        """, db.bind)
        
        # 按涨幅降序排列

        # 取前limit个
        df_limit = df.head(limit)
        
        # 准备名称映射，避免名称字段为空
        name_map = {}
        if not df_limit.empty:
            code_list = [str(code) for code in df_limit['code'].tolist() if code]
            if code_list:
                name_rows = db.query(StockBasicInfo.code, StockBasicInfo.name).filter(
                    StockBasicInfo.code.in_(code_list)
                ).all()
                name_map = {str(row.code): row.name for row in name_rows if row.name}
        
        data = []
        for _, row in df_limit.iterrows():
            code = str(row['code'])
            display_name = row['name']
            if not display_name or str(display_name).lower() == 'null':
                display_name = name_map.get(code) or ''
            data.append({
                'code': code,
                'name': display_name,
                'current': row['current_price'],
                'change_percent': row['change_percent'],
                'open': row['open'],
                'pre_close': row['pre_close'],
                'high': row['high'],
                'low': row['low'],
                'volume': row['volume'],
                'turnover': row['amount'],
            })
        print(f"✅(DB) 成功获取 {len(data)} 条A股涨幅榜数据（已去重）")
        db.close()
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
    page_size: int = Query(20, description="每页条数，默认20"),
    keyword: str = Query(None, description="搜索关键词（股票代码或名称）")
):
    """
    获取A股最新行情，支持多种排行类型、市场过滤和分页 (数据源: stock_realtime_quote)
    """
    try:
        print(f"📊 获取A股行情排行 (from DB): type={ranking_type}, market={market}, page={page}, page_size={page_size}, keyword={keyword}")
        
        # 1. 获取最新交易日期的实时行情数据
        db = next(get_db())
        
        try:
            latest_date_result = pd.read_sql_query("""
                SELECT MAX(trade_date) as latest_date 
                FROM stock_realtime_quote 
                WHERE change_percent IS NOT NULL
            """, db.bind)
            
            if latest_date_result.empty or latest_date_result.iloc[0]['latest_date'] is None:
                latest_trade_date = None
                df = pd.DataFrame()
            else:
                latest_trade_date = latest_date_result.iloc[0]['latest_date']
                if latest_trade_date is not None and len(str(latest_trade_date)) > 10:
                    latest_trade_date = str(latest_trade_date)[:10]
                print(f"📅 使用最新交易日期: {latest_trade_date}")
              
                # 构建查询SQL - 使用text()包装SQL语句
                if keyword and keyword.strip():
                    keyword_clean = keyword.strip().replace("'", "''")  # 防止SQL注入
                    sql_query = text(f"""
                        SELECT * FROM stock_realtime_quote 
                        WHERE change_percent IS NOT NULL AND trade_date = '{latest_trade_date}'
                        AND (code LIKE '%{keyword_clean}%' OR name LIKE '%{keyword_clean}%')
                        ORDER BY code
                    """)
                else:
                    sql_query = text(f"""
                        SELECT * FROM stock_realtime_quote 
                        WHERE change_percent IS NOT NULL AND trade_date = '{latest_trade_date}'
                        ORDER BY code
                    """)
                
                df = pd.read_sql_query(sql_query, db.bind)
        finally:
            db.close()

        # 3. 市场类型过滤
        if market != 'all':
            if market == 'sh':
                df = df[df['code'].str.startswith('6')]
            elif market == 'sz':
                df = df[df['code'].str.startswith('0') | df['code'].str.startswith('3')] # 深市包含主板和创业板
            elif market == 'cy':
                df = df[df['code'].str.startswith('3')]
            elif market == 'bj':
                df = df[df['code'].str.startswith('8') | df['code'].str.startswith('4')] # 北交所
        
        # 4. 排行类型排序
        sort_column_map = {
            'rise': ('change_percent', False),
            'fall': ('change_percent', True),
            'volume': ('volume', False),
            'turnover_rate': ('turnover_rate', False)
        }
        
        if ranking_type in sort_column_map:
            col, ascending = sort_column_map[ranking_type]
            df = df.sort_values(by=col, ascending=ascending)
        else:
            return JSONResponse({'success': False, 'message': '无效的排行类型'}, status_code=400)

        # 5. 字段重命名和格式化
        df = df.replace({np.nan: None})
        
        # 确保数值字段的数据类型正确
        numeric_columns = ['current_price', 'change_percent', 'open', 'pre_close', 'high', 'low', 
                          'volume', 'amount', 'turnover_rate', 'pe_dynamic', 'pb_ratio', 
                          'total_market_value', 'circulating_market_value']
        
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        field_rename_map = {
            'code': 'code',
            'name': 'name',
            'current_price': 'current',
            # 'change' is not in db, can be calculated if needed
            'change_percent': 'change_percent',
            'open': 'open',
            'pre_close': 'pre_close',
            'high': 'high',
            'low': 'low',
            'volume': 'volume',
            'amount': 'turnover',
            'turnover_rate': 'rate',
            'pe_dynamic': 'pe_dynamic',
            'pb_ratio': 'pb',
            'total_market_value': 'market_cap',
            'circulating_market_value': 'circulating_market_cap'
        }
        
        if df.empty:
            df_selected = pd.DataFrame(columns=field_rename_map.values())
        else:
            df_selected = df[list(field_rename_map.keys())].rename(columns=field_rename_map)

        # Calculate 'change' if possible
        if not df_selected.empty and 'current' in df_selected.columns and 'pre_close' in df_selected.columns:
            # 确保数据类型为数值型，处理可能的字符串或None值
            current_numeric = pd.to_numeric(df_selected['current'], errors='coerce')
            pre_close_numeric = pd.to_numeric(df_selected['pre_close'], errors='coerce')
            df_selected['change'] = (current_numeric - pre_close_numeric).round(2)
        else:
            df_selected['change'] = None

        total = len(df_selected)
        fallback_used = False
        if total < page_size:
            spot_df = get_cached_spot_df()
            df_from_spot = prepare_spot_dataframe(spot_df)
            if not df_from_spot.empty:
                df_selected = df_from_spot
                total = len(df_selected)
                fallback_used = True
                print(f"⚠️ 本地行情数据不足，使用AkShare行情填充，共 {total} 条")
                
                if market != 'all':
                    if market == 'sh':
                        df_selected = df_selected[df_selected['code'].str.startswith('6')]
                    elif market == 'sz':
                        df_selected = df_selected[df_selected['code'].str.startswith('0') | df_selected['code'].str.startswith('3')]
                    elif market == 'cy':
                        df_selected = df_selected[df_selected['code'].str.startswith('3')]
                    elif market == 'bj':
                        df_selected = df_selected[df_selected['code'].str.startswith('8') | df_selected['code'].str.startswith('4')]
                
                fallback_sort_map = {
                    'rise': ('change_percent', False),
                    'fall': ('change_percent', True),
                    'volume': ('volume', False),
                    'turnover_rate': ('rate', False)
                }
                sort_col, ascending = fallback_sort_map.get(ranking_type, ('change_percent', False))
                if sort_col in df_selected.columns:
                    df_selected = df_selected.sort_values(by=sort_col, ascending=ascending)
                total = len(df_selected)

        start = (page - 1) * page_size
        end = start + page_size
        df_page = df_selected.iloc[start:end].copy()
        
        # 名称兜底（仅对本地数据）
        if not fallback_used and not df_page.empty and 'code' in df_page.columns:
            code_list = [str(code) for code in df_page['code'].tolist() if code]
            if code_list:
                db_lookup = next(get_db())
                try:
                    name_rows = db_lookup.query(StockBasicInfo.code, StockBasicInfo.name).filter(
                        StockBasicInfo.code.in_(code_list)
                    ).all()
                finally:
                    db_lookup.close()
                name_map = {str(row.code): row.name for row in name_rows if row.name}
                def resolve_name(row):
                    current_name = row.get('name')
                    if current_name and str(current_name).strip().lower() != 'null':
                        return current_name
                    return name_map.get(str(row.get('code'))) or current_name or ''
                df_page['name'] = df_page.apply(resolve_name, axis=1)
        
        data = df_page.to_dict(orient='records')
        data = clean_nan(data)
        
        print(f"✅ 成功获取 {len(data)} 条A股排行数据 (总数: {total})")
        db.close()
        return JSONResponse({'success': True, 'data': data, 'total': total, 'page': page, 'page_size': page_size})
        
    except Exception as e:
        print(f"❌ 获取A股排行数据失败: {str(e)}")
        tb = traceback.format_exc()
        print(tb)
        return JSONResponse({'success': False, 'message': '获取A股排行数据失败', 'error': str(e), 'traceback': tb}, status_code=500)

# 根据股票代码获取实时行情
@router.get("/realtime_quote_by_code")
async def get_realtime_quote_by_code(code: str = Query(None, description="股票代码"), db: Session = Depends(get_db)):
    print(f"[realtime_quote_by_code] 输入参数: code={code}")
    if not code:
        print("[realtime_quote_by_code] 缺少参数")
        return JSONResponse({"success": False, "message": "缺少股票代码参数code"}, status_code=400)
    try:
        # 先判断股票类型
        if is_hk_stock(code, db):
            print(f"[realtime_quote_by_code] 检测到港股代码: {code}，调用港股接口")
            # 导入港股接口函数
            from stock.hk_stock_manage import get_hk_realtime_quote_by_code
            # 调用港股接口
            return await get_hk_realtime_quote_by_code(code, db)
        
        # A股逻辑继续
        # 优先从数据库获取市盈率等财务指标数据
        # 获取最新交易日期
        latest_date_result = pd.read_sql_query("""
            SELECT MAX(trade_date) as latest_date 
            FROM stock_realtime_quote 
            WHERE change_percent IS NOT NULL AND change_percent != 0
        """, db.bind)
        
        db_stock_data = None
        if not latest_date_result.empty and latest_date_result.iloc[0]['latest_date'] is not None:
            latest_trade_date = latest_date_result.iloc[0]['latest_date']
            db_stock_data = db.query(StockRealtimeQuote).filter(
                StockRealtimeQuote.code == code,
                StockRealtimeQuote.trade_date == latest_trade_date
            ).first()
        
        # 获取买卖盘数据
        try:
            df_bid_ask = ak.stock_bid_ask_em(symbol=code)
            if df_bid_ask.empty:
                print(f"[realtime_quote_by_code] 未找到股票代码: {code}")
                return JSONResponse({"success": False, "message": f"未找到股票代码: {code}"}, status_code=404)
        except Exception as e:
            print(f"[realtime_quote_by_code] 获取买卖盘数据失败: {e}")
            return JSONResponse({"success": False, "message": f"获取股票数据失败: {str(e)}"}, status_code=500)
        
        # 合并数据
        bid_ask_dict = dict(zip(df_bid_ask['item'], df_bid_ask['value']))
        
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
            avg_price = bid_ask_dict.get("均价") or bid_ask_dict.get("成交均价")
            if avg_price is None and bid_ask_dict.get("金额") and bid_ask_dict.get("总手") and float(bid_ask_dict.get("总手")) != 0:
                avg_price = float(bid_ask_dict.get("金额")) / float(bid_ask_dict.get("总手"))
        except Exception:
            avg_price = None
        
              
        result = {
            "code": code,
            "current_price": fmt(bid_ask_dict.get("最新")),
            "change_amount": fmt(bid_ask_dict.get("涨跌")),
            "change_percent": fmt(bid_ask_dict.get("涨幅")),
            "open": fmt(bid_ask_dict.get("今开")),
            "pre_close": fmt(bid_ask_dict.get("昨收")),
            "high": fmt(bid_ask_dict.get("最高")),
            "low": fmt(bid_ask_dict.get("最低")),
            "volume": fmt(bid_ask_dict.get("总手")),
            "turnover": fmt(bid_ask_dict.get("金额")),
            "turnover_rate": fmt(bid_ask_dict.get("换手")),
            "pe_dynamic": None,
            "average_price": fmt(avg_price),
        }
        print(f"[realtime_quote_by_code] 输出数据: {result}")
        return JSONResponse({"success": True, "data": result})
    except Exception as e:
        print(f"[realtime_quote_by_code] 异常: {e}")
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)

# 股票类型判断接口
@router.get("/check_type")
async def check_stock_type(code: str = Query(None, description="股票代码"), db: Session = Depends(get_db)):
    """
    判断股票类型（A股或港股）
    
    Args:
        code: 股票代码
        
    Returns:
        {"success": True, "is_hk": True/False, "code": "股票代码"}
    """
    if not code:
        return JSONResponse({"success": False, "message": "缺少股票代码参数code"}, status_code=400)
    
    try:
        is_hk = is_hk_stock(code, db)
        return JSONResponse({
            "success": True,
            "is_hk": is_hk,
            "code": code
        })
    except Exception as e:
        print(f"[check_type] 异常: {e}")
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)

# 获取指定股票代码的当日分时数据（分时线），非交易日返回最近一个交易日的分钟数据
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
        trade_dates = ak.tool_trade_date_hist_sina()['trade_date'].tolist()
        trade_dates_str = [d.strftime('%Y-%m-%d') for d in trade_dates]
        print(f"[minute_data_by_code] 交易日历: {trade_dates_str[:10]} ... 共{len(trade_dates_str)}天")
        today = datetime.date.today()
        today_str = today.strftime('%Y-%m-%d')
        # 如果今天不是交易日，则取最近一个交易日的分钟数据
        if today_str not in trade_dates_str:
            today = today - datetime.timedelta(days=1)
            today_str = today.strftime('%Y-%m-%d')
        is_trading_day = today_str in trade_dates_str
        print(f"[minute_data_by_code] 今日是否交易日: {is_trading_day}")
        result = []
        if is_trading_day:
            df = ak.stock_intraday_em(symbol=code)
            if df is None or df.empty:
                print(f"[minute_data_by_code] 未找到股票代码: {code}")
                return JSONResponse({"success": False, "message": f"未找到股票代码: {code}"}, status_code=404)
            for _, row in df.iterrows():
                def fmt(val):
                    try:
                        if val is None:
                            return None
                        return round(float(val), 2)
                    except Exception:
                        return None
                result.append({
                    "time": row.get("时间"),
                    "price": fmt(row.get("成交价")),
                    "volume": row.get("手数"),
                    "amount": fmt(fmt(row.get("手数")) * fmt(row.get("成交价")) if fmt(row.get("手数")) is not None and fmt(row.get("成交价")) is not None else None),
                    "trade_type": row.get("买卖盘性质") if "买卖盘性质" in row else None,
                })
            print(f"[minute_data_by_code] 交易日，返回{len(result)}条分时数据")
        else:
            # 非交易日，取最近一个交易日的分钟数据
            df = ak.stock_zh_a_hist_pre_min_em(symbol=code, start_time="09:00:00", end_time="15:40:00")
            if df is None or df.empty:
                print(f"[minute_data_by_code] 非交易日未找到股票代码: {code}")
                return JSONResponse({"success": False, "message": f"未找到股票代码: {code}"}, status_code=404)
            # 取最近一个交易日
            for _, row in df.iterrows():
                def fmt(val):
                    try:
                        if val is None:
                            return None
                        return round(float(val), 2)
                    except Exception:
                        return None
                result.append({
                    "time": row.get("时间"),
                    "price": fmt(row.get("最新价")),
                    "open": fmt(row.get("开盘")),
                    "close": fmt(row.get("收盘")),
                    "high": fmt(row.get("最高")),
                    "low": fmt(row.get("最低")),
                    "avg_price": fmt((row.get("成交额") / (row.get("成交量") * 100)) if row.get("成交量") else None),
                    "volume": row.get("成交量"),
                    "amount": fmt(row.get("成交额")),
                })
            print(f"[minute_data_by_code] 非交易日，返回{len(result)}条分时数据")
        if result:
            print(f"[minute_data_by_code] 前3条数据: {result[:3]}")
        return JSONResponse({"success": True, "data": result})
    except Exception as e:
        print(f"[minute_data_by_code] 异常: {e}")
        import traceback
        print(traceback.format_exc())
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)

@router.get("/kline_hist")
async def get_kline_hist(
    code: str = Query(None, description="股票代码"),
    period: str = Query("daily", description="周期，如daily/weekly/monthly/quarterly/semiannual/annual"),
    start_date: str = Query(None, description="开始日期，YYYY-MM-DD"),
    end_date: str = Query(None, description="结束日期，YYYY-MM-DD"),
    adjust: str = Query("qfq", description="复权类型，如qfq"),
    indicator: str = Query(None, description="指标类型，如vol/macd/kdj/rsi，默认返回vol"),
    db: Session = Depends(get_db)
):
    """
    获取A股K线历史数据
    修改后：从数据库历史行情表获取除当天外的数据，当天数据从实时行情表获取
    """
    print(f"[kline_hist] 输入参数: code={code}, period={period}, start_date={start_date}, end_date={end_date}, adjust={adjust}, indicator={indicator}")
    if not code or not start_date or not end_date:
        print(f"[kline_hist] 缺少参数")
        return JSONResponse({"success": False, "message": "缺少参数"}, status_code=400)
    
    try:
        from datetime import datetime, date
        today = datetime.now().strftime('%Y-%m-%d')
        today_date = datetime.now().date()
        
        # 将start_date和end_date转换为date类型，确保类型一致
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            start_date_obj = start_date
            end_date_obj = end_date
        
        def fmt(val):
            try:
                if val is None:
                    return None
                return round(float(val), 2)
            except Exception:
                return None
        
        # 如果是日线，直接从数据库查询并合并
        if period == "daily":
            result = []
            
            # 1. 查询历史数据（除当天外）
            # 注意：数据库中的date字段可能是TEXT类型，需要使用cast转换
            # 使用PostgreSQL的::date语法进行类型转换
            historical_query = db.query(HistoricalQuotes).filter(
                HistoricalQuotes.code == code,
                func.cast(HistoricalQuotes.date, SQLDate) >= start_date_obj,
                func.cast(HistoricalQuotes.date, SQLDate) < today_date
            ).order_by(func.cast(HistoricalQuotes.date, SQLDate).asc())
            
            historical_quotes = historical_query.all()
            
            # 转换历史数据
            for quote in historical_quotes:
                date_str = quote.date.strftime('%Y-%m-%d') if hasattr(quote.date, 'strftime') else str(quote.date)
                result.append({
                    "date": date_str,
                    "code": code,
                    "open": fmt(quote.open),
                    "close": fmt(quote.close),
                    "high": fmt(quote.high),
                    "low": fmt(quote.low),
                    "volume": int(quote.volume) if quote.volume is not None else None,
                    "amount": fmt(quote.amount),
                    "amplitude": fmt(quote.amplitude),
                    "pct_chg": fmt(quote.change_percent),
                    "change": fmt(quote.change),
                    "turnover": fmt(quote.turnover_rate),
                })
            
            # 2. 查询当天实时数据
            today_realtime = db.query(StockRealtimeQuote).filter(
                StockRealtimeQuote.code == code,
                StockRealtimeQuote.trade_date == today
            ).first()
            
            if today_realtime:
                result.append({
                    "date": today,
                    "code": code,
                    "open": fmt(today_realtime.open),
                    "close": fmt(today_realtime.current_price),  # 实时行情中current_price相当于收盘价
                    "high": fmt(today_realtime.high),
                    "low": fmt(today_realtime.low),
                    "volume": int(today_realtime.volume) if today_realtime.volume is not None else None,
                    "amount": fmt(today_realtime.amount),
                    "amplitude": None,  # 实时数据可能没有振幅
                    "pct_chg": fmt(today_realtime.change_percent),
                    "change": None,  # 实时数据可能没有涨跌额
                    "turnover": fmt(today_realtime.turnover_rate),
                })
            
            # 按日期排序（确保日期格式统一后排序）
            result.sort(key=lambda x: datetime.strptime(x['date'], '%Y-%m-%d') if isinstance(x['date'], str) and len(x['date']) == 10 else datetime.min)
            
            # 根据indicator参数决定查询哪些指标数据
            # 默认返回vol（成交量），vol总是返回
            # 如果指定了indicator（macd/kdj/rsi/boll），则返回对应的指标数据
            indicator_list = indicator.split(',') if indicator else []
            
            # 查询MACD数据
            if 'macd' in indicator_list:
                try:
                    macd_query = db.query(MACDIndicators).filter(
                        MACDIndicators.code == code,
                        MACDIndicators.market_type == 'CN',
                        MACDIndicators.date >= start_date,
                        MACDIndicators.date <= end_date
                    ).order_by(MACDIndicators.date.asc())
                    
                    macd_records = macd_query.all()
                    macd_dict = {}
                    for record in macd_records:
                        date_str = record.date.strftime('%Y-%m-%d') if hasattr(record.date, 'strftime') else str(record.date)
                        macd_dict[date_str] = {
                            "dif": round(float(record.dif), 4) if record.dif is not None else None,
                            "dea": round(float(record.dea), 4) if record.dea is not None else None,
                            "macd": round(float(record.macd), 4) if record.macd is not None else None
                        }
                    
                    # 将MACD数据合并到K线数据中
                    for item in result:
                        if item['date'] in macd_dict:
                            item.update(macd_dict[item['date']])
                except Exception as e:
                    print(f"[kline_hist] MACD数据查询失败: {e}")
            
            # 查询KDJ数据
            if 'kdj' in indicator_list:
                try:
                    kdj_query = db.query(KDJIndicators).filter(
                        KDJIndicators.code == code,
                        KDJIndicators.market_type == 'CN',
                        KDJIndicators.date >= start_date,
                        KDJIndicators.date <= end_date
                    ).order_by(KDJIndicators.date.asc())
                    
                    kdj_records = kdj_query.all()
                    kdj_dict = {}
                    for record in kdj_records:
                        date_str = record.date.strftime('%Y-%m-%d') if hasattr(record.date, 'strftime') else str(record.date)
                        kdj_dict[date_str] = {
                            "k": round(float(record.k), 4) if record.k is not None else None,
                            "d": round(float(record.d), 4) if record.d is not None else None,
                            "j": round(float(record.j), 4) if record.j is not None else None
                        }
                    
                    # 将KDJ数据合并到K线数据中
                    for item in result:
                        if item['date'] in kdj_dict:
                            item.update(kdj_dict[item['date']])
                except Exception as e:
                    print(f"[kline_hist] KDJ数据查询失败: {e}")

            # 查询RSI数据
            if 'rsi' in indicator_list:
                try:
                    rsi_query = db.query(RSIIndicators).filter(
                        RSIIndicators.code == code,
                        RSIIndicators.market_type == 'CN',
                        RSIIndicators.date >= start_date,
                        RSIIndicators.date <= end_date
                    ).order_by(RSIIndicators.date.asc())
                    
                    rsi_records = rsi_query.all()
                    rsi_dict = {}
                    for record in rsi_records:
                        date_str = record.date.strftime('%Y-%m-%d') if hasattr(record.date, 'strftime') else str(record.date)
                        rsi_dict[date_str] = {
                            "rsi6": round(float(record.rsi6), 4) if record.rsi6 is not None else None,
                            "rsi12": round(float(record.rsi12), 4) if record.rsi12 is not None else None,
                            "rsi24": round(float(record.rsi24), 4) if record.rsi24 is not None else None
                        }
                    
                    # 将RSI数据合并到K线数据中
                    for item in result:
                        if item['date'] in rsi_dict:
                            item.update(rsi_dict[item['date']])
                except Exception as e:
                    print(f"[kline_hist] RSI数据查询失败: {e}")
            
            # 查询BOLL数据
            if 'boll' in indicator_list:
                try:
                    boll_query = db.query(BOLLIndicators).filter(
                        BOLLIndicators.code == code,
                        BOLLIndicators.market_type == 'CN',
                        BOLLIndicators.date >= start_date,
                        BOLLIndicators.date <= end_date
                    ).order_by(BOLLIndicators.date.asc())
                    
                    boll_records = boll_query.all()
                    boll_dict = {}
                    for record in boll_records:
                        # 兼容字符串和日期类型
                        date_str = record.date
                        if hasattr(date_str, 'strftime'):
                            date_str = date_str.strftime('%Y-%m-%d')
                        
                        boll_dict[date_str] = {
                            "boll_mid": round(float(record.mid), 4) if record.mid is not None else None,
                            "boll_upper": round(float(record.upper), 4) if record.upper is not None else None,
                            "boll_lower": round(float(record.lower), 4) if record.lower is not None else None
                        }
                    
                    # 将BOLL数据合并到K线数据中
                    for item in result:
                        if item['date'] in boll_dict:
                            item.update(boll_dict[item['date']])
                except Exception as e:
                    print(f"[kline_hist] BOLL数据查询失败: {e}")
            
            # 查询MA数据（MA总是返回，因为它是K线图的基础指标）
            try:
                ma_query = db.query(MAIndicators).filter(
                    MAIndicators.code == code,
                    MAIndicators.market_type == 'A股',
                    MAIndicators.date >= start_date,
                    MAIndicators.date <= end_date
                ).order_by(MAIndicators.date.asc())
                
                ma_records = ma_query.all()
                ma_dict = {}
                for record in ma_records:
                    date_str = record.date.strftime('%Y-%m-%d') if hasattr(record.date, 'strftime') else str(record.date)
                    ma_dict[date_str] = {
                        "ma5": round(float(record.ma5), 4) if record.ma5 is not None else None,
                        "ma10": round(float(record.ma10), 4) if record.ma10 is not None else None,
                        "ma20": round(float(record.ma20), 4) if record.ma20 is not None else None,
                        "ma30": round(float(record.ma30), 4) if record.ma30 is not None else None,
                        "ma60": round(float(record.ma60), 4) if record.ma60 is not None else None,
                        "ma120": round(float(record.ma120), 4) if record.ma120 is not None else None,
                        "ma200": round(float(record.ma200), 4) if record.ma200 is not None else None
                    }
                
                # 将MA数据合并到K线数据中
                for item in result:
                    if item['date'] in ma_dict:
                        item.update(ma_dict[item['date']])
            except Exception as e:
                print(f"[kline_hist] MA数据查询失败: {e}")
            
            # 如果没有指定indicator或indicator为vol，只返回基础K线数据和成交量（已经在result中）
            
            print(f"[kline_hist] 返回{len(result)}条日线数据（历史{len(historical_quotes)}条，当天{1 if today_realtime else 0}条）")
            return JSONResponse({"success": True, "data": result})
        
        # 其他周期：优先从周期表查询，如果没有则从日线数据实时聚合
        else:
            # 周期表映射
            period_table_map = {
                'weekly': 'weekly_quotes',
                'monthly': 'monthly_quotes',
                'quarterly': 'quarterly_quotes',
                'semiannual': 'semiannual_quotes',
                'annual': 'annual_quotes'
            }
            
            table_name = period_table_map.get(period)
            result = []
            
            # 尝试从周期表查询
            if table_name:
                try:
                    period_query = db.execute(text(f"""
                        SELECT code, date, open, close, high, low, volume, amount, 
                               change_percent, change, amplitude, turnover_rate
                        FROM {table_name}
                        WHERE code = :code AND date >= :start_date AND date <= :end_date
                        ORDER BY date ASC
                    """), {
                        "code": code,
                        "start_date": start_date,
                        "end_date": end_date
                    })
                    period_rows = period_query.fetchall()
                    
                    if period_rows:
                        for row in period_rows:
                            date_str = row[1].strftime('%Y-%m-%d') if hasattr(row[1], 'strftime') else str(row[1])
                            result.append({
                                "date": date_str,
                                "code": row[0],
                                "open": fmt(row[2]),
                                "close": fmt(row[3]),
                                "high": fmt(row[4]),
                                "low": fmt(row[5]),
                                "volume": int(row[6]) if row[6] is not None else None,
                                "amount": fmt(row[7]),
                                "amplitude": fmt(row[9]),
                                "pct_chg": fmt(row[8]),
                                "change": fmt(row[9]),
                                "turnover": fmt(row[10]),
                            })
                        print(f"[kline_hist] 从周期表{table_name}返回{len(result)}条数据")
                        return JSONResponse({"success": True, "data": result})
                except Exception as e:
                    print(f"[kline_hist] 从周期表{table_name}查询失败，将使用实时聚合: {e}")
            
            # Fallback: 从日线数据实时聚合
            print(f"[kline_hist] 从日线数据实时聚合{period}周期数据")
            
            # 获取日线数据（包括当天）
            # 注意：数据库中的date字段可能是TEXT类型，需要使用cast转换
            # 使用PostgreSQL的::date语法进行类型转换
            daily_query = db.query(HistoricalQuotes).filter(
                HistoricalQuotes.code == code,
                func.cast(HistoricalQuotes.date, SQLDate) >= start_date_obj,
                func.cast(HistoricalQuotes.date, SQLDate) < today_date
            ).order_by(func.cast(HistoricalQuotes.date, SQLDate).asc())
            
            daily_quotes = daily_query.all()
            
            # 获取当天实时数据
            today_realtime = db.query(StockRealtimeQuote).filter(
                StockRealtimeQuote.code == code,
                StockRealtimeQuote.trade_date == today
            ).first()
            
            # 构建DataFrame
            daily_data = []
            for quote in daily_quotes:
                date_str = quote.date.strftime('%Y-%m-%d') if hasattr(quote.date, 'strftime') else str(quote.date)
                daily_data.append({
                    'date': date_str,
                    'open': quote.open,
                    'close': quote.close,
                    'high': quote.high,
                    'low': quote.low,
                    'volume': quote.volume or 0,
                    'amount': quote.amount or 0,
                })
            
            if today_realtime:
                daily_data.append({
                    'date': today,
                    'open': today_realtime.open or 0,
                    'close': today_realtime.current_price or 0,
                    'high': today_realtime.high or 0,
                    'low': today_realtime.low or 0,
                    'volume': today_realtime.volume or 0,
                    'amount': today_realtime.amount or 0,
                })
            
            if not daily_data:
                print(f"[kline_hist] 没有日线数据可供聚合")
                return JSONResponse({"success": True, "data": []})
            
            # 使用pandas进行聚合
            df = pd.DataFrame(daily_data)
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            
            # 根据周期进行聚合
            if period == 'weekly':
                resampled = df.resample('W-FRI').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum',
                    'amount': 'sum'
                })
            elif period == 'monthly':
                resampled = df.resample('M').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum',
                    'amount': 'sum'
                })
            elif period == 'quarterly':
                resampled = df.resample('Q').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum',
                    'amount': 'sum'
                })
            elif period == 'semiannual':
                # 半年线：每年6月30日和12月31日
                resampled = df.resample('6M', label='right', closed='right').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum',
                    'amount': 'sum'
                })
            elif period == 'annual':
                resampled = df.resample('A').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum',
                    'amount': 'sum'
                })
            else:
                return JSONResponse({"success": False, "message": f"不支持的周期类型: {period}"}, status_code=400)
            
            # 转换结果
            for idx, row in resampled.iterrows():
                date_str = idx.strftime('%Y-%m-%d')
                result.append({
                    "date": date_str,
                    "code": code,
                    "open": fmt(row['open']),
                    "close": fmt(row['close']),
                    "high": fmt(row['high']),
                    "low": fmt(row['low']),
                    "volume": int(row['volume']) if pd.notna(row['volume']) else None,
                    "amount": fmt(row['amount']),
                    "amplitude": None,
                    "pct_chg": None,
                    "change": None,
                    "turnover": None,
                })
            
            print(f"[kline_hist] 实时聚合返回{len(result)}条{period}周期数据")
            return JSONResponse({"success": True, "data": result})
            
    except Exception as e:
        print(f"[kline_hist] 异常: {e}")
        import traceback
        print(traceback.format_exc())
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)

# 获取A股分钟K线历史数据
@router.get("/kline_min_hist")
async def get_kline_min_hist(
    code: str = Query(None, description="股票代码"),
    period: str = Query("60", description="周期，分钟K，如1、5、15、30、60"),
    start_datetime: str = Query(None, description="开始时间，YYYY-MM-DD HH:MM:SS"),
    end_datetime: str = Query(None, description="结束时间，YYYY-MM-DD HH:MM:SS"),
    adjust: str = Query("qfq", description="复权类型，如qfq")
):
    """
    获取A股分钟K线（如1小时线）历史数据
    """
    print(f"[kline_min_hist] 输入参数: code={code}, period={period}, start_datetime={start_datetime}, end_datetime={end_datetime}, adjust={adjust}")
    if not code or not start_datetime or not end_datetime:
        print(f"[kline_min_hist] 缺少参数")
        return JSONResponse({"success": False, "message": "缺少参数"}, status_code=400)
    try:
        # 日期格式化
        start_dt_fmt = start_datetime.replace('-', '').replace(':', '').replace(' ', '') if start_datetime else None
        end_dt_fmt = end_datetime.replace('-', '').replace(':', '').replace(' ', '') if end_datetime else None
        # 1分钟线不支持复权，adjust传空
        ak_adjust = '' if period == '1' else adjust
        print(f"[kline_min_hist] 调用ak，symbol={code}, period={period}, start={start_dt_fmt}, end={end_dt_fmt}, adjust={ak_adjust}")
        df = ak.stock_zh_a_hist_min_em(symbol=code, period=period, start_date=start_dt_fmt, end_date=end_dt_fmt, adjust=ak_adjust)
        if df is None or df.empty:
            print(f"[kline_min_hist] 未找到股票代码: {code}")
            return JSONResponse({"success": False, "message": f"未找到股票代码: {code}"}, status_code=404)
        result = []
        def fmt(val):
            try:
                if val is None:
                    return None
                return round(float(val), 2)
            except Exception:
                return None
        for _, row in df.iterrows():
            date_val = row.get("时间")
            if hasattr(date_val, 'strftime'):
                date_val = date_val.strftime('%Y-%m-%d %H:%M:%S')
            result.append({
                "date": date_val,
                "code": code,
                "open": fmt(row.get("开盘")),
                "close": fmt(row.get("收盘")),
                "high": fmt(row.get("最高")),
                "low": fmt(row.get("最低")),
                "volume": int(row.get("成交量")) if row.get("成交量") is not None else None,
                "amount": fmt(row.get("成交额")),
                "amplitude": fmt(row.get("振幅")),
                "pct_chg": fmt(row.get("涨跌幅")),
                "change": fmt(row.get("涨跌额")),
                "turnover": fmt(row.get("换手率")),
            })
        print(f"[kline_min_hist] 返回{len(result)}条分钟K线数据，前3条: {result[:3]}")
        return JSONResponse({"success": True, "data": result})
    except Exception as e:
        print(f"[kline_min_hist] 异常: {e}")
        import traceback
        print(traceback.format_exc())
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)

@router.get("/macd")
async def get_macd(
    code: str = Query(None, description="股票代码"),
    start_date: str = Query(None, description="开始日期，YYYY-MM-DD"),
    end_date: str = Query(None, description="结束日期，YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    """
    获取A股MACD指标数据
    """
    print(f"[macd] 输入参数: code={code}, start_date={start_date}, end_date={end_date}")
    if not code or not start_date or not end_date:
        return JSONResponse({"success": False, "message": "缺少参数"}, status_code=400)
    
    try:
        # 查询MACD数据
        macd_query = db.query(MACDIndicators).filter(
            MACDIndicators.code == code,
            MACDIndicators.market_type == 'CN',
            MACDIndicators.date >= start_date,
            MACDIndicators.date <= end_date
        ).order_by(MACDIndicators.date.asc())
        
        macd_records = macd_query.all()
        
        result = []
        for record in macd_records:
            date_str = record.date.strftime('%Y-%m-%d') if hasattr(record.date, 'strftime') else str(record.date)
            result.append({
                "date": date_str,
                "code": record.code,
                "dif": round(float(record.dif), 4) if record.dif is not None else None,
                "dea": round(float(record.dea), 4) if record.dea is not None else None,
                "macd": round(float(record.macd), 4) if record.macd is not None else None,
                "ema12": round(float(record.ema12), 4) if record.ema12 is not None else None,
                "ema26": round(float(record.ema26), 4) if record.ema26 is not None else None
            })
        
        print(f"[macd] 返回 {len(result)} 条MACD数据")
        return JSONResponse({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        print(f"[macd] 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)

@router.get("/ma")
async def get_ma(
    code: str = Query(None, description="股票代码"),
    start_date: str = Query(None, description="开始日期，YYYY-MM-DD"),
    end_date: str = Query(None, description="结束日期，YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    """
    获取A股MA指标数据
    """
    print(f"[ma] 输入参数: code={code}, start_date={start_date}, end_date={end_date}")
    if not code or not start_date or not end_date:
        return JSONResponse({"success": False, "message": "缺少参数"}, status_code=400)
    
    try:
        # 查询MA数据
        ma_query = db.query(MAIndicators).filter(
            MAIndicators.code == code,
            MAIndicators.market_type == 'A股',
            MAIndicators.date >= start_date,
            MAIndicators.date <= end_date
        ).order_by(MAIndicators.date.asc())
        
        ma_records = ma_query.all()
        
        result = []
        for record in ma_records:
            date_str = record.date.strftime('%Y-%m-%d') if hasattr(record.date, 'strftime') else str(record.date)
            result.append({
                "date": date_str,
                "code": record.code,
                "ma5": round(float(record.ma5), 4) if record.ma5 is not None else None,
                "ma10": round(float(record.ma10), 4) if record.ma10 is not None else None,
                "ma20": round(float(record.ma20), 4) if record.ma20 is not None else None,
                "ma30": round(float(record.ma30), 4) if record.ma30 is not None else None,
                "ma60": round(float(record.ma60), 4) if record.ma60 is not None else None,
                "ma120": round(float(record.ma120), 4) if record.ma120 is not None else None,
                "ma200": round(float(record.ma200), 4) if record.ma200 is not None else None
            })
        
        print(f"[ma] 返回 {len(result)} 条MA数据")
        return JSONResponse({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        print(f"[ma] 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)
    
@router.get("/latest_financial")
async def get_latest_financial(code: str = Query(..., description="股票代码"), db: Session = Depends(get_db)):
    """
    获取指定股票代码的最新报告期主要财务指标（支持A股和港股）
    """
    try:
        print(f"[latest_financial] 请求参数: code={code}")
        import pandas as pd
        
        # 判断是否为港股
        is_hk = is_hk_stock(code, db)
        print(f"[latest_financial] 股票类型: {'港股' if is_hk else 'A股'}")
        
        if is_hk:
            # 港股：使用 stock_hk_financial_indicator_em 接口
            try:
                df = ak.stock_hk_financial_indicator_em(symbol=code)
            except Exception as e:
                print(f"[latest_financial] 港股调用akshare接口失败: {e}")
                import traceback
                traceback.print_exc()
                return JSONResponse({"success": False, "message": f"获取港股财务数据失败: {str(e)}"}, status_code=500)
            
            print(f"[latest_financial] 港股获取到原始数据: {df.shape if df is not None else None}")
            if df is None or df.empty:
                print(f"[latest_financial] 港股未获取到财务数据")
                return JSONResponse({"success": False, "message": "未获取到财务数据"}, status_code=404)
            
            if len(df) == 0:
                print(f"[latest_financial] 港股DataFrame为空")
                return JSONResponse({"success": False, "message": "未获取到财务数据"}, status_code=404)
            
            print(f"[latest_financial] 港股DataFrame columns: {df.columns.tolist()}")
            
            # 港股数据格式：单行多列，每个指标是一列
            # 取第一行数据
            try:
                row_data = df.iloc[0]
            except (IndexError, KeyError) as e:
                print(f"[latest_financial] 港股获取行数据失败: {e}")
                return JSONResponse({"success": False, "message": "未获取到财务数据"}, status_code=404)
            
            # 港股指标映射（列名 -> 结果key）
            hk_indicator_map = {
                "pe": ["市盈率"],
                "pb": ["市净率"],
                "roe": ["股东权益回报率(%)"],
                "roa": ["总资产回报率(%)"],
                "revenue": ["营业总收入"],
                "profit": ["净利润"],
                "eps": ["基本每股收益(元)"],
                "bps": ["每股净资产(元)"]
            }
            
            result = {
                "report_date": None  # 港股接口不返回报告期
            }
            
            for key, possible_cols in hk_indicator_map.items():
                value = None
                for col_name in possible_cols:
                    try:
                        if col_name not in df.columns:
                            continue
                        # 使用安全的访问方式
                        val = row_data[col_name] if col_name in row_data.index else None
                        if val is None:
                            continue
                        # 处理百分比字段（如ROE、ROA），去掉%号并转换为数值
                        if isinstance(val, str) and '%' in val:
                            val = val.replace('%', '').strip()
                        # 检查是否为NaN或空值
                        if pd.isna(val) or (isinstance(val, str) and val.strip() == ''):
                            continue
                        try:
                            value = float(val)
                            print(f"[latest_financial] 港股指标 {key} 匹配到列: {col_name}，值: {value}")
                            break
                        except (ValueError, TypeError) as e:
                            print(f"[latest_financial] 港股指标 {key} 列 {col_name} 值转换失败: {val}, 错误: {e}")
                            continue
                    except Exception as e:
                        print(f"[latest_financial] 港股指标 {key} 处理列 {col_name} 时出错: {e}")
                        import traceback
                        traceback.print_exc()
                        continue
                if value is None:
                    print(f"[latest_financial] 港股指标 {key} 未匹配到任何列")
                result[key] = value
            
            print(f"[latest_financial] 港股返回结果: {result}")
            result = clean_nan(result)
            return JSONResponse({"success": True, "data": result})
        else:
            # A股：使用 stock_financial_abstract 接口（原有逻辑）
            df = ak.stock_financial_abstract(symbol=code)
            print(f"[latest_financial] A股获取到原始数据: {df.shape if df is not None else None}")
            if df is None or df.empty:
                print(f"[latest_financial] A股未获取到财务数据")
                return JSONResponse({"success": False, "message": "未获取到财务数据"}, status_code=404)
            print(f"[latest_financial] A股DataFrame columns: {df.columns.tolist()}")

            # 自动查找行名列
            row_name_col = None
            for possible in ['指标', '选项', '名称']:
                if possible in df.columns:
                    row_name_col = possible
                    break
            if row_name_col is None:
                print(f"[latest_financial] A股未找到指标行名列，所有列为: {df.columns.tolist()}")
                return JSONResponse({"success": False, "message": "未找到指标行名列"}, status_code=500)

            # 找到所有报告期列（一般为数字开头的列）
            period_cols = [col for col in df.columns if str(col).isdigit()]
            if not period_cols:
                # 也可能是 '2024-03-31' 这种格式
                period_cols = [col for col in df.columns if str(col).startswith('20')]
            if not period_cols:
                print(f"[latest_financial] A股未找到报告期列，所有列为: {df.columns.tolist()}")
                return JSONResponse({"success": False, "message": "未找到报告期列"}, status_code=500)
            # 取最新报告期
            period_cols_sorted = sorted(period_cols, reverse=True)
            latest_date = period_cols_sorted[0]
            print(f"[latest_financial] A股最新报告期: {latest_date}")
     
            # A股指标映射
            indicator_map = {
                "pe": ["市盈率", "市盈率-TTM", "市盈率(动)"],
                "pb": ["市净率"],
                "roe": ["净资产收益率", "净资产收益率(加权)", "净资产收益率(ROE)"],
                "roa": ["资产收益率", "资产收益率(ROA)", "总资产报酬率(ROA)"],
                "revenue": ["营业总收入", "营业收入"],
                "profit": ["归母净利润", "净利润"],
                "eps": ["每股收益", "基本每股收益", "每股收益(EPS)"],
                "bps": ["每股净资产", "每股净资产(BPS)"]
            }

            result = {
                "report_date": latest_date
            }
            for key, possible_names in indicator_map.items():
                value = None
                for name in possible_names:
                    row = df[df[row_name_col] == name]
                    if not row.empty:
                        value = row[latest_date].values[0] if latest_date in row else row.iloc[0, -1]
                        print(f"[latest_financial] A股指标 {key} 匹配到: {name}，值: {value}")
                        break
                if value is None:
                    print(f"[latest_financial] A股指标 {key} 未匹配到任何行")
                result[key] = value

            print(f"[latest_financial] A股返回结果: {result}")
            result = clean_nan(result)
            return JSONResponse({"success": True, "data": result})
    except Exception as e:
        import traceback
        print(f"[latest_financial] 异常: {e}")
        print(traceback.format_exc())
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)

@router.get("/financial_indicator_list")
async def get_financial_indicator_list(
    symbol: str = Query(..., description="股票代码"),
    indicator: str = Query("按报告期", description="指标报告类型"),
    db: Session = Depends(get_db)
):
    """
    获取指定股票代码和指标类型的主要财务指标列表（返回所有报告期）
    支持A股和港股
    """
    try:
        print(f"[financial_indicator_list] symbol={symbol}, indicator={indicator}")
        
        # 判断是否为港股
        is_hk = is_hk_stock(symbol, db)
        print(f"[financial_indicator_list] 股票类型: {'港股' if is_hk else 'A股'}")
        
        if is_hk:
            # 港股：使用 stock_hk_financial_indicator_em 接口
            # 注意：该接口只返回最新报告期的单行数据，没有历史数据
            try:
                df = ak.stock_hk_financial_indicator_em(symbol=symbol)
            except Exception as e:
                print(f"[financial_indicator_list] 港股调用akshare接口失败: {e}")
                import traceback
                traceback.print_exc()
                return JSONResponse({"success": False, "message": f"获取港股财务数据失败: {str(e)}"}, status_code=500)
            
            print(f"[financial_indicator_list] 港股获取到原始数据: {df.shape if df is not None else None}")
            if df is None or df.empty:
                return JSONResponse({"success": False, "message": "未获取到财务数据"}, status_code=404)
            
            if len(df) == 0:
                print(f"[financial_indicator_list] 港股DataFrame为空")
                return JSONResponse({"success": False, "message": "未获取到财务数据"}, status_code=404)
            
            # 港股数据格式：单行多列，需要转换为与A股一致的格式
            try:
                row_data = df.iloc[0]
            except (IndexError, KeyError) as e:
                print(f"[financial_indicator_list] 港股获取行数据失败: {e}")
                return JSONResponse({"success": False, "message": "未获取到财务数据"}, status_code=404)
            
            # 港股指标映射（列名 -> 结果字段名）
            hk_indicator_map = {
                "净资产收益率": "股东权益回报率(%)",
                "资产收益率": "总资产回报率(%)",
                "营业总收入": "营业总收入",
                "净利润": "净利润",
                "基本每股收益": "基本每股收益(元)",
                "每股净资产": "每股净资产(元)"
            }
            
            # 构建返回数据（港股只有一条记录，没有报告期）
            result_data = {}
            for result_key, col_name in hk_indicator_map.items():
                try:
                    if col_name not in df.columns:
                        print(f"[financial_indicator_list] 港股指标 {result_key} 列 {col_name} 不存在")
                        result_data[result_key] = None
                        continue
                    # 使用安全的访问方式
                    val = row_data[col_name] if col_name in row_data.index else None
                    if val is None:
                        result_data[result_key] = None
                        continue
                    # 处理百分比字段
                    if isinstance(val, str) and '%' in val:
                        val = val.replace('%', '').strip()
                    # 检查是否为NaN或空值
                    if pd.isna(val) or (isinstance(val, str) and val.strip() == ''):
                        result_data[result_key] = None
                        continue
                    try:
                        result_data[result_key] = float(val)
                    except (ValueError, TypeError) as e:
                        print(f"[financial_indicator_list] 港股指标 {result_key} 列 {col_name} 值转换失败: {val}, 错误: {e}")
                        result_data[result_key] = None
                except Exception as e:
                    print(f"[financial_indicator_list] 港股指标 {result_key} 处理列 {col_name} 时出错: {e}")
                    import traceback
                    traceback.print_exc()
                    result_data[result_key] = None
            
            # 港股没有报告期，使用当前日期作为报告期
            result_data["报告期"] = datetime.datetime.now().strftime("%Y-%m-%d")
            
            # 返回单条记录列表（保持与A股接口格式一致）
            data = [clean_nan(result_data)]
            return JSONResponse({"success": True, "data": data})
        else:
            # A股：使用 stock_financial_abstract_ths 接口（原有逻辑）
            if indicator == "1":
                indicator = "按报告期"
            elif indicator == "2":
                indicator = "按年度"
            elif indicator == "3":
                indicator = "按单季度"
            else:
                indicator = "按报告期"
            df = ak.stock_financial_abstract_ths(symbol=symbol, indicator=indicator)
            print(f"[financial_indicator_list] A股原始数据列: {df.columns.tolist()}")
            if df is None or df.empty:
                return JSONResponse({"success": False, "message": "未获取到财务数据"}, status_code=404)

            # A股需要的指标
            wanted_indicators = [
                "报告期", "净资产收益率", "资产收益率", "营业总收入", "净利润",
                "基本每股收益", "每股净资产"
            ]
            # 只保留需要的列，且存在于df中的
            cols = [col for col in wanted_indicators if col in df.columns]
            if not cols:
                return JSONResponse({"success": False, "message": "未找到所需指标"}, status_code=404)

            # 按报告期升序排列（从旧到新，便于图表从左到右显示）
            df = df.sort_values("报告期", ascending=True)
            # 转为dict
            data = df[cols].to_dict(orient="records")
            data = clean_nan(data)
            return JSONResponse({"success": True, "data": data})
    except Exception as e:
        import traceback
        print(f"[financial_indicator_list] 异常: {e}")
        print(traceback.format_exc())
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)


def clean_nan(obj):
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: clean_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_nan(v) for v in obj]
    return obj


@router.post("/quote")
async def get_batch_quotes(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    批量获取股票报价数据
    前端自选股页面使用，支持A股和港股
    
    Args:
        request: 包含codes数组的请求体
        db: 数据库会话
        
    Returns:
        包含股票报价数据的数组
    """
    try:
        # 解析请求体
        import json
        body = await request.body()
        data = json.loads(body.decode('utf-8'))
        codes = data.get('codes', [])
        
        if not codes:
            return JSONResponse({
                'success': False,
                'message': '缺少股票代码列表'
            }, status_code=400)
        
        print(f"[batch_quotes] 收到请求: codes={codes}")
        
        # 获取最新交易日期
        latest_date_result = pd.read_sql_query("""
            SELECT MAX(trade_date) AS latest_date 
            FROM stock_realtime_quote 
            WHERE change_percent IS NOT NULL
        """, db.bind)
        
        latest_trade_date = None
        if not latest_date_result.empty and latest_date_result.iloc[0]['latest_date'] is not None:
            latest_trade_date = latest_date_result.iloc[0]['latest_date']
        
        # 获取港股最新交易日期
        latest_hk_date_result = pd.read_sql_query("""
            SELECT MAX(trade_date) AS latest_date 
            FROM stock_realtime_quote_hk 
            WHERE change_percent IS NOT NULL
        """, db.bind)
        
        latest_hk_trade_date = None
        if not latest_hk_date_result.empty and latest_hk_date_result.iloc[0]['latest_date'] is not None:
            latest_hk_trade_date = latest_hk_date_result.iloc[0]['latest_date']
        
        result = []
        
        for code in codes:
            try:
                # 判断是否为港股
                is_hk = is_hk_stock(code, db)
                
                if is_hk and latest_hk_trade_date:
                    # 港股数据
                    quote_data = db.query(StockRealtimeQuoteHK).filter(
                        StockRealtimeQuoteHK.code == code,
                        StockRealtimeQuoteHK.trade_date == latest_hk_trade_date
                    ).first()
                    
                    if quote_data:
                        stock_info = {
                            'code': quote_data.code,
                            'name': quote_data.name or '',
                            'current_price': quote_data.current_price,
                            'change_amount': None,  # StockRealtimeQuote没有change_amount字段
                            'change_percent': quote_data.change_percent,
                            'open': quote_data.open,
                            'pre_close': quote_data.pre_close,
                            'high': quote_data.high,
                            'low': quote_data.low,
                            'volume': quote_data.volume,
                            'turnover': quote_data.amount  # 使用amount而不是turnover
                        }
                        result.append(clean_nan(stock_info))
                        continue
                
                elif latest_trade_date:
                    # A股数据
                    quote_data = db.query(StockRealtimeQuote).filter(
                        StockRealtimeQuote.code == code,
                        StockRealtimeQuote.trade_date == latest_trade_date
                    ).first()
                    
                    if quote_data:
                        stock_info = {
                            'code': quote_data.code,
                            'name': quote_data.name or '',
                            'current_price': quote_data.current_price,
                            'change_amount': None,  # StockRealtimeQuote没有change_amount字段
                            'change_percent': quote_data.change_percent,
                            'open': quote_data.open,
                            'pre_close': quote_data.pre_close,
                            'high': quote_data.high,
                            'low': quote_data.low,
                            'volume': quote_data.volume,
                            'turnover': quote_data.amount  # 使用amount而不是turnover
                        }
                        result.append(clean_nan(stock_info))
                        continue
                
                # 如果没有找到数据，返回基本信息
                print(f"[batch_quotes] 未找到股票 {code} 的行情数据")
                result.append({
                    'code': code,
                    'name': '',
                    'current_price': None,
                    'change_amount': None,
                    'change_percent': None,
                    'open': None,
                    'pre_close': None,
                    'high': None,
                    'low': None,
                    'volume': None,
                    'turnover': None
                })
                
            except Exception as e:
                print(f"[batch_quotes] 处理股票 {code} 时出错: {e}")
                result.append({
                    'code': code,
                    'name': '',
                    'current_price': None,
                    'change_amount': None,
                    'change_percent': None,
                    'open': None,
                    'pre_close': None,
                    'high': None,
                    'low': None,
                    'volume': None,
                    'turnover': None
                })
        
        print(f"[batch_quotes] 返回数据: {len(result)} 条记录")
        
        return JSONResponse({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        print(f"[batch_quotes] 错误: {e}")
        import traceback
        tb = traceback.format_exc()
        return JSONResponse({
            'success': False,
            'message': f'获取股票报价失败: {str(e)}',
            'error': str(e),
            'traceback': tb
        }, status_code=500)