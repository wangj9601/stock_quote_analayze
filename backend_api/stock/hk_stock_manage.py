"""
港股行情管理API
提供港股实时行情数据查询服务
"""

from fastapi import APIRouter, Query, Depends
from fastapi.responses import JSONResponse
from backend_api.database import get_db
from sqlalchemy.orm import Session
import traceback
import numpy as np
import pandas as pd
import akshare as ak
from sqlalchemy import text, create_engine, func
from backend_api.models import StockRealtimeQuoteHK, StockBasicInfoHK, HistoricalQuotesHK, MACDIndicators, KDJIndicators, RSIIndicators, MAIndicators, BOLLIndicators, MAVOLIndicators
import datetime

# 创建两个路由器：一个用于旧的接口（保持原路径），一个用于新的港股详情页接口
router_old = APIRouter(prefix="/api/stock", tags=["stock_hk"])
router = APIRouter(prefix="/api/stock/hk", tags=["stock_hk"])

def safe_float(value):
    """安全地将值转换为浮点数"""
    try:
        if value in [None, '', '-'] or pd.isna(value):
            return None
        return float(value)
    except (ValueError, TypeError):
        return None

def clean_nan(data_list):
    """清理数据中的NaN值"""
    if not isinstance(data_list, list):
        return data_list
    cleaned = []
    for item in data_list:
        if isinstance(item, dict):
            cleaned_item = {}
            for k, v in item.items():
                if pd.isna(v) or (isinstance(v, float) and np.isnan(v)):
                    cleaned_item[k] = None
                else:
                    cleaned_item[k] = v
            cleaned.append(cleaned_item)
        else:
            cleaned.append(item)
    return cleaned

