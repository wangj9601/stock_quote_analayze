"""
港股历史数据直接采集程序（从AKShare API）
直接从AKShare API获取港股历史数据，不依赖实时行情表
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
import logging
import time
import akshare as ak
import pandas as pd

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend_core.database.db import SessionLocal
from sqlalchemy import text
from backend_core.utils.macd_calculator import MACDCalculator
from backend_core.utils.kdj_calculator import KDJCalculator
from backend_core.utils.ma_calculator import MACalculator
from backend_core.utils.boll_calculator import BOLLCalculator
from backend_core.utils.mavol_calculator import MAVOLCalculator
from backend_core.utils.mean_frequency_calculator import MeanFrequencyResonanceCalculator
from backend_core.utils.rsi_calculator import RSICalculator


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('direct_hk_collection.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def safe_value(val) -> float:
    """安全地转换数值"""
    if pd.isna(val):
        return None
    try:
        return float(val)
    except:
        return None


def get_hk_stock_list(session) -> list:
    """从数据库获取所有港股代码和名称"""
    try:
        result = session.execute(text("SELECT code, name FROM stock_basic_info_hk ORDER BY code"))
        stocks = [{"code": row[0], "name": row[1]} for row in result.fetchall()]
        logger.info(f"从数据库获取到 {len(stocks)} 只港股")
        return stocks
    except Exception as e:
        logger.error(f"获取港股列表失败: {e}")
        return []


def fetch_stock_data_from_akshare(stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    从AKShare获取单只股票的历史数据
    
    Args:
        stock_code: 股票代码（5位数字）
        start_date: 开始日期 YYYYMMDD
        end_date: 结束日期 YYYYMMDD
        
    Returns:
        DataFrame 或 None
    """
    try:
        # 尝试使用东方财富数据源
        logger.debug(f"正在从东方财富获取 {stock_code} 的数据...")
        df = ak.stock_hk_hist_em(
            symbol=stock_code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust=""
        )
        
        if df is not None and not df.empty:
            logger.debug(f"成功从东方财富获取 {stock_code} 的 {len(df)} 条数据")
            return df
        else:
            logger.warning(f"东方财富未返回 {stock_code} 的数据")
            return None
            
    except Exception as e:
        logger.error(f"从AKShare获取 {stock_code} 数据失败: {e}")
        return None


def save_to_database(stock_code: str, stock_name: str, df: pd.DataFrame, session):
    """
    保存数据到数据库
    
    Args:
        stock_code: 股票代码
        stock_name: 股票名称
        df: 数据DataFrame
        session: 数据库会话
    """
    saved_count = 0
    
    for _, row in df.iterrows():
        try:
            # 提取数据
            trade_date = pd.to_datetime(row['日期']).strftime('%Y-%m-%d')
            
            # 构造插入数据
            insert_dict = {
                'code': stock_code,
                'name': stock_name,
                'date': trade_date,
                'open': safe_value(row.get('开盘')),
                'high': safe_value(row.get('最高')),
                'low': safe_value(row.get('最低')),
                'close': safe_value(row.get('收盘')),
                'volume': safe_value(row.get('成交量')),
                'amount': safe_value(row.get('成交额')),
                'amplitude': safe_value(row.get('振幅')),
                'change_percent': safe_value(row.get('涨跌幅')),
                'change_amount': safe_value(row.get('涨跌额')),
                'turnover_rate': safe_value(row.get('换手率')),
                'collected_source': 'akshare',
                'collected_date': datetime.now().strftime('%Y-%m-%d'),
                'create_date': datetime.now()
            }
            
            # 插入或更新数据
            upsert_stmt = text("""
                INSERT INTO historical_quotes_hk (
                    code, name, date, open, high, low, close, volume, amount,
                    amplitude, change_percent, change_amount, turnover_rate,
                    collected_source, collected_date, create_date
                ) VALUES (
                    :code, :name, :date, :open, :high, :low, :close, :volume, :amount,
                    :amplitude, :change_percent, :change_amount, :turnover_rate,
                    :collected_source, :collected_date, :create_date
                )
                ON CONFLICT (code, date) DO UPDATE SET
                    name = EXCLUDED.name,
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    amount = EXCLUDED.amount,
                    amplitude = EXCLUDED.amplitude,
                    change_percent = EXCLUDED.change_percent,
                    change_amount = EXCLUDED.change_amount,
                    turnover_rate = EXCLUDED.turnover_rate,
                    collected_source = EXCLUDED.collected_source,
                    collected_date = EXCLUDED.collected_date
            """)
            
            session.execute(upsert_stmt, insert_dict)
            saved_count += 1
            
        except Exception as e:
            logger.error(f"保存 {stock_code} 在 {trade_date} 的数据失败: {e}")
            continue
    
    session.commit()
    return saved_count


