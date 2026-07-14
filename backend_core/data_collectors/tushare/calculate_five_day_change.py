#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
5日涨跌幅计算脚本
支持手动触发和批量计算历史行情数据的5日涨跌幅
"""

import argparse
import logging
from backend_core.logging_utils import should_log_to_file, resolve_log_file
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from backend_core.database.db import SessionLocal
from backend_core.data_collectors.tushare.five_day_change_calculator import FiveDayChangeCalculator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(resolve_log_file('five_day_change_calculation.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def calculate_for_date(target_date: str) -> bool:
    """
    为指定日期计算5日涨跌幅
    
    Args:
        target_date: 目标日期 (YYYY-MM-DD)
        
    Returns:
        bool: 计算是否成功
    """
    try:
        logger.info(f"开始为日期 {target_date} 计算5日涨跌幅")
        
        session = SessionLocal()
        calculator = FiveDayChangeCalculator(session)
        
        result = calculator.calculate_for_date(target_date)
        
        logger.info(f"日期 {target_date} 的5日涨跌幅计算完成:")
        logger.info(f"  总计股票: {result['total']}")
        logger.info(f"  成功计算: {result['success']}")
        logger.info(f"  失败计算: {result['failed']}")
        
        if result['failed'] > 0:
            logger.warning("部分股票计算失败:")
            for detail in result['details']:
                logger.warning(f"  - {detail}")
        
        session.close()
        return result['failed'] == 0
        
    except Exception as e:
        logger.error(f"为日期 {target_date} 计算5日涨跌幅失败: {e}")
        return False

def calculate_for_date_range(start_date: str, end_date: str) -> bool:
    """
    为指定日期范围计算5日涨跌幅
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        
    Returns:
        bool: 计算是否成功
    """
    try:
        logger.info(f"开始为日期范围 {start_date} 到 {end_date} 计算5日涨跌幅")
        
        session = SessionLocal()
        calculator = FiveDayChangeCalculator(session)
        
        result = calculator.calculate_batch_for_date_range(start_date, end_date)
        
        logger.info(f"日期范围 {start_date} 到 {end_date} 的5日涨跌幅计算完成:")
        logger.info(f"  总计日期: {result['total_dates']}")
        logger.info(f"  总计成功: {result['total_success']}")
        logger.info(f"  总计失败: {result['total_failed']}")
        
        if result['total_failed'] > 0:
            logger.warning("部分计算失败:")
            for detail in result['details']:
                logger.warning(f"  - {detail}")
        
        session.close()
        return result['total_failed'] == 0
        
    except Exception as e:
        logger.error(f"为日期范围 {start_date} 到 {end_date} 计算5日涨跌幅失败: {e}")
        return False

def get_calculation_status(target_date: str) -> None:
    """
    获取指定日期的计算状态
    
    Args:
        target_date: 目标日期 (YYYY-MM-DD)
    """
    try:
        logger.info(f"获取日期 {target_date} 的5日涨跌幅计算状态")
        
        session = SessionLocal()
        calculator = FiveDayChangeCalculator(session)
        
        status = calculator.get_calculation_status(target_date)
        
        logger.info(f"日期 {target_date} 的计算状态:")
        logger.info(f"  总记录数: {status['total_records']}")
        logger.info(f"  已计算记录数: {status['calculated_records']}")
        logger.info(f"  待计算记录数: {status['pending_records']}")
        logger.info(f"  完成率: {status['completion_rate']}%")
        
        if 'error' in status:
            logger.error(f"获取状态时出错: {status['error']}")
        
        session.close()
        
    except Exception as e:
        logger.error(f"获取日期 {target_date} 的计算状态失败: {e}")

def calculate_recent_days(days: int) -> bool:
    """
    计算最近N天的5日涨跌幅
    
    Args:
        days: 天数
        
    Returns:
        bool: 计算是否成功
    """
    try:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        logger.info(f"计算最近 {days} 天 ({start_date} 到 {end_date}) 的5日涨跌幅")
        
        return calculate_for_date_range(start_date, end_date)
        
    except Exception as e:
        logger.error(f"计算最近 {days} 天的5日涨跌幅失败: {e}")
        return False

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='5日涨跌幅计算工具')
    parser.add_argument('--mode', choices=['date', 'range', 'recent', 'status'], required=True,
                       help='计算模式: date(单日期), range(日期范围), recent(最近N天), status(查看状态)')
    parser.add_argument('--date', type=str, help='目标日期 (YYYY-MM-DD)')
    parser.add_argument('--start-date', type=str, help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--days', type=int, help='最近天数')
    
    args = parser.parse_args()
    
    try:
        if args.mode == 'date':
            if not args.date:
                logger.error("单日期模式需要指定 --date 参数")
                return False
            return calculate_for_date(args.date)
            
        elif args.mode == 'range':
            if not args.start_date or not args.end_date:
                logger.error("日期范围模式需要指定 --start-date 和 --end-date 参数")
                return False
            return calculate_for_date_range(args.start_date, args.end_date)
            
        elif args.mode == 'recent':
            if not args.days:
                logger.error("最近N天模式需要指定 --days 参数")
                return False
            return calculate_recent_days(args.days)
            
        elif args.mode == 'status':
            if not args.date:
                logger.error("状态查看模式需要指定 --date 参数")
                return False
            get_calculation_status(args.date)
            return True
            
    except Exception as e:
        logger.error(f"执行失败: {e}")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
