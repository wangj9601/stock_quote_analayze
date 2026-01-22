#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查数据库中的实际交易记录数据
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 数据库连接
DATABASE_URL = "postgresql+psycopg2://postgres:qidianspacetime@localhost:5446/stock_analysis"

def check_database_data():
    """检查数据库中的实际数据"""
    
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        print("=== 检查数据库中的交易记录 ===\n")
        
        # 查询所有交易记录
        query = text("""
            SELECT id, result_id, stock_code, trade_date, entry_time, exit_time, 
                   entry_price, exit_price, exit_reason, created_at
            FROM pvfrs_trade_records_enhanced 
            WHERE stock_code = '300398'
            ORDER BY created_at DESC
            LIMIT 10
        """)
        
        records = session.execute(query).fetchall()
        
        print(f"找到 {len(records)} 条记录\n")
        
        for i, record in enumerate(records, 1):
            print(f"--- 记录 {i} ---")
            print(f"ID: {record.id}")
            print(f"结果ID: {record.result_id}")
            print(f"股票代码: {record.stock_code}")
            print(f"交易日期: {record.trade_date}")
            print(f"入场时间: {record.entry_time}")
            print(f"出场时间: {record.exit_time}")
            print(f"入场价格: {record.entry_price}")
            print(f"出场价格: {record.exit_price}")
            print(f"退出原因: {record.exit_reason}")
            print(f"创建时间: {record.created_at}")
            
            # 判断交易状态
            is_completed = bool(record.exit_reason) or (record.exit_price and record.exit_price > 0)
            status = "已完成" if is_completed else "持仓中"
            print(f"交易状态: {status}")
            
            if is_completed and not record.exit_time:
                print("⚠️  问题: 交易已完成但 exit_time 为空")
            elif not is_completed and record.exit_time:
                print("⚠️  问题: 交易未完成但 exit_time 有值")
            elif is_completed and record.exit_time:
                print("✅ 正常: 交易已完成且 exit_time 有值")
            else:
                print("ℹ️  正常: 交易未完成且 exit_time 为空")
            
            print()
        
        # 检查是否有 trade_date 为空的记录
        null_trade_date_query = text("""
            SELECT COUNT(*) as count
            FROM pvfrs_trade_records_enhanced 
            WHERE trade_date IS NULL
        """)
        
        null_count = session.execute(null_trade_date_query).scalar()
        print(f"trade_date 为空的记录数: {null_count}")
        
    except Exception as e:
        print(f"❌ 检查失败: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        session.close()

if __name__ == "__main__":
    check_database_data()