def calculate_indicators(stock_code: str, session):
    """
    计算并保存技术指标
    
    Args:
        stock_code: 股票代码
        session: 数据库会话
    """
    try:
        # 获取历史数据
        result = session.execute(text("""
            SELECT date, close, high, low, volume
            FROM historical_quotes_hk
            WHERE code = :code
            AND close IS NOT NULL
            ORDER BY date ASC
        """), {"code": stock_code})
        
        rows = result.fetchall()
        if len(rows) < 30:  # 至少需要30天数据
            logger.debug(f"{stock_code} 数据不足，跳过指标计算")
            return
        
        dates = [row[0] for row in rows]
        closes = [float(row[1]) for row in rows]
        highs = [float(row[2]) for row in rows]
        lows = [float(row[3]) for row in rows]
        volumes = [float(row[4]) if row[4] else 0 for row in rows]
        
        # 计算MACD
        if len(closes) >= 26:
            macd_calc = MACDCalculator()
            macd_results = macd_calc.calculate_macd_batch(closes)
            for i, macd_data in enumerate(macd_results):
                if macd_data['dif'] is not None:
                    try:
                        session.execute(text("""
                            INSERT INTO macd_indicators
                            (code, date, market_type, dif, dea, macd, ema12, ema26, created_at)
                            VALUES (:code, :date, :market_type, :dif, :dea, :macd, :ema12, :ema26, :created_at)
                            ON CONFLICT (code, date, market_type) DO UPDATE SET
                                dif = EXCLUDED.dif, dea = EXCLUDED.dea, macd = EXCLUDED.macd,
                                ema12 = EXCLUDED.ema12, ema26 = EXCLUDED.ema26
                        """), {
                            'code': stock_code, 'date': dates[i], 'market_type': 'HK',
                            'dif': macd_data['dif'], 'dea': macd_data['dea'], 'macd': macd_data['macd'],
                            'ema12': macd_data['ema12'], 'ema26': macd_data['ema26'],
                            'created_at': datetime.now()
                        })
                    except Exception as e:
                        logger.debug(f"保存MACD失败: {e}")
        
        # 计算KDJ
        if len(closes) >= 9:
            kdj_calc = KDJCalculator()
            kdj_results = kdj_calc.calculate_kdj_batch(closes, highs, lows)
            for i, kdj_data in enumerate(kdj_results):
                if kdj_data['k'] is not None:
                    try:
                        session.execute(text("""
                            INSERT INTO kdj_indicators
                            (code, date, market_type, k, d, j, rsv, created_at)
                            VALUES (:code, :date, :market_type, :k, :d, :j, :rsv, :created_at)
                            ON CONFLICT (code, date, market_type) DO UPDATE SET
                                k = EXCLUDED.k, d = EXCLUDED.d, j = EXCLUDED.j, rsv = EXCLUDED.rsv
                        """), {
                            'code': stock_code, 'date': dates[i], 'market_type': 'HK',
                            'k': kdj_data['k'], 'd': kdj_data['d'], 'j': kdj_data['j'],
                            'rsv': kdj_data['rsv'], 'created_at': datetime.now()
                        })
                    except Exception as e:
                        logger.debug(f"保存KDJ失败: {e}")
        
        # 计算RSI
        if len(closes) >= 25:
            rsi_calc = RSICalculator()
            rsi_results = rsi_calc.calculate_rsi_batch(closes)
            for i, rsi_data in enumerate(rsi_results):
                if rsi_data.get('rsi6') is not None:
                    try:
                        session.execute(text("""
                            INSERT INTO rsi_indicators
                            (code, date, market_type, rsi6, rsi12, rsi24, created_at)
                            VALUES (:code, :date, :market_type, :rsi6, :rsi12, :rsi24, :created_at)
                            ON CONFLICT (code, date, market_type) DO UPDATE SET
                                rsi6 = EXCLUDED.rsi6, rsi12 = EXCLUDED.rsi12, rsi24 = EXCLUDED.rsi24
                        """), {
                            'code': stock_code, 'date': dates[i], 'market_type': 'HK',
                            'rsi6': rsi_data.get('rsi6'), 'rsi12': rsi_data.get('rsi12'),
                            'rsi24': rsi_data.get('rsi24'), 'created_at': datetime.now()
                        })
                    except Exception as e:
                        logger.debug(f"保存RSI失败: {e}")
        
        # 计算MA
        if len(closes) >= 5:
            ma_calc = MACalculator()
            ma_results = ma_calc.calculate_for_dataframe(pd.DataFrame({'close': closes}))
            for i, ma_data in enumerate(ma_results):
                if ma_data.get('ma5') is not None:
                    try:
                        session.execute(text("""
                            INSERT INTO ma_indicators
                            (code, date, market_type, ma5, ma10, ma20, ma30, ma60, ma120, ma200, created_at)
                            VALUES (:code, :date, :market_type, :ma5, :ma10, :ma20, :ma30, :ma60, :ma120, :ma200, :created_at)
                            ON CONFLICT (code, date, market_type) DO UPDATE SET
                                ma5 = EXCLUDED.ma5, ma10 = EXCLUDED.ma10, ma20 = EXCLUDED.ma20,
                                ma30 = EXCLUDED.ma30, ma60 = EXCLUDED.ma60, ma120 = EXCLUDED.ma120, ma200 = EXCLUDED.ma200
                        """), {
                            'code': stock_code, 'date': dates[i], 'market_type': 'HK',
                            'ma5': ma_data.get('ma5'), 'ma10': ma_data.get('ma10'), 'ma20': ma_data.get('ma20'),
                            'ma30': ma_data.get('ma30'), 'ma60': ma_data.get('ma60'), 'ma120': ma_data.get('ma120'),
                            'ma200': ma_data.get('ma200'), 'created_at': datetime.now()
                        })
                    except Exception as e:
                        logger.debug(f"保存MA失败: {e}")
        
        session.commit()
        logger.debug(f"{stock_code} 指标计算完成")
        
    except Exception as e:
        logger.error(f"计算 {stock_code} 指标失败: {e}")
        session.rollback()