@router_old.get("/hk_quote_board_list")
def get_hk_quote_board_list(
    ranking_type: str = Query('rise', description="排行类型: rise(涨幅榜), fall(跌幅榜), volume(成交量榜), turnover_rate(换手率榜)"),
    page: int = Query(1, description="页码，从1开始"),
    page_size: int = Query(20, description="每页条数，默认20"),
    keyword: str = Query(None, description="搜索关键词（股票代码或名称）")
):
    """
    获取港股实时行情排行数据，支持多种排行类型、搜索和分页 (数据源: stock_realtime_quote_hk)
    """
    try:
        print(f"📊 获取港股行情排行 (from DB): type={ranking_type}, page={page}, page_size={page_size}, keyword={keyword}")
        
        # 1. 获取最新交易日期的实时行情数据
        db = next(get_db())
        
        try:
            latest_date_result = pd.read_sql_query("""
                SELECT MAX(trade_date) as latest_date 
                FROM stock_realtime_quote_hk 
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
              
                # 构建查询SQL - 使用与stock_manage.py相同的方式
                if keyword and keyword.strip():
                    keyword_clean = keyword.strip().replace("'", "''")  # 防止SQL注入
                    sql_query = text(f"""
                        SELECT * FROM stock_realtime_quote_hk 
                        WHERE change_percent IS NOT NULL AND trade_date = '{latest_trade_date}'
                        AND (code LIKE '%{keyword_clean}%' OR name LIKE '%{keyword_clean}%' OR english_name LIKE '%{keyword_clean}%')
                        ORDER BY code
                    """)
                else:
                    sql_query = text(f"""
                        SELECT * FROM stock_realtime_quote_hk 
                        WHERE change_percent IS NOT NULL AND trade_date = '{latest_trade_date}'
                        ORDER BY code
                    """)
                
                df = pd.read_sql_query(sql_query, db.bind)
        finally:
            db.close()

        # 2. 排行类型排序
        sort_column_map = {
            'rise': ('change_percent', False),
            'fall': ('change_percent', True),
            'volume': ('volume', False),
            'turnover_rate': ('turnover_rate', False)
        }
        
        if ranking_type in sort_column_map:
            col, ascending = sort_column_map[ranking_type]
            if not df.empty and col in df.columns:
                df = df.sort_values(by=col, ascending=ascending, na_position='last')
        else:
            return JSONResponse({'success': False, 'message': '无效的排行类型'}, status_code=400)

        # 3. 字段重命名和格式化
        df = df.replace({np.nan: None})
        
        # 确保数值字段的数据类型正确
        numeric_columns = ['current_price', 'change_percent', 'change_amount', 'open', 'pre_close', 
                          'high', 'low', 'volume', 'amount']
        
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 字段映射，与A股接口保持一致
        field_rename_map = {
            'code': 'code',
            'name': 'name',
            'english_name': 'english_name',
            'current_price': 'current',
            'change_percent': 'change_percent',
            'change_amount': 'change',
            'open': 'open',
            'pre_close': 'pre_close',
            'high': 'high',
            'low': 'low',
            'volume': 'volume',
            'amount': 'turnover'
        }
        
        if df.empty:
            df_selected = pd.DataFrame(columns=field_rename_map.values())
        else:
            # 只选择存在的字段
            available_fields = [f for f in field_rename_map.keys() if f in df.columns]
            df_selected = df[available_fields].rename(columns=field_rename_map)
            
            # 如果change字段不存在，尝试计算
            if 'change' not in df_selected.columns and 'current' in df_selected.columns and 'pre_close' in df_selected.columns:
                current_numeric = pd.to_numeric(df_selected['current'], errors='coerce')
                pre_close_numeric = pd.to_numeric(df_selected['pre_close'], errors='coerce')
                df_selected['change'] = (current_numeric - pre_close_numeric).round(2)
            
            # 添加rate字段（换手率），港股可能没有，设为None
            if 'rate' not in df_selected.columns:
                df_selected['rate'] = None

        total = len(df_selected)

        # 4. 分页处理
        start = (page - 1) * page_size
        end = start + page_size
        df_page = df_selected.iloc[start:end].copy()
        
        # 5. 格式化数据
        data = df_page.to_dict(orient='records')
        data = clean_nan(data)
        
        # 格式化数值字段
        for item in data:
            for key in ['current', 'change', 'change_percent', 'open', 'pre_close', 'high', 'low', 'volume', 'turnover', 'rate']:
                if key in item and item[key] is not None:
                    if key in ['change_percent', 'rate']:
                        # 百分比字段保留2位小数
                        item[key] = round(float(item[key]), 2) if item[key] is not None else None
                    elif key in ['current', 'open', 'pre_close', 'high', 'low', 'change']:
                        # 价格字段保留2位小数
                        item[key] = round(float(item[key]), 2) if item[key] is not None else None
                    else:
                        # 其他数值字段
                        item[key] = float(item[key]) if item[key] is not None else None
        
        print(f"✅ 成功获取 {len(data)} 条港股排行数据 (总数: {total})")
        return JSONResponse({
            'success': True, 
            'data': data, 
            'total': total, 
            'page': page, 
            'page_size': page_size
        })
        
    except Exception as e:
        print(f"❌ 获取港股排行数据失败: {str(e)}")
        tb = traceback.format_exc()
        print(tb)
        return JSONResponse({
            'success': False, 
            'message': '获取港股排行数据失败', 
            'error': str(e), 
            'traceback': tb
        }, status_code=500)

@router_old.get("/hk_indices")
def get_hk_indices():
    """
    获取港股指数模拟数据
    返回恒生指数、恒生科技指数等模拟数据
    """
    try:
        import random
        from datetime import datetime
        
        # 模拟港股指数数据
        indices_data = [
            {
                'code': 'HSI',
                'name': '恒生指数',
                'value': round(18000 + random.uniform(-500, 500), 2),
                'change': round(random.uniform(-200, 200), 2),
                'change_percent': round(random.uniform(-1.5, 1.5), 2)
            },
            {
                'code': 'HSTECH',
                'name': '恒生科技指数',
                'value': round(4500 + random.uniform(-200, 200), 2),
                'change': round(random.uniform(-80, 80), 2),
                'change_percent': round(random.uniform(-2.0, 2.0), 2)
            },
            {
                'code': 'HSCEI',
                'name': '恒生中国企业指数',
                'value': round(6500 + random.uniform(-300, 300), 2),
                'change': round(random.uniform(-150, 150), 2),
                'change_percent': round(random.uniform(-2.5, 2.5), 2)
            },
            {
                'code': 'HSCI',
                'name': '恒生综合指数',
                'value': round(2800 + random.uniform(-100, 100), 2),
                'change': round(random.uniform(-50, 50), 2),
                'change_percent': round(random.uniform(-2.0, 2.0), 2)
            }
        ]
        
        return JSONResponse({
            'success': True,
            'data': indices_data,
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        print(f"❌ 获取港股指数数据失败: {str(e)}")
        tb = traceback.format_exc()
        print(tb)
        return JSONResponse({
            'success': False,
            'message': '获取港股指数数据失败',
            'error': str(e)
        }, status_code=500)

# 港股实时行情接口
@router.get("/realtime_quote_by_code")
async def get_hk_realtime_quote_by_code(code: str = Query(None, description="股票代码"), db: Session = Depends(get_db)):
    """
    获取港股实时行情数据
    优先从数据库查询，如果数据库没有则调用akshare实时获取
    
    Args:
        code: 股票代码
        
    Returns:
        {"success": True, "data": {...}}
    """
    print(f"[hk_realtime_quote_by_code] 输入参数: code={code}")
    if not code:
        print("[hk_realtime_quote_by_code] 缺少参数")
        return JSONResponse({"success": False, "message": "缺少股票代码参数code"}, status_code=400)
    
    try:
        # 获取最新交易日期
        latest_date_result = pd.read_sql_query("""
            SELECT MAX(trade_date) as latest_date 
            FROM stock_realtime_quote_hk 
            WHERE change_percent IS NOT NULL
        """, db.bind)
        
        db_stock_data = None
        if not latest_date_result.empty and latest_date_result.iloc[0]['latest_date'] is not None:
            latest_trade_date = latest_date_result.iloc[0]['latest_date']
            if isinstance(latest_trade_date, str):
                latest_trade_date = latest_trade_date[:10]  # 只取日期部分
            else:
                latest_trade_date = str(latest_trade_date)[:10]
            
            db_stock_data = db.query(StockRealtimeQuoteHK).filter(
                StockRealtimeQuoteHK.code == code,
                StockRealtimeQuoteHK.trade_date == latest_trade_date
            ).first()
        
        # 如果数据库有数据，直接返回
        if db_stock_data:
            def fmt(val):
                try:
                    if val is None:
                        return None
                    return f"{float(val):.2f}"
                except Exception:
                    return None
            
            result = {
                "code": db_stock_data.code,
                "name": db_stock_data.name,
                "current_price": fmt(db_stock_data.current_price),
                "change_amount": fmt(db_stock_data.change_amount),
                "change_percent": fmt(db_stock_data.change_percent),
                "open": fmt(db_stock_data.open),
                "pre_close": fmt(db_stock_data.pre_close),
                "high": fmt(db_stock_data.high),
                "low": fmt(db_stock_data.low),
                "volume": fmt(db_stock_data.volume),
                "turnover": fmt(db_stock_data.amount),
                "turnover_rate": None,  # 从历史行情表获取
                "pe_dynamic": None,  # 从财务指标接口获取
                "average_price": None,  # 需要计算
            }
            
            # 计算均价
            if db_stock_data.volume and db_stock_data.volume > 0 and db_stock_data.amount:
                try:
                    avg_price = float(db_stock_data.amount) / float(db_stock_data.volume)
                    result["average_price"] = fmt(avg_price)
                except Exception:
                    pass
            
            # 从历史行情表获取最新的换手率
            try:
                latest_history = db.query(HistoricalQuotesHK).filter(
                    HistoricalQuotesHK.code == code,
                    HistoricalQuotesHK.turnover_rate.isnot(None)
                ).order_by(HistoricalQuotesHK.date.desc()).first()
                if latest_history and latest_history.turnover_rate is not None:
                    result["turnover_rate"] = fmt(latest_history.turnover_rate)
                    print(f"[hk_realtime_quote_by_code] 从历史行情表获取换手率: {result['turnover_rate']}")
            except Exception as e:
                print(f"[hk_realtime_quote_by_code] 获取换手率失败: {e}")
            
            # 从财务指标接口获取市盈率
            try:
                import akshare as ak
                financial_df = ak.stock_hk_financial_indicator_em(symbol=code)
                if financial_df is not None and not financial_df.empty and '市盈率' in financial_df.columns:
                    pe_value = financial_df.iloc[0]['市盈率']
                    if pd.notna(pe_value):
                        result["pe_dynamic"] = fmt(pe_value)
                        print(f"[hk_realtime_quote_by_code] 从财务指标获取市盈率: {result['pe_dynamic']}")
            except Exception as e:
                print(f"[hk_realtime_quote_by_code] 获取市盈率失败: {e}")
            
            print(f"[hk_realtime_quote_by_code] 从数据库返回数据: {result}")
            return JSONResponse({"success": True, "data": result})
        
        # 数据库没有数据，尝试从akshare实时获取
        try:
            df_hk_spot = ak.stock_hk_spot_em()
            stock_data = df_hk_spot[df_hk_spot['代码'] == code]
            
            if stock_data.empty:
                print(f"[hk_realtime_quote_by_code] 未找到股票代码: {code}")
                return JSONResponse({"success": False, "message": f"未找到股票代码: {code}"}, status_code=404)
            
            row = stock_data.iloc[0]
            
            def fmt(val):
                try:
                    if val is None or pd.isna(val):
                        return None
                    return f"{float(val):.2f}"
                except Exception:
                    return None
            
            result = {
                "code": code,
                "name": row.get('名称', ''),
                "current_price": fmt(row.get('最新价')),
                "change_amount": fmt(row.get('涨跌额')),
                "change_percent": fmt(row.get('涨跌幅')),
                "open": fmt(row.get('今开')),
                "pre_close": fmt(row.get('昨收')),
                "high": fmt(row.get('最高')),
                "low": fmt(row.get('最低')),
                "volume": fmt(row.get('成交量')),
                "turnover": fmt(row.get('成交额')),
                "turnover_rate": None,  # 从历史行情表获取
                "pe_dynamic": None,  # 从财务指标接口获取
                "average_price": None,
            }
            
            # 计算均价
            if row.get('成交量') and float(row.get('成交量', 0)) > 0 and row.get('成交额'):
                try:
                    avg_price = float(row.get('成交额')) / float(row.get('成交量'))
                    result["average_price"] = fmt(avg_price)
                except Exception:
                    pass
            
            # 从历史行情表获取最新的换手率
            try:
                latest_history = db.query(HistoricalQuotesHK).filter(
                    HistoricalQuotesHK.code == code,
                    HistoricalQuotesHK.turnover_rate.isnot(None)
                ).order_by(HistoricalQuotesHK.date.desc()).first()
                if latest_history and latest_history.turnover_rate is not None:
                    result["turnover_rate"] = fmt(latest_history.turnover_rate)
                    print(f"[hk_realtime_quote_by_code] 从历史行情表获取换手率: {result['turnover_rate']}")
            except Exception as e:
                print(f"[hk_realtime_quote_by_code] 获取换手率失败: {e}")
            
            # 从财务指标接口获取市盈率
            try:
                financial_df = ak.stock_hk_financial_indicator_em(symbol=code)
                if financial_df is not None and not financial_df.empty and '市盈率' in financial_df.columns:
                    pe_value = financial_df.iloc[0]['市盈率']
                    if pd.notna(pe_value):
                        result["pe_dynamic"] = fmt(pe_value)
                        print(f"[hk_realtime_quote_by_code] 从财务指标获取市盈率: {result['pe_dynamic']}")
            except Exception as e:
                print(f"[hk_realtime_quote_by_code] 获取市盈率失败: {e}")
            
            print(f"[hk_realtime_quote_by_code] 从akshare返回数据: {result}")
            return JSONResponse({"success": True, "data": result})
            
        except Exception as e:
            print(f"[hk_realtime_quote_by_code] 从akshare获取数据失败: {e}")
            return JSONResponse({"success": False, "message": f"获取港股实时行情失败: {str(e)}"}, status_code=500)
            
    except Exception as e:
        print(f"[hk_realtime_quote_by_code] 异常: {e}")
        traceback.print_exc()
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)

# 港股分时数据接口
@router.get("/minute_data_by_code")
async def get_hk_minute_data_by_code(code: str = Query(None, description="股票代码")):
    """
    获取港股分时数据（使用ak.stock_hk_hist_min_em获取1分钟数据）
    
    Args:
        code: 股票代码
        
    Returns:
        {"success": True, "data": [{time, price, volume, amount, ...}]}
    """
    print(f"[hk_minute_data_by_code] 输入参数: code={code}")
    if not code:
        print("[hk_minute_data_by_code] 缺少参数")
        return JSONResponse({"success": False, "message": "缺少股票代码参数code"}, status_code=400)
    
    try:
        # 获取当日日期
        today = datetime.date.today()
        today_str = today.strftime('%Y%m%d')
        
        # 获取最近几天的分钟数据（确保能获取到当日数据）
        # 使用1分钟周期
        try:
            df = ak.stock_hk_hist_min_em(symbol=code, period="1", start_date=today_str, end_date=today_str, adjust="")
            
            if df is None or df.empty:
                # 如果当日没有数据，尝试获取最近一个交易日的数据
                # 往前推几天
                for i in range(1, 6):
                    prev_date = (today - datetime.timedelta(days=i)).strftime('%Y%m%d')
                    try:
                        df = ak.stock_hk_hist_min_em(symbol=code, period="1", start_date=prev_date, end_date=prev_date, adjust="")
                        if df is not None and not df.empty:
                            print(f"[hk_minute_data_by_code] 使用日期 {prev_date} 的数据")
                            break
                    except Exception:
                        continue
                
                if df is None or df.empty:
                    print(f"[hk_minute_data_by_code] 未找到股票代码: {code}")
                    return JSONResponse({"success": False, "message": f"未找到股票代码: {code}"}, status_code=404)
        except Exception as e:
            print(f"[hk_minute_data_by_code] 调用akshare失败: {e}")
            return JSONResponse({"success": False, "message": f"获取港股分时数据失败: {str(e)}"}, status_code=500)
        
        result = []
        for _, row in df.iterrows():
            def fmt(val):
                try:
                    if val is None or pd.isna(val):
                        return None
                    return round(float(val), 2)
                except Exception:
                    return None
            
            # 获取时间字段（可能是"时间"或"日期时间"等）
            time_val = None
            for time_col in ['时间', '日期时间', 'datetime', 'time']:
                if time_col in row:
                    time_val = row[time_col]
                    break
            
            # 格式化时间
            if time_val is not None:
                if hasattr(time_val, 'strftime'):
                    time_val = time_val.strftime('%H:%M:%S')
                else:
                    time_val = str(time_val)
            
            # 获取价格字段
            price = None
            for price_col in ['收盘', '最新价', 'close', 'price']:
                if price_col in row:
                    price = fmt(row[price_col])
                    break
            
            # 获取成交量字段
            volume = None
            for vol_col in ['成交量', 'volume']:
                if vol_col in row:
                    vol_val = row[vol_col]
                    if vol_val is not None and not pd.isna(vol_val):
                        volume = int(float(vol_val))
                    break
            
            # 获取成交额字段
            amount = None
            for amt_col in ['成交额', 'amount']:
                if amt_col in row:
                    amount = fmt(row[amt_col])
                    break
            
            # 如果没有成交额，尝试计算
            if amount is None and price is not None and volume is not None:
                try:
                    amount = fmt(float(price) * float(volume))
                except Exception:
                    pass
            
            result.append({
                "time": time_val or "",
                "price": price,
                "volume": volume,
                "amount": amount,
                "trade_type": None,  # 港股分时数据可能没有买卖盘性质
            })
        
        print(f"[hk_minute_data_by_code] 返回{len(result)}条分时数据")
        return JSONResponse({"success": True, "data": result})
        
    except Exception as e:
        print(f"[hk_minute_data_by_code] 异常: {e}")
        traceback.print_exc()
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)

# 港股K线历史数据接口（日线/周线/月线/季线/半年线/年线）
@router.get("/kline_hist")
async def get_hk_kline_hist(
    code: str = Query(None, description="股票代码"),
    period: str = Query("daily", description="周期，如daily/weekly/monthly/quarterly/semiannual/annual"),
    start_date: str = Query(None, description="开始日期，YYYY-MM-DD"),
    end_date: str = Query(None, description="结束日期，YYYY-MM-DD"),
    adjust: str = Query("", description="复权类型，港股暂不支持复权"),
    indicator: str = Query(None, description="指标类型，如vol/macd/kdj/rsi，默认返回vol"),
    db: Session = Depends(get_db)
):
    """
    获取港股K线历史数据
    修改后：从数据库历史行情表获取除当天外的数据，当天数据从实时行情表获取
    """
    print(f"[hk_kline_hist] 输入参数: code={code}, period={period}, start_date={start_date}, end_date={end_date}")
    if not code or not start_date or not end_date:
        return JSONResponse({"success": False, "message": "缺少参数"}, status_code=400)
    
    try:
        from datetime import datetime
        import pandas as pd
        today = datetime.now().strftime('%Y-%m-%d')
        
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
            
            # 1. 查询历史数据（除当天外，港股date是String类型）
            historical_query = db.query(HistoricalQuotesHK).filter(
                HistoricalQuotesHK.code == code,
                HistoricalQuotesHK.date >= start_date,
                HistoricalQuotesHK.date < today
            ).order_by(HistoricalQuotesHK.date.asc())
            
            historical_quotes = historical_query.all()
            
            # 转换历史数据
            for quote in historical_quotes:
                result.append({
                    "date": quote.date,
                    "code": code,
                    "open": fmt(quote.open),
                    "close": fmt(quote.close),
                    "high": fmt(quote.high),
                    "low": fmt(quote.low),
                    "volume": int(quote.volume) if quote.volume is not None else None,
                    "amount": fmt(quote.amount),
                    "amplitude": fmt(quote.amplitude),
                    "pct_chg": fmt(quote.change_percent),
                    "change": fmt(quote.change_amount),
                    "turnover": fmt(quote.turnover_rate),
                })
            
            # 2. 查询当天实时数据
            today_realtime = db.query(StockRealtimeQuoteHK).filter(
                StockRealtimeQuoteHK.code == code,
                StockRealtimeQuoteHK.trade_date == today
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
                    "change": fmt(today_realtime.change_amount),
                    "turnover": None,  # 实时数据可能没有换手率
                })
            
            # 按日期排序（确保日期格式统一后排序）
            from datetime import datetime
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
                        MACDIndicators.market_type == 'HK',
                        MACDIndicators.date >= start_date,
                        MACDIndicators.date <= end_date
                    ).order_by(MACDIndicators.date.asc())
                    
                    macd_records = macd_query.all()
                    macd_dict = {}
                    for record in macd_records:
                        date_str = str(record.date)
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
                    print(f"[hk_kline_hist] MACD数据查询失败: {e}")
            
            # 查询KDJ数据
            if 'kdj' in indicator_list:
                try:
                    kdj_query = db.query(KDJIndicators).filter(
                        KDJIndicators.code == code,
                        KDJIndicators.market_type == 'HK',
                        KDJIndicators.date >= start_date,
                        KDJIndicators.date <= end_date
                    ).order_by(KDJIndicators.date.asc())
                    
                    kdj_records = kdj_query.all()
                    kdj_dict = {}
                    for record in kdj_records:
                        date_str = str(record.date)
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
                    print(f"[hk_kline_hist] KDJ数据查询失败: {e}")

            # 查询RSI数据
            if 'rsi' in indicator_list:
                try:
                    rsi_query = db.query(RSIIndicators).filter(
                        RSIIndicators.code == code,
                        RSIIndicators.market_type == 'HK',
                        RSIIndicators.date >= start_date,
                        RSIIndicators.date <= end_date
                    ).order_by(RSIIndicators.date.asc())
                    
                    rsi_records = rsi_query.all()
                    rsi_dict = {}
                    for record in rsi_records:
                        date_str = str(record.date)
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
                    print(f"[hk_kline_hist] RSI数据查询失败: {e}")
            
            # 查询BOLL数据
            if 'boll' in indicator_list:
                try:
                    boll_query = db.query(BOLLIndicators).filter(
                        BOLLIndicators.code == code,
                        BOLLIndicators.market_type == 'HK',
                        BOLLIndicators.date >= start_date,
                        BOLLIndicators.date <= end_date
                    ).order_by(BOLLIndicators.date.asc())
                    
                    boll_records = boll_query.all()
                    boll_dict = {}
                    for record in boll_records:
                        date_str = str(record.date)
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
                    print(f"[hk_kline_hist] BOLL数据查询失败: {e}")
            
            # 查询MA数据（MA总是返回，因为它是K线图的基础指标）
            try:
                ma_query = db.query(MAIndicators).filter(
                    MAIndicators.code == code,
                    MAIndicators.market_type == '港股',
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
                print(f"[hk_kline_hist] MA数据查询失败: {e}")
            
            # 查询MAVOL数据
            try:
                mavol_query = db.query(MAVOLIndicators).filter(
                    MAVOLIndicators.code == code,
                    MAVOLIndicators.market_type.in_(['HK', '港股']),
                    MAVOLIndicators.date >= start_date,
                    MAVOLIndicators.date <= end_date
                ).order_by(MAVOLIndicators.date.asc())
                
                mavol_records = mavol_query.all()
                mavol_dict = {}
                for record in mavol_records:
                    date_str = str(record.date)
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
                print(f"[hk_kline_hist] MAVOL数据查询失败: {e}")
            
            # 如果没有指定indicator或indicator为vol，只返回基础K线数据和成交量（已经在result中）
            
            print(f"[hk_kline_hist] 返回{len(result)}条日线数据（历史{len(historical_quotes)}条，当天{1 if today_realtime else 0}条）")
            return JSONResponse({"success": True, "data": result})
        
        # 其他周期：优先从周期表查询，如果没有则从日线数据实时聚合
        else:
            # 周期表映射
            period_table_map = {
                'weekly': 'hk_weekly_quotes',
                'monthly': 'hk_monthly_quotes',
                'quarterly': 'hk_quarterly_quotes',
                'semiannual': 'hk_semiannual_quotes',
                'annual': 'hk_annual_quotes'
            }
            
            table_name = period_table_map.get(period)
            result = []
            
            # 尝试从周期表查询
            if table_name:
                try:
                    period_query = db.execute(text(f"""
                        SELECT code, date, open, close, high, low, volume, amount, 
                               change_percent, change_amount, amplitude, turnover_rate
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
                            result.append({
                                "date": str(row[1]),
                                "code": row[0],
                                "open": fmt(row[2]),
                                "close": fmt(row[3]),
                                "high": fmt(row[4]),
                                "low": fmt(row[5]),
                                "volume": int(row[6]) if row[6] is not None else None,
                                "amount": fmt(row[7]),
                                "amplitude": fmt(row[10]),
                                "pct_chg": fmt(row[8]),
                                "change": fmt(row[9]),
                                "turnover": fmt(row[11]),
                            })
                        print(f"[hk_kline_hist] 从周期表{table_name}返回{len(result)}条数据")
                        return JSONResponse({"success": True, "data": result})
                except Exception as e:
                    print(f"[hk_kline_hist] 从周期表{table_name}查询失败，将使用实时聚合: {e}")
            
            # Fallback: 从日线数据实时聚合
            print(f"[hk_kline_hist] 从日线数据实时聚合{period}周期数据")
            
            # 获取日线数据（包括当天）
            daily_query = db.query(HistoricalQuotesHK).filter(
                HistoricalQuotesHK.code == code,
                HistoricalQuotesHK.date >= start_date,
                HistoricalQuotesHK.date < today
            ).order_by(HistoricalQuotesHK.date.asc())
            
            daily_quotes = daily_query.all()
            
            # 获取当天实时数据
            today_realtime = db.query(StockRealtimeQuoteHK).filter(
                StockRealtimeQuoteHK.code == code,
                StockRealtimeQuoteHK.trade_date == today
            ).first()
            
            # 构建DataFrame
            daily_data = []
            for quote in daily_quotes:
                daily_data.append({
                    'date': quote.date,
                    'open': quote.open or 0,
                    'close': quote.close or 0,
                    'high': quote.high or 0,
                    'low': quote.low or 0,
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
                print(f"[hk_kline_hist] 没有日线数据可供聚合")
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
            
            print(f"[hk_kline_hist] 实时聚合返回{len(result)}条{period}周期数据")
            return JSONResponse({"success": True, "data": result})
            
    except Exception as e:
        print(f"[hk_kline_hist] 异常: {e}")
        traceback.print_exc()
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)

@router.get("/macd")
async def get_hk_macd(
    code: str = Query(None, description="股票代码"),
    start_date: str = Query(None, description="开始日期，YYYY-MM-DD"),
    end_date: str = Query(None, description="结束日期，YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    """
    获取港股MACD指标数据
    """
    print(f"[hk_macd] 输入参数: code={code}, start_date={start_date}, end_date={end_date}")
    if not code or not start_date or not end_date:
        return JSONResponse({"success": False, "message": "缺少参数"}, status_code=400)
    
    try:
        # 查询MACD数据
        macd_query = db.query(MACDIndicators).filter(
            MACDIndicators.code == code,
            MACDIndicators.market_type == 'HK',
            MACDIndicators.date >= start_date,
            MACDIndicators.date <= end_date
        ).order_by(MACDIndicators.date.asc())
        
        macd_records = macd_query.all()
        
        result = []
        for record in macd_records:
            date_str = str(record.date)  # 港股date是String类型
            result.append({
                "date": date_str,
                "code": record.code,
                "dif": round(float(record.dif), 4) if record.dif is not None else None,
                "dea": round(float(record.dea), 4) if record.dea is not None else None,
                "macd": round(float(record.macd), 4) if record.macd is not None else None,
                "ema12": round(float(record.ema12), 4) if record.ema12 is not None else None,
                "ema26": round(float(record.ema26), 4) if record.ema26 is not None else None
            })
        
        print(f"[hk_macd] 返回 {len(result)} 条MACD数据")
        return JSONResponse({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        print(f"[hk_macd] 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)

# 港股分钟K线历史数据接口
@router.get("/kline_min_hist")
async def get_hk_kline_min_hist(
    code: str = Query(None, description="股票代码"),
    period: str = Query("60", description="周期，分钟K，如1、5、15、30、60"),
    start_datetime: str = Query(None, description="开始时间，YYYY-MM-DD HH:MM:SS"),
    end_datetime: str = Query(None, description="结束时间，YYYY-MM-DD HH:MM:SS"),
    adjust: str = Query("", description="复权类型，港股暂不支持复权")
):
    """
    获取港股分钟K线历史数据
    使用ak.stock_hk_hist_min_em接口
    """
    print(f"[hk_kline_min_hist] 输入参数: code={code}, period={period}, start_datetime={start_datetime}, end_datetime={end_datetime}")
    if not code or not start_datetime or not end_datetime:
        return JSONResponse({"success": False, "message": "缺少参数"}, status_code=400)
    
    try:
        # 日期格式化：YYYY-MM-DD HH:MM:SS -> YYYYMMDD
        start_date = start_datetime.split(' ')[0].replace('-', '')
        end_date = end_datetime.split(' ')[0].replace('-', '')
        
        print(f"[hk_kline_min_hist] 调用akshare: symbol={code}, period={period}, start_date={start_date}, end_date={end_date}")
        
        # 调用akshare接口
        df = ak.stock_hk_hist_min_em(symbol=code, period=period, start_date=start_date, end_date=end_date, adjust=adjust)
        
        if df is None or df.empty:
            print(f"[hk_kline_min_hist] 未找到股票代码: {code}")
            return JSONResponse({"success": False, "message": f"未找到股票代码: {code}"}, status_code=404)
        
        result = []
        def fmt(val):
            try:
                if val is None or pd.isna(val):
                    return None
                return round(float(val), 2)
            except Exception:
                return None
        
        for _, row in df.iterrows():
            # 获取时间字段
            date_val = None
            for time_col in ['时间', '日期时间', 'datetime', 'time']:
                if time_col in row:
                    date_val = row[time_col]
                    break
            
            if date_val is not None:
                if hasattr(date_val, 'strftime'):
                    date_val = date_val.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    date_val = str(date_val)
            
            # 获取价格字段
            open_price = None
            close_price = None
            high_price = None
            low_price = None
            
            for col in ['开盘', 'open']:
                if col in row:
                    open_price = fmt(row[col])
                    break
            for col in ['收盘', 'close']:
                if col in row:
                    close_price = fmt(row[col])
                    break
            for col in ['最高', 'high']:
                if col in row:
                    high_price = fmt(row[col])
                    break
            for col in ['最低', 'low']:
                if col in row:
                    low_price = fmt(row[col])
                    break
            
            # 获取成交量
            volume = None
            for vol_col in ['成交量', 'volume']:
                if vol_col in row:
                    vol_val = row[vol_col]
                    if vol_val is not None and not pd.isna(vol_val):
                        volume = int(float(vol_val))
                    break
            
            # 获取成交额
            amount = None
            for amt_col in ['成交额', 'amount']:
                if amt_col in row:
                    amount = fmt(row[amt_col])
                    break
            
            result.append({
                "date": date_val,
                "code": code,
                "open": open_price,
                "close": close_price,
                "high": high_price,
                "low": low_price,
                "volume": volume,
                "amount": amount,
                "amplitude": None,  # 港股分钟数据可能没有振幅
                "pct_chg": None,  # 港股分钟数据可能没有涨跌幅
                "change": None,  # 港股分钟数据可能没有涨跌额
                "turnover": None,  # 港股分钟数据可能没有换手率
            })
        
        print(f"[hk_kline_min_hist] 返回{len(result)}条分钟K线数据")
        return JSONResponse({"success": True, "data": result})
        
    except Exception as e:
        print(f"[hk_kline_min_hist] 异常: {e}")
        traceback.print_exc()
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)

