#!/usr/bin/env python3
"""
测试股票名称查询功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend_api.database import SessionLocal
from backend_api.models import StockBasicInfo

def test_stock_name_query():
    """测试股票名称查询"""
    print("=== 测试股票名称查询功能 ===")
    
    # 创建数据库会话
    db = SessionLocal()
    try:
        # 测试查询几个常见股票
        test_codes = ['000001', '000002', '600000', '600036', 'SZ000001', 'SH600000']
        
        print("测试股票代码查询:")
        for code in test_codes:
            stock_info = db.query(StockBasicInfo).filter(StockBasicInfo.code == code).first()
            if stock_info:
                print(f"  {code} -> {stock_info.name}")
            else:
                print(f"  {code} -> 未找到")
                
        # 测试模糊查询
        print("\n测试模糊查询:")
        stocks_like_000 = db.query(StockBasicInfo).filter(StockBasicInfo.code.like('000%')).limit(5).all()
        for stock in stocks_like_000:
            print(f"  {stock.code} -> {stock.name}")
            
    finally:
        db.close()

if __name__ == "__main__":
    test_stock_name_query()