def collect_data_direct(start_date: str, end_date: str, stock_codes: list = None,
                       collection_mode: str = 'specified', calculate_indicators_flag: bool = True):
    """
    直接从AKShare采集港股历史数据
    
    Args:
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
        stock_codes: 股票代码列表（可选）
        collection_mode: 采集模式 ('specified', 'all')
        calculate_indicators_flag: 是否计算技术指标
    """
    logger.info("=" * 80)
    logger.info("港股历史数据直接采集程序启动（从AKShare API）")
    logger.info(f"采集日期范围: {start_date} 至 {end_date}")
    logger.info(f"采集模式: {collection_mode}")
    logger.info(f"计算指标: {'是' if calculate_indicators_flag else '否'}")
    logger.info("=" * 80)
    
    session = SessionLocal()
    
    try:
        # 转换日期格式
        start_date_str = start_date.replace('-', '')
        end_date_str = end_date.replace('-', '')
        
        # 获取股票列表
        if collection_mode == 'all':
            stocks = get_hk_stock_list(session)
            if not stocks:
                logger.error("未能获取港股列表，采集终止")
                return
        elif collection_mode == 'specified':
            if not stock_codes:
                logger.error("指定股票采集模式需要提供股票代码列表")
                return
            # 获取股票名称
            stocks = []
            for code in stock_codes:
                result = session.execute(
                    text("SELECT name FROM stock_basic_info_hk WHERE code = :code"),
                    {"code": code}
                )
                row = result.fetchone()
                if row:
                    stocks.append({"code": code, "name": row[0]})
                else:
                    logger.warning(f"股票代码 {code} 不存在于数据库中")
        else:
            logger.error(f"不支持的采集模式: {collection_mode}")
            return
        
        logger.info(f"本次将采集 {len(stocks)} 只股票的历史数据")
        
        # 统计信息
        success_count = 0
        fail_count = 0
        total_records = 0
        
        # 逐个采集股票数据
        for idx, stock in enumerate(stocks, 1):
            stock_code = stock['code']
            stock_name = stock['name']
            
            logger.info(f"\n进度: [{idx}/{len(stocks)}] 正在采集 {stock_code} ({stock_name})...")
            
            try:
                # 从AKShare获取数据
                df = fetch_stock_data_from_akshare(stock_code, start_date_str, end_date_str)
                
                if df is not None and not df.empty:
                    # 保存到数据库
                    saved = save_to_database(stock_code, stock_name, df, session)
                    total_records += saved
                    
                    # 计算指标
                    if calculate_indicators_flag:
                        calculate_indicators(stock_code, session)
                    
                    success_count += 1
                    logger.info(f"✓ {stock_code} 采集成功，保存 {saved} 条记录")
                else:
                    fail_count += 1
                    logger.warning(f"✗ {stock_code} 无数据")
                
                # 延迟5秒，避免API限流
                if idx < len(stocks):
                    time.sleep(5)
                    
            except Exception as e:
                fail_count += 1
                logger.error(f"✗ {stock_code} 采集失败: {e}")
                continue
        
        # 输出统计信息
        logger.info("\n" + "=" * 80)
        logger.info("采集任务完成")
        logger.info(f"总股票数: {len(stocks)}")
        logger.info(f"成功: {success_count}")
        logger.info(f"失败: {fail_count}")
        logger.info(f"总记录数: {total_records}")
        logger.info(f"成功率: {success_count/len(stocks)*100:.2f}%")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"采集过程发生异常: {e}")
    finally:
        session.close()


