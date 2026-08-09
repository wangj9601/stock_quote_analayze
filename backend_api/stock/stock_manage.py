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
from typing import Any, Optional, cast as typing_cast
from backend_api.models import StockRealtimeQuote, StockBasicInfo, StockRealtimeQuoteHK, StockBasicInfoHK, HistoricalQuotes, HistoricalQuotesHK, MACDIndicators, KDJIndicators, RSIIndicators, MAIndicators, BOLLIndicators, MAVOLIndicators
from backend_core.data_collectors.akshare.period_agg import resample_ohlcv_to_period_ends


def _is_na(val: Any) -> bool:
    """标量缺失判断，避免 pd.isna 在类型检查中被推断为 Series/ndarray。"""
    if val is None:
        return True
    try:
        result = pd.isna(val)
        if isinstance(result, (bool, np.bool_)):
            return bool(result)
        return False
    except (ValueError, TypeError):
        return False


def _to_numeric_series(series: Any) -> pd.Series:
    s = series if isinstance(series, pd.Series) else pd.Series(series)
    return pd.Series(pd.to_numeric(s, errors='coerce'), index=s.index)

# ma_indicators 表 market_type：新数据为 CN/HK，历史数据可能为 A股/港股
MA_MARKET_TYPES_CN = ('CN', 'A股')
MA_MARKET_TYPES_HK = ('HK', '港股')


def _normalize_indicator_date(value) -> str:
    if value is None:
        return ''
    s = value.strftime('%Y-%m-%d') if hasattr(value, 'strftime') else str(value)
    return s.strip()[:10]

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
    
    # 先查询港股表（港股基础信息表通常不依赖 A 股 stock_basic_info.industry 列）
    hk_exists = db.execute(
        text("SELECT 1 FROM stock_basic_info_hk WHERE code = :code LIMIT 1"),
        {"code": code_str},
    ).fetchone()
    if hk_exists:
        return True

    # 再查询 A 股表
    # 注意：stock_basic_info 可能缺少 industry 列时，直接 query(StockBasicInfo).first() 会触发 UndefinedColumn
    # 因此此处仅做 exists 查询（不选择所有列），避免 ORM 报错导致事务终止
    a_exists = db.execute(
        text("SELECT 1 FROM stock_basic_info WHERE code = :code LIMIT 1"),
        {"code": code_str},
    ).fetchone()
    if a_exists:
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

def prepare_spot_dataframe(df: Optional[pd.DataFrame]) -> pd.DataFrame:
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
    # 避免 DataFrame.rename(columns=dict) 与 pandas stubs 重载不匹配的类型检查错误
    df_prepared = df.loc[:, available_cols].copy()
    df_prepared.columns = [rename_map[col] for col in available_cols]
    df_prepared['code'] = df_prepared['code'].apply(normalize_code)

    def to_pct_float(series: pd.Series) -> pd.Series:
        return _to_numeric_series(series.astype(str).str.replace('%', ''))
    
    if 'current' in df_prepared.columns:
        df_prepared['current'] = _to_numeric_series(df_prepared['current'])
    if 'change' in df_prepared.columns:
        df_prepared['change'] = _to_numeric_series(df_prepared['change'])
    if 'change_percent' in df_prepared.columns:
        df_prepared['change_percent'] = to_pct_float(df_prepared['change_percent'])
    if 'volume' in df_prepared.columns:
        df_prepared['volume'] = _to_numeric_series(df_prepared['volume'])
    if 'turnover' in df_prepared.columns:
        df_prepared['turnover'] = _to_numeric_series(df_prepared['turnover'])
    if 'rate' in df_prepared.columns:
        df_prepared['rate'] = to_pct_float(df_prepared['rate'])
    return df_prepared

