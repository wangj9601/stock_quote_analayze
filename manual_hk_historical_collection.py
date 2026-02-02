"""
港股历史数据手动采集程序
用于手动采集指定日期范围和股票代码的港股历史数据
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
import logging

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend_core.data_collectors.akshare.hk_historical import HKHistoricalQuoteCollector
from backend_core.database.db import SessionLocal
from sqlalchemy import text


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('manual_hk_collection.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_trading_dates(start_date: str, end_date: str) -> list:
    """
    生成日期范围内的所有日期列表（不过滤交易日，由采集器自动处理）
    
    Args:
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
        
    Returns:
        日期列表，格式为 YYYYMMDD
    """
    dates = []
    current = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    
    while current <= end:
        # 跳过周六和周日
        if current.weekday() < 5:  # 0-4 代表周一到周五
            dates.append(current.strftime('%Y%m%d'))
        current += timedelta(days=1)
    
    return dates


def get_hk_stock_list(session) -> list:
    """
    从数据库获取所有港股代码
    
    Args:
        session: 数据库会话
        
    Returns:
        港股代码列表
    """
    try:
        result = session.execute(text("SELECT code FROM stock_basic_info_hk ORDER BY code"))
        codes = [row[0] for row in result.fetchall()]
        logger.info(f"从数据库获取到 {len(codes)} 只港股")
        return codes
    except Exception as e:
        logger.error(f"获取港股列表失败: {e}")
        return []


def get_watchlist_stocks(session) -> list:
    """
    从数据库获取自选股列表
    
    Args:
        session: 数据库会话
        
    Returns:
        自选股代码列表
    """
    try:
        result = session.execute(text("SELECT DISTINCT stock_code FROM watchlist"))
        codes = [row[0] for row in result.fetchall()]
        logger.info(f"从数据库获取到 {len(codes)} 只自选股")
        return codes
    except Exception as e:
        logger.error(f"获取自选股列表失败: {e}")
        return []


def validate_stock_codes(stock_codes: list, session) -> list:
    """
    验证股票代码是否存在于数据库中
    
    Args:
        stock_codes: 待验证的股票代码列表
        session: 数据库会话
        
    Returns:
        有效的股票代码列表
    """
    valid_codes = []
    for code in stock_codes:
        try:
            result = session.execute(
                text("SELECT code FROM stock_basic_info_hk WHERE code = :code"),
                {"code": code}
            )
            if result.fetchone():
                valid_codes.append(code)
            else:
                logger.warning(f"股票代码 {code} 不存在于数据库中，已跳过")
        except Exception as e:
            logger.error(f"验证股票代码 {code} 时出错: {e}")
    
    return valid_codes


def collect_data(start_date: str, end_date: str, stock_codes: list = None, 
                 collection_mode: str = 'specified'):
    """
    采集港股历史数据
    
    Args:
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
        stock_codes: 股票代码列表（可选）
        collection_mode: 采集模式
            - 'specified': 指定股票采集（需要提供stock_codes）
            - 'all': 全量采集（采集数据库中所有港股）
            - 'watchlist': 自选股采集
    """
    logger.info("=" * 80)
    logger.info("港股历史数据手动采集程序启动")
    logger.info(f"采集日期范围: {start_date} 至 {end_date}")
    logger.info(f"采集模式: {collection_mode}")
    logger.info("=" * 80)
    
    # 初始化数据库会话
    session = SessionLocal()
    
    try:
        # 根据采集模式确定股票列表
        if collection_mode == 'all':
            stock_codes = get_hk_stock_list(session)
            if not stock_codes:
                logger.error("未能获取港股列表，采集终止")
                return
        elif collection_mode == 'watchlist':
            stock_codes = get_watchlist_stocks(session)
            if not stock_codes:
                logger.error("未能获取自选股列表，采集终止")
                return
        elif collection_mode == 'specified':
            if not stock_codes:
                logger.error("指定股票采集模式需要提供股票代码列表")
                return
            # 验证股票代码
            stock_codes = validate_stock_codes(stock_codes, session)
            if not stock_codes:
                logger.error("没有有效的股票代码，采集终止")
                return
        else:
            logger.error(f"不支持的采集模式: {collection_mode}")
            return
        
        logger.info(f"本次将采集 {len(stock_codes)} 只股票的历史数据")
        
        # 生成日期列表
        dates = get_trading_dates(start_date, end_date)
        logger.info(f"共需采集 {len(dates)} 个交易日的数据")
        
        # 初始化采集器
        collector = HKHistoricalQuoteCollector()
        
        # 统计信息
        success_count = 0
        fail_count = 0
        total_tasks = len(dates)
        
        # 按日期采集数据
        for idx, date_str in enumerate(dates, 1):
            logger.info(f"\n进度: [{idx}/{total_tasks}] 正在采集 {date_str} 的数据...")
            
            try:
                # 调用采集器采集数据
                # 注意：HKHistoricalQuoteCollector.collect_historical_quotes 
                # 会从 stock_realtime_quote_hk 表读取数据并同步到历史表
                result = collector.collect_historical_quotes(date_str)
                
                if result:
                    success_count += 1
                    logger.info(f"✓ {date_str} 数据采集成功")
                else:
                    fail_count += 1
                    logger.warning(f"✗ {date_str} 数据采集失败或无数据")
                    
            except Exception as e:
                fail_count += 1
                logger.error(f"✗ {date_str} 数据采集异常: {e}")
                continue
        
        # 输出统计信息
        logger.info("\n" + "=" * 80)
        logger.info("采集任务完成")
        logger.info(f"总任务数: {total_tasks}")
        logger.info(f"成功: {success_count}")
        logger.info(f"失败: {fail_count}")
        logger.info(f"成功率: {success_count/total_tasks*100:.2f}%")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"采集过程发生异常: {e}")
    finally:
        session.close()


def print_usage():
    """打印使用说明"""
    print("""
