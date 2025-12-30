#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
均值频率共振指标(PVFRS)回溯计算脚本
用于手动触发计算，填充新添加的 bias 字段
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import logging
import argparse
from sqlalchemy import text

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend_core.database.db import SessionLocal
from backend_core.data_collectors.akshare.historical_collector import AkshareHistoricalCollector
from backend_core.data_collectors.akshare.hk_historical import HKHistoricalQuoteCollector

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def backfill_pvfrs(market_type, code=None, days=60):
    session = SessionLocal()
    try:
        # 确保列存在
        try:
            session.execute(text('ALTER TABLE mean_frequency_resonance_indicators ADD COLUMN bias REAL'))
            session.commit()
            logger.info("成功添加 bias 列")
        except Exception as e:
            logger.info(f"bias 列可能已存在: {e}")
            session.rollback()

        # 计算日期范围
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        logger.info(f"开始回溯 PVFRS 指标: 市场={market_type}, 代码={code if code else '全部'}, 范围={start_date}到{end_date}")

        if market_type == 'CN':
            collector = AkshareHistoricalCollector()
            if code:
                stocks = [code]
            else:
                # 获取所有股票代码
                result = session.execute(text("SELECT DISTINCT code FROM historical_quotes"))
                stocks = [row[0] for row in result.fetchall()]
            
            logger.info(f"共有 {len(stocks)} 只股票需要处理")
            for i, stock_code in enumerate(stocks):
                logger.info(f"[{i+1}/{len(stocks)}] 处理 A股 {stock_code}")
                try:
                    # 调用 collector 内部方法进行计算和保存
                    # 注意：这里我们直接调用 _calculate_and_save_mean_frequency
                    # 它会自动处理覆盖旧数据（ON CONFLICT update）
                    collector._calculate_and_save_mean_frequency(stock_code, start_date, end_date)
                except Exception as e:
                    logger.error(f"处理 {stock_code} 失败: {e}")

        elif market_type == 'HK':
            collector = HKHistoricalQuoteCollector()
            if code:
                stocks = [code]
            else:
                result = session.execute(text("SELECT DISTINCT code FROM historical_quotes_hk"))
                stocks = [row[0] for row in result.fetchall()]
            
            logger.info(f"共有 {len(stocks)} 只股票需要处理")
            # 港股是按日期批量处理的，但为了复用 _calculate_and_save_mean_frequency_hk，我们需要按代码分组或者修改逻辑
            # 看代码 _calculate_and_save_mean_frequency_hk 是接受股票列表和单个目标日期的
            # 这里的回溯有点麻烦，因为它设计为按天处理。
            # 为了简单起见，我们循环每一天调用它？或者我们直接修改该方法支持日期范围？
            # 实际上，我们可以循环处理每只股票，然后模拟计算
            
            # 由于港股方法 _calculate_and_save_mean_frequency_hk 是针对"单个目标日期"设计的
            # 我们这里为了回溯一段历史，最好是按天循环
            
            current_date = datetime.strptime(start_date, '%Y-%m-%d')
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
            
            while current_date <= end_date_obj:
                target_date = current_date.strftime('%Y-%m-%d')
                logger.info(f"处理港股日期: {target_date}")
                try:
                    # 每次处理一批股票
                    batch_size = 50
                    for i in range(0, len(stocks), batch_size):
                        batch = stocks[i:i+batch_size]
                        collector._calculate_and_save_mean_frequency_hk(batch, target_date, session)
                except Exception as e:
                    logger.error(f"处理日期 {target_date} 失败: {e}")
                
                current_date += timedelta(days=1)

    except Exception as e:
        logger.error(f"回溯失败: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='PVFRS 指标回溯')
    parser.add_argument('--market', type=str, required=True, choices=['CN', 'HK'], help='市场类型')
    parser.add_argument('--code', type=str, help='股票代码(可选)')
    parser.add_argument('--days', type=int, default=60, help='回溯天数')
    
    args = parser.parse_args()
    backfill_pvfrs(args.market, args.code, args.days)