# 获取所有股票的基本信息（代码和名称），用于前端登录后全局缓存
@router.get("/stock_basic_info_all")
async def get_stock_basic_info_all(db: Session = Depends(get_db)):
    """获取所有股票的基本信息（代码和名称），用于前端登录后全局缓存"""
    print(f"[stock_basic_info_all] 收到请求: 获取所有股票信息")
    try:
        from models import StockBasicInfo
        stocks = db.query(StockBasicInfo).filter(text("COALESCE(collect_enabled, TRUE) = TRUE")).all()
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
        q_a = db.query(StockBasicInfo).filter(text("COALESCE(collect_enabled, TRUE) = TRUE"))
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
    db = None
    try:
        from backend_api.database import SessionLocal

        db = SessionLocal()
        # 首先获取最新的交易日期（使用 session.execute 避免 pd.read_sql_query 与 Engine 不兼容）
        latest_date_row = db.execute(text("""
            SELECT MAX(trade_date) AS latest_date
            FROM stock_realtime_quote
            WHERE change_percent IS NOT NULL AND change_percent != 0
        """)).fetchone()

        if not latest_date_row or latest_date_row[0] is None:
            return JSONResponse({'success': False, 'message': '暂无行情数据'}, status_code=404)

        latest_trade_date = latest_date_row[0]
        print(f"📅 首页涨幅榜使用最新交易日期: {latest_trade_date}")

        # 获取最新交易日期的数据（参数化查询，避免 SQL 注入）
        rows = db.execute(text("""
            SELECT code, name, current_price, change_percent, open, pre_close, high, low, volume, amount
            FROM stock_realtime_quote
            WHERE change_percent IS NOT NULL AND change_percent != 0 AND trade_date = :trade_date
            ORDER BY change_percent DESC
        """), {"trade_date": latest_trade_date}).fetchmany(limit)

        # 准备名称映射，避免名称字段为空
        code_list = [str(r[0]) for r in rows if r[0]]
        name_map = {}
        if code_list:
            name_rows = db.query(StockBasicInfo.code, StockBasicInfo.name).filter(
                StockBasicInfo.code.in_(code_list)
            ).all()
            name_map = {str(row.code): row.name for row in name_rows if row.name}

        data = []
        for row in rows:
            code = str(row[0])
            display_name = row[1]
            if not display_name or str(display_name).lower() == 'null':
                display_name = name_map.get(code) or ''
            data.append({
                'code': code,
                'name': display_name,
                'current': row[2],
                'change_percent': row[3],
                'open': row[4],
                'pre_close': row[5],
                'high': row[6],
                'low': row[7],
                'volume': row[8],
                'turnover': row[9],
            })
        print(f"✅(DB) 成功获取 {len(data)} 条A股涨幅榜数据（已去重）")
        return JSONResponse({'success': True, 'data': data})
    except Exception as e:
        print(f"❌ 获取A股涨幅榜数据失败: {str(e)}")
        tb = traceback.format_exc()
        print(tb)
        return JSONResponse({'success': False, 'message': '获取A股涨幅榜数据失败', 'error': str(e), 'traceback': tb}, status_code=500)
    finally:
        if db is not None:
            try:
                db.rollback()
            except Exception:
                pass
            db.close()
    
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
        
        # 1. 获取最新交易日期的实时行情数据（使用 session.execute 避免 pd.read_sql_query 与 Engine 不兼容）
        from backend_api.database import SessionLocal
        db = SessionLocal()
        try:
            latest_date_row = db.execute(text("""
                SELECT MAX(trade_date) AS latest_date
                FROM stock_realtime_quote
                WHERE change_percent IS NOT NULL
            """)).fetchone()

            if not latest_date_row or latest_date_row[0] is None:
                latest_trade_date = None
                df = pd.DataFrame()
            else:
                latest_trade_date = latest_date_row[0]
                if latest_trade_date is not None and len(str(latest_trade_date)) > 10:
                    latest_trade_date = str(latest_trade_date)[:10]
                print(f"📅 使用最新交易日期: {latest_trade_date}")

                if keyword and keyword.strip():
                    kw = keyword.strip()
                    result = db.execute(text("""
                        SELECT * FROM stock_realtime_quote
                        WHERE change_percent IS NOT NULL AND trade_date = :trade_date
                        AND (code LIKE :pat OR name LIKE :pat)
                        ORDER BY code
                    """), {"trade_date": latest_trade_date, "pat": f"%{kw}%"})
                else:
                    result = db.execute(text("""
                        SELECT * FROM stock_realtime_quote
                        WHERE change_percent IS NOT NULL AND trade_date = :trade_date
                        ORDER BY code
                    """), {"trade_date": latest_trade_date})

                rows = result.fetchall()
                df = pd.DataFrame(rows, columns=pd.Index(list(result.keys()))) if rows else pd.DataFrame()
        finally:
            try:
                db.rollback()
            except Exception:
                pass
            db.close()

        # 3. 市场类型过滤（用 loc 保持 DataFrame 类型，避免布尔索引被推断为 Series|DataFrame）
        if market != 'all' and not df.empty and 'code' in df.columns:
            code_s = df['code'].astype(str)
            if market == 'sh':
                df = df.loc[code_s.str.startswith('6')].copy()
            elif market == 'sz':
                df = df.loc[code_s.str.startswith('0') | code_s.str.startswith('3')].copy()  # 深市包含主板和创业板
            elif market == 'cy':
                df = df.loc[code_s.str.startswith('3')].copy()
            elif market == 'bj':
                df = df.loc[code_s.str.startswith('8') | code_s.str.startswith('4')].copy()  # 北交所
        
        # 4. 排行类型排序
        sort_column_map = {
            'rise': ('change_percent', False),
            'fall': ('change_percent', True),
            'volume': ('volume', False),
            'turnover_rate': ('turnover_rate', False)
        }
        
        if ranking_type in sort_column_map:
            col, ascending = sort_column_map[ranking_type]
            if col in df.columns:
                df = df.sort_values(by=[col], ascending=ascending)
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
                df[col] = _to_numeric_series(df.loc[:, col])
        
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
        renamed_cols = list(field_rename_map.values())
        
        if df.empty:
            df_selected = pd.DataFrame(columns=pd.Index(renamed_cols))
        else:
            src_cols = [c for c in field_rename_map.keys() if c in df.columns]
            df_selected = df.loc[:, src_cols].copy()
            df_selected.columns = pd.Index([field_rename_map[c] for c in src_cols])

        # Calculate 'change' if possible
        if not df_selected.empty and 'current' in df_selected.columns and 'pre_close' in df_selected.columns:
            # 确保数据类型为数值型，处理可能的字符串或None值
            current_numeric = _to_numeric_series(df_selected.loc[:, 'current'])
            pre_close_numeric = _to_numeric_series(df_selected.loc[:, 'pre_close'])
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
                
                if market != 'all' and 'code' in df_selected.columns:
                    code_s = df_selected['code'].astype(str)
                    if market == 'sh':
                        df_selected = df_selected.loc[code_s.str.startswith('6')].copy()
                    elif market == 'sz':
                        df_selected = df_selected.loc[code_s.str.startswith('0') | code_s.str.startswith('3')].copy()
                    elif market == 'cy':
                        df_selected = df_selected.loc[code_s.str.startswith('3')].copy()
                    elif market == 'bj':
                        df_selected = df_selected.loc[code_s.str.startswith('8') | code_s.str.startswith('4')].copy()
                
                fallback_sort_map = {
                    'rise': ('change_percent', False),
                    'fall': ('change_percent', True),
                    'volume': ('volume', False),
                    'turnover_rate': ('rate', False)
                }
                sort_col, ascending = fallback_sort_map.get(ranking_type, ('change_percent', False))
                if sort_col in df_selected.columns:
                    df_selected = df_selected.sort_values(by=[sort_col], ascending=ascending)
                total = len(df_selected)

        start = (page - 1) * page_size
        end = start + page_size
        df_page = df_selected.iloc[start:end].copy()
        
        # 名称兜底（仅对本地数据）
        if not fallback_used and not df_page.empty and 'code' in df_page.columns:
            code_list = [str(code) for code in df_page['code'].tolist() if code]
            if code_list:
                from backend_api.database import SessionLocal
                db_lookup = SessionLocal()
                try:
                    name_rows = db_lookup.query(StockBasicInfo.code, StockBasicInfo.name).filter(
                        StockBasicInfo.code.in_(code_list)
                    ).all()
                finally:
                    try:
                        db_lookup.rollback()
                    except Exception:
                        pass
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
        return JSONResponse({'success': True, 'data': data, 'total': total, 'page': page, 'page_size': page_size})
        
    except Exception as e:
        print(f"❌ 获取A股排行数据失败: {str(e)}")
        tb = traceback.format_exc()
        print(tb)
        return JSONResponse({'success': False, 'message': '获取A股排行数据失败', 'error': str(e), 'traceback': tb}, status_code=500)