港股历史数据手动采集程序
========================

使用方法:
    python manual_hk_historical_collection.py

采集模式:
    1. 指定股票采集 (specified)
       - 需要在代码中指定股票代码列表
       
    2. 全量采集 (all)
       - 采集数据库中所有港股的历史数据
       
    3. 自选股采集 (watchlist)
       - 采集自选股列表中的股票

注意事项:
    1. 本程序从 stock_realtime_quote_hk 表读取数据并同步到历史表
    2. 需要先确保实时行情数据已采集
    3. 采集过程会自动计算各项技术指标（MACD、KDJ、RSI、MA、BOLL、MAVOL、PVFRS）
    4. 仅对自选股中的股票计算技术指标
    5. 日志文件保存在: manual_hk_collection.log

示例:
    # 采集指定股票的历史数据
    collect_data(
        start_date='2024-01-01',
        end_date='2024-01-31',
        stock_codes=['00700', '09988', '01810'],
        collection_mode='specified'
    )
    
    # 采集所有港股的历史数据
    collect_data(
        start_date='2024-01-01',
        end_date='2024-01-31',
        collection_mode='all'
    )
    
    # 采集自选股的历史数据
    collect_data(
        start_date='2024-01-01',
        end_date='2024-01-31',
        collection_mode='watchlist'
    )
""")


if __name__ == '__main__':
    # 打印使用说明
    print_usage()
    
    # ========== 配置采集参数 ==========
    # 请根据需要修改以下参数
    
    # 日期范围
    START_DATE = '2024-01-01'  # 开始日期
    END_DATE = '2024-01-31'    # 结束日期
    
    # 采集模式选择
    # 'specified': 指定股票采集
    # 'all': 全量采集
    # 'watchlist': 自选股采集
    COLLECTION_MODE = 'specified'
    
    # 指定股票代码列表（仅在 collection_mode='specified' 时需要）
    STOCK_CODES = [
        '00700',  # 腾讯控股
        '09988',  # 阿里巴巴-SW
        '01810',  # 小米集团-W
    ]
    
    # ===================================
    
    # 确认采集参数
    print("\n当前采集配置:")
    print(f"  日期范围: {START_DATE} 至 {END_DATE}")
    print(f"  采集模式: {COLLECTION_MODE}")
    if COLLECTION_MODE == 'specified':
        print(f"  股票代码: {', '.join(STOCK_CODES)}")
    
    # 用户确认
    confirm = input("\n是否开始采集？(y/n): ")
    if confirm.lower() == 'y':
        # 开始采集
        collect_data(
            start_date=START_DATE,
            end_date=END_DATE,
            stock_codes=STOCK_CODES if COLLECTION_MODE == 'specified' else None,
            collection_mode=COLLECTION_MODE
        )
    else:
        print("采集已取消")