if __name__ == '__main__':
    print("""
港股历史数据直接采集程序（从AKShare API）
==========================================

本程序直接从AKShare API获取港股历史数据，不依赖实时行情表。

使用说明:
1. 修改下方的配置参数
2. 运行程序
3. 确认后开始采集

注意事项:
- 采集间隔为5秒，避免API限流
- 会自动计算技术指标（可配置）
- 数据保存到 historical_quotes_hk 表
""")
    
    # ========== 配置采集参数 ==========
    START_DATE = '2024-01-01'
    END_DATE = '2024-01-31'
    COLLECTION_MODE = 'specified'  # 'specified' 或 'all'
    CALCULATE_INDICATORS = True    # 是否计算技术指标
    
    STOCK_CODES = [
        '00700',  # 腾讯控股
        '09988',  # 阿里巴巴-SW
        '01810',  # 小米集团-W
    ]
    # ===================================
    
    print("\n当前采集配置:")
    print(f"  日期范围: {START_DATE} 至 {END_DATE}")
    print(f"  采集模式: {COLLECTION_MODE}")
    print(f"  计算指标: {'是' if CALCULATE_INDICATORS else '否'}")
    if COLLECTION_MODE == 'specified':
        print(f"  股票代码: {', '.join(STOCK_CODES)}")
    
    confirm = input("\n是否开始采集？(y/n): ")
    if confirm.lower() == 'y':
        collect_data_direct(
            start_date=START_DATE,
            end_date=END_DATE,
            stock_codes=STOCK_CODES if COLLECTION_MODE == 'specified' else None,
            collection_mode=COLLECTION_MODE,
            calculate_indicators_flag=CALCULATE_INDICATORS
        )
    else:
        print("采集已取消")
