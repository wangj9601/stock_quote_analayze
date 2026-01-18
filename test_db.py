#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend_api.database import get_db
from models import StockBasicInfo

def test_database():
    """测试数据库连接和股票数据"""
    try:
        print("正在连接数据库...")
        db = next(get_db())
        
        # 查询总股票数
        total_stocks = db.query(StockBasicInfo).count()
        print(f"数据库中总股票数: {total_stocks}")
        
        # 查询A股股票数
        a_stocks = db.query(StockBasicInfo).filter(StockBasicInfo.market == 'A股').count()
        print(f"A股股票数: {a_stocks}")
        
        # 查看市场类型分布
        markets = db.query(StockBasicInfo.market).distinct().all()
        print(f"市场类型: {[m[0] for m in markets]}")
        
        # 查看前几个股票样本
        sample = db.query(StockBasicInfo).limit(5).all()
        print("\n前5个股票样本:")
        for stock in sample:
            print(f"  {stock.code} - {stock.name} - 市场: {stock.market}")
        
        db.close()
        print("数据库测试完成")
        
    except Exception as e:
        print(f"数据库查询错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_database()