@router.get("/volume_aberration_list")
def get_volume_aberration_list(
    market: str = Query(..., description="市场: cn(A股) 或 hk(港股)"),
    date: str = Query(None, description="交易日期 YYYY-MM-DD，不传则取该市场最新交易日"),
    order: str = Query("desc", description="排序: desc 放量榜(量比降序), asc 缩量榜(量比升序)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    keyword: str = Query(None, description="搜索关键词（股票代码或名称）")
):
    """
    A股/港股每日成交量异动榜：行情表 JOIN mavol_indicators，按量比(20)排序分页。
    仅返回当日有 mavol 记录的股票（量比可算）。
    """
    if market not in ("cn", "hk"):
        return JSONResponse({"success": False, "message": "market 须为 cn 或 hk"}, status_code=400)
    if order not in ("desc", "asc"):
        order = "desc"

    from backend_api.services.volume_aberration_service import get_volume_aberration_data
    from backend_api.database import SessionLocal

    db = SessionLocal()
    try:
        result, trade_date = get_volume_aberration_data(db, market=market, date=date, order=order)
        if trade_date is None:
            return JSONResponse({"success": True, "data": [], "total": 0, "date": None, "page": page, "page_size": page_size})
        
        # 处理搜索关键词
        if keyword and keyword.strip():
            kw = keyword.strip().lower()
            # 如果是纯数字且长度不足6位，通常可能是A股代码简写，但这里结果已经是全量，直接包含匹配即可
            filtered = []
            for item in result:
                code_str = str(item.get('code', '')).lower()
                name_str = str(item.get('name', '')).lower()
                if kw in code_str or kw in name_str:
                    filtered.append(item)
            result = filtered

        total = len(result)
        start = (page - 1) * page_size
        page_data = result[start : start + page_size]
        for i, item in enumerate(page_data):
            item["rank"] = start + i + 1
        return JSONResponse({
            "success": True,
            "data": page_data,
            "total": total,
            "date": trade_date,
            "page": page,
            "page_size": page_size,
        })
    except Exception as e:
        traceback.print_exc()
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)
    finally:
        try:
            db.rollback()
        except Exception:
            pass
        db.close()


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
        def fmt(val):
            try:
                if val is None:
                    return None
                return f"{float(val):.2f}"
            except Exception:
                return None

        # 1. 优先尝试从实时行情表获取最新数据
        # 先找到该股票最新的交易日期
        db_stock_data = db.query(StockRealtimeQuote).filter(
            StockRealtimeQuote.code == code
        ).order_by(desc(StockRealtimeQuote.trade_date)).first()
        
        source = "realtime_db"
        
        # 2. 如果实时行情表没有，从历史行情表获取最近一天的数据
        if not db_stock_data:
            latest_history = db.query(HistoricalQuotes).filter(
                HistoricalQuotes.code == code
            ).order_by(desc(HistoricalQuotes.date)).first()
            
            if latest_history:
                db_stock_data = latest_history
                source = "history_db"
                # 统一字段名映射 (HistoricalQuotes 使用 date, change, change_percent)
                # StockRealtimeQuote 使用 trade_date, change_percent
                pass

        if not db_stock_data:
            print(f"[realtime_quote_by_code] 数据库中未找到股票代码: {code}")
            return JSONResponse({"success": False, "message": f"未找到股票代码: {code}"}, status_code=404)

        # 构建统一的结果格式
        # 注意：HistoricalQuotes 中的字段名和 StockRealtimeQuote 有些不同，需要适配
        if source == "realtime_db":
            result = {
                "code": code,
                "name": db_stock_data.name,
                "current_price": fmt(db_stock_data.current_price),
                "change_amount": fmt((db_stock_data.current_price - db_stock_data.pre_close) if db_stock_data.current_price and db_stock_data.pre_close else None),
                "change_percent": fmt(db_stock_data.change_percent),
                "open": fmt(db_stock_data.open),
                "pre_close": fmt(db_stock_data.pre_close),
                "high": fmt(db_stock_data.high),
                "low": fmt(db_stock_data.low),
                "volume": fmt(db_stock_data.volume), # 后端存的是"手"还是"张"？前端期望显示时除以10000
                "turnover": fmt(db_stock_data.amount),
                "turnover_rate": fmt(db_stock_data.turnover_rate),
                "pe_dynamic": fmt(db_stock_data.pe_dynamic),
                "average_price": fmt(None),
            }
            # 计算均价：成交额(元) / 成交量。
            # volume 有时为「手」、有时为「股」；若均价相对现价偏离过大，按手×100 再算。
            if db_stock_data.amount and db_stock_data.volume and db_stock_data.volume > 0:
                amt = float(db_stock_data.amount)
                vol = float(db_stock_data.volume)
                px = float(db_stock_data.current_price or 0) or None
                avg = amt / vol
                if px and px > 0 and avg > px * 8:
                    avg = amt / (vol * 100.0)
                result["average_price"] = fmt(avg)
        else: # history_db
            result = {
                "code": code,
                "name": db_stock_data.name,
                "current_price": fmt(db_stock_data.close),
                "change_amount": fmt(db_stock_data.change),
                "change_percent": fmt(db_stock_data.change_percent),
                "open": fmt(db_stock_data.open),
                "pre_close": fmt(db_stock_data.pre_close),
                "high": fmt(db_stock_data.high),
                "low": fmt(db_stock_data.low),
                "volume": fmt(db_stock_data.volume),
                "turnover": fmt(db_stock_data.amount),
                "turnover_rate": fmt(db_stock_data.turnover_rate),
                "pe_dynamic": None,
                "average_price": fmt(None),
            }
            if db_stock_data.amount and db_stock_data.volume and db_stock_data.volume > 0:
                amt = float(db_stock_data.amount)
                vol = float(db_stock_data.volume)
                px = float(db_stock_data.close or 0) or None
                avg = amt / vol
                if px and px > 0 and avg > px * 8:
                    avg = amt / (vol * 100.0)
                result["average_price"] = fmt(avg)

        print(f"[realtime_quote_by_code] 从{source}输出数据: {result}")
        return JSONResponse({"success": True, "data": result})
    except Exception as e:
        print(f"[realtime_quote_by_code] 异常: {e}")
        traceback.print_exc()
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
            def fmt(val):
                try:
                    if val is None or _is_na(val):
                        return None
                    return round(float(val), 2)
                except Exception:
                    return None
            for _, row in df.iterrows():
                hands = fmt(row.get("手数"))
                price = fmt(row.get("成交价"))
                amount = fmt(hands * price) if hands is not None and price is not None else None
                result.append({
                    "time": row.get("时间"),
                    "price": price,
                    "volume": row.get("手数"),
                    "amount": amount,
                    "trade_type": row.get("买卖盘性质") if "买卖盘性质" in row.index else None,
                })
            print(f"[minute_data_by_code] 交易日，返回{len(result)}条分时数据")
        else:
            # 非交易日，取最近一个交易日的分钟数据
            df = ak.stock_zh_a_hist_pre_min_em(symbol=code, start_time="09:00:00", end_time="15:40:00")
            if df is None or df.empty:
                print(f"[minute_data_by_code] 非交易日未找到股票代码: {code}")
                return JSONResponse({"success": False, "message": f"未找到股票代码: {code}"}, status_code=404)
            # 取最近一个交易日
            def fmt(val):
                try:
                    if val is None or _is_na(val):
                        return None
                    return round(float(val), 2)
                except Exception:
                    return None
            for _, row in df.iterrows():
                amount_val = row.get("成交额")
                volume_val = row.get("成交量")
                avg_price = None
                if amount_val is not None and volume_val is not None and not _is_na(volume_val):
                    try:
                        vol_f = float(volume_val)
                        if vol_f != 0:
                            avg_price = fmt(float(amount_val) / (vol_f * 100))
                    except (TypeError, ValueError):
                        avg_price = None
                result.append({
                    "time": row.get("时间"),
                    "price": fmt(row.get("最新价")),
                    "open": fmt(row.get("开盘")),
                    "close": fmt(row.get("收盘")),
                    "high": fmt(row.get("最高")),
                    "low": fmt(row.get("最低")),
                    "avg_price": avg_price,
                    "volume": volume_val,
                    "amount": fmt(amount_val),
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
                # 实时行情的成交量通常是股，而历史行情是手(100股)，所以需要转换
                real_volume = today_realtime.volume
                if real_volume is not None and real_volume > 0:
                    real_volume = int(real_volume / 100)
                
                result.append({
                    "date": today,
                    "code": code,
                    "open": fmt(today_realtime.open),
                    "close": fmt(today_realtime.current_price),  # 实时行情中current_price相当于收盘价
                    "high": fmt(today_realtime.high),
                    "low": fmt(today_realtime.low),
                    "volume": real_volume,
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
                    MAIndicators.market_type.in_(MA_MARKET_TYPES_CN),
                    MAIndicators.date >= start_date,
                    MAIndicators.date <= end_date
                ).order_by(MAIndicators.date.asc())
                
                ma_records = ma_query.all()
                ma_dict = {}
                for record in ma_records:
                    date_str = _normalize_indicator_date(record.date)
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
            
            # 查询MAVOL数据
            try:
                mavol_query = db.query(MAVOLIndicators).filter(
                    MAVOLIndicators.code == code,
                    MAVOLIndicators.market_type.in_(['CN', 'A股']),
                    MAVOLIndicators.date >= start_date,
                    MAVOLIndicators.date <= end_date
                ).order_by(MAVOLIndicators.date.asc())
                
                mavol_records = mavol_query.all()
                mavol_dict = {}
                for record in mavol_records:
                    date_str = record.date.strftime('%Y-%m-%d') if hasattr(record.date, 'strftime') else str(record.date)
                    mavol_dict[date_str] = {
                        "mavol5": round(float(record.mavol5), 2) if record.mavol5 is not None else None,
                        "mavol10": round(float(record.mavol10), 2) if record.mavol10 is not None else None,
                        "mavol20": round(float(record.mavol20), 2) if record.mavol20 is not None else None
                    }
                
                # 将MAVOL数据合并到K线数据中
                for item in result:
                    if item['date'] in mavol_dict:
                        item.update(mavol_dict[item['date']])
            except Exception as e:
                print(f"[kline_hist] MAVOL数据查询失败: {e}")
            
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
                            # SELECT: code,date,open,close,high,low,volume,amount,change_percent,change,amplitude,turnover_rate
                            result.append({
                                "date": date_str,
                                "code": row[0],
                                "open": fmt(row[2]),
                                "close": fmt(row[3]),
                                "high": fmt(row[4]),
                                "low": fmt(row[5]),
                                "volume": int(row[6]) if row[6] is not None else None,
                                "amount": fmt(row[7]),
                                "pct_chg": fmt(row[8]),
                                "change": fmt(row[9]),
                                "amplitude": fmt(row[10]),
                                "turnover": fmt(row[11]),
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
                # 实时行情的成交量通常是股，而历史行情是手(100股)，所以需要转换
                real_volume = today_realtime.volume or 0
                if real_volume > 0:
                    real_volume = real_volume / 100
                    
                daily_data.append({
                    'date': today,
                    'open': today_realtime.open or 0,
                    'close': today_realtime.current_price or 0,
                    'high': today_realtime.high or 0,
                    'low': today_realtime.low or 0,
                    'volume': real_volume,
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
            elif period in ('quarterly', 'semiannual', 'annual'):
                # 季/半年/年：日历期末日（03-31/06-30/09-30/12-31；半年 06-30/12-31；年 12-31）
                resampled = resample_ohlcv_to_period_ends(
                    df, period, columns=('open', 'high', 'low', 'close', 'volume', 'amount')
                )
            else:
                return JSONResponse({"success": False, "message": f"不支持的周期类型: {period}"}, status_code=400)
            
            # 转换结果
            for idx, row in resampled.iterrows():
                date_str = _normalize_indicator_date(idx)
                vol = row['volume']
                result.append({
                    "date": date_str,
                    "code": code,
                    "open": fmt(row['open']),
                    "close": fmt(row['close']),
                    "high": fmt(row['high']),
                    "low": fmt(row['low']),
                    "volume": int(vol) if not _is_na(vol) else None,
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
        # 日期格式化（上方已校验非空，此处直接格式化）
        start_dt_fmt = start_datetime.replace('-', '').replace(':', '').replace(' ', '')
        end_dt_fmt = end_datetime.replace('-', '').replace(':', '').replace(' ', '')
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
                if val is None or _is_na(val):
                    return None
                return round(float(val), 2)
            except Exception:
                return None
        for _, row in df.iterrows():
            date_val = row.get("时间")
            if date_val is not None and hasattr(date_val, 'strftime'):
                date_val = date_val.strftime('%Y-%m-%d %H:%M:%S')  # type: ignore[union-attr]
            vol = row.get("成交量")
            try:
                volume = int(vol) if vol is not None and not _is_na(vol) else None
            except (TypeError, ValueError):
                volume = None
            result.append({
                "date": date_val,
                "code": code,
                "open": fmt(row.get("开盘")),
                "close": fmt(row.get("收盘")),
                "high": fmt(row.get("最高")),
                "low": fmt(row.get("最低")),
                "volume": volume,
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
            MAIndicators.market_type.in_(MA_MARKET_TYPES_CN),
            MAIndicators.date >= start_date,
            MAIndicators.date <= end_date
        ).order_by(MAIndicators.date.asc())
        
        ma_records = ma_query.all()
        
        result = []
        for record in ma_records:
            date_str = _normalize_indicator_date(record.date)
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
            # 港股：使用 stock_financial_hk_analysis_indicator_em（东方财富-港股-财务分析-主要指标）
            try:
                df = ak.stock_financial_hk_analysis_indicator_em(symbol=code, indicator="报告期")
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
            
            # 按报告期降序，取最新一期
            if "REPORT_DATE" in df.columns:
                df = df.sort_values("REPORT_DATE", ascending=False)
            try:
                row_data = df.iloc[0]
            except (IndexError, KeyError) as e:
                print(f"[latest_financial] 港股获取行数据失败: {e}")
                return JSONResponse({"success": False, "message": "未获取到财务数据"}, status_code=404)
            
            # 港股英文字段 -> 结果 key（该接口无市盈率/市净率）
            hk_indicator_map = {
                "roe": ["ROE_AVG", "ROE_YEARLY"],
                "roa": ["ROA"],
                "revenue": ["OPERATE_INCOME"],
                "profit": ["HOLDER_PROFIT"],
                "eps": ["BASIC_EPS"],
                "bps": ["BPS"],
            }
            
            report_date = None
            if "REPORT_DATE" in row_data.index and not pd.isna(row_data["REPORT_DATE"]):
                report_date = str(row_data["REPORT_DATE"])[:10]
            
            result = {
                "report_date": report_date,
                "pe": None,
                "pb": None,
            }
            
            for key, possible_cols in hk_indicator_map.items():
                value = None
                for col_name in possible_cols:
                    try:
                        if col_name not in df.columns:
                            continue
                        val = row_data[col_name] if col_name in row_data.index else None
                        if val is None:
                            continue
                        if isinstance(val, str) and '%' in val:
                            val = val.replace('%', '').strip()
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
                    matched = df.loc[df[row_name_col] == name]
                    if not matched.empty:
                        if latest_date in matched.columns:
                            value = matched.iloc[0][latest_date]
                        else:
                            value = matched.iloc[0, -1]
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
            # 港股：使用 stock_financial_hk_analysis_indicator_em（支持年度/报告期多期数据）
            hk_indicator = "年度"
            if indicator in ("1", "按报告期"):
                hk_indicator = "报告期"
            elif indicator in ("2", "按年度"):
                hk_indicator = "年度"
            elif indicator in ("年度", "报告期"):
                hk_indicator = indicator
            try:
                df = ak.stock_financial_hk_analysis_indicator_em(symbol=symbol, indicator=hk_indicator)
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
            
            # 英文字段 -> 与 A 股前端一致的中文结果字段
            hk_col_map = {
                "报告期": "REPORT_DATE",
                "净资产收益率": "ROE_AVG",
                "资产收益率": "ROA",
                "营业总收入": "OPERATE_INCOME",
                "净利润": "HOLDER_PROFIT",
                "基本每股收益": "BASIC_EPS",
                "每股净资产": "BPS",
            }
            
            records = []
            for _, row in df.iterrows():
                result_data = {}
                for result_key, col_name in hk_col_map.items():
                    try:
                        if col_name not in df.columns:
                            result_data[result_key] = None
                            continue
                        val = row[col_name]
                        if result_key == "报告期":
                            if _is_na(val):
                                result_data[result_key] = None
                            else:
                                result_data[result_key] = str(val)[:10]
                            continue
                        if _is_na(val) or (isinstance(val, str) and val.strip() == ''):
                            result_data[result_key] = None
                            continue
                        if isinstance(val, str) and '%' in val:
                            val = val.replace('%', '').strip()
                        try:
                            result_data[result_key] = float(val)
                        except (ValueError, TypeError) as e:
                            print(f"[financial_indicator_list] 港股指标 {result_key} 值转换失败: {val}, 错误: {e}")
                            result_data[result_key] = None
                    except Exception as e:
                        print(f"[financial_indicator_list] 港股指标 {result_key} 处理出错: {e}")
                        result_data[result_key] = None
                records.append(result_data)
            
            # 按报告期升序（与 A 股图表从左到右一致）
            records.sort(key=lambda x: x.get("报告期") or "")
            data = clean_nan(records)
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
            if "报告期" in df.columns:
                df = df.sort_values(by=["报告期"], ascending=True)
            # 转为dict（loc 保证子集为 DataFrame，避免 to_dict 重载不匹配）
            subset = df.loc[:, cols]
            data = typing_cast(list, subset.to_dict(orient="records"))
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
        latest_trade_date = None
        latest_date_row = db.execute(text("""
            SELECT MAX(trade_date) AS latest_date
            FROM stock_realtime_quote
            WHERE change_percent IS NOT NULL
        """)).fetchone()
        if latest_date_row and latest_date_row[0] is not None:
            latest_trade_date = latest_date_row[0]
        
        # 获取港股最新交易日期
        latest_hk_trade_date = None
        latest_hk_date_row = db.execute(text("""
            SELECT MAX(trade_date) AS latest_date
            FROM stock_realtime_quote_hk
            WHERE change_percent IS NOT NULL
        """)).fetchone()
        if latest_hk_date_row and latest_hk_date_row[0] is not None:
            latest_hk_trade_date = latest_hk_date_row[0]
        
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