#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend_core.data_collectors.akshare.realtime_stock_notice_report_ak import AkshareStockNoticeReportCollector
from backend_core.config.config import DATA_COLLECTORS
import pandas as pd
import logging
from datetime import datetime

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_stock_notice_report.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def test_notice_collector():
    """测试A股公告数据采集器"""
    logger.info("=== 开始测试A股公告数据采集器 ===")
    
    try:
        # 初始化采集器
        collector = AkshareStockNoticeReportCollector(DATA_COLLECTORS.get('akshare', {}))
        logger.info("采集器初始化成功")
        
        # 测试采集当日公告数据
        logger.info("测试采集当日公告数据...")
        result = collector.collect_stock_notices(symbol="全部")
        if result:
            logger.info("✅ 当日公告数据采集成功")
        else:
            logger.warning("⚠️ 当日公告数据采集失败")
        
        # 测试采集特定类型的公告
        logger.info("测试采集重大事项公告...")
        result = collector.collect_stock_notices(symbol="重大事项")
        if result:
            logger.info("✅ 重大事项公告采集成功")
        else:
            logger.warning("⚠️ 重大事项公告采集失败")
        
        # 测试查询功能
        logger.info("测试查询功能...")
        
        # 按股票代码查询
        df = collector.get_notices_by_stock("000001", limit=10)
        logger.info(f"股票000001的公告数据：{len(df)}条")
        if not df.empty:
            logger.info(f"最新公告：{df.iloc[0]['notice_title']}")
        
        # 按日期查询
        today = datetime.now().strftime('%Y-%m-%d')
        df = collector.get_notices_by_date(today, limit=10)
        logger.info(f"今日公告数据：{len(df)}条")
        
        logger.info("=== A股公告数据采集器测试完成 ===")
        
    except Exception as e:
        logger.error(f"测试过程中出错: {str(e)}", exc_info=True)

def test_database_structure():
    """测试数据库表结构"""
    logger.info("=== 测试数据库表结构 ===")
    
    try:
        collector = AkshareStockNoticeReportCollector(DATA_COLLECTORS.get('akshare', {}))
        
        # 初始化数据库（创建表）
        conn = collector._init_db()
        cursor = conn.cursor()
        
        # 查看表结构
        cursor.execute("PRAGMA table_info(stock_notice_report)")
        columns = cursor.fetchall()
        logger.info("stock_notice_report表结构：")
        for col in columns:
            logger.info(f"  {col[1]} {col[2]} {'NOT NULL' if col[3] else 'NULL'}")
        
        # 查看索引
        cursor.execute("PRAGMA index_list(stock_notice_report)")
        indexes = cursor.fetchall()
        logger.info("索引列表：")
        for idx in indexes:
            logger.info(f"  {idx[1]}")
        
        conn.close()
        logger.info("=== 数据库表结构测试完成 ===")
        
    except Exception as e:
        logger.error(f"数据库结构测试出错: {str(e)}", exc_info=True)

if __name__ == "__main__":
    logger.info("开始运行A股公告数据采集测试...")
    
    # 测试数据库结构
    test_database_structure()
    
    # 测试采集功能
    test_notice_collector()
    
    logger.info("所有测试完成") 