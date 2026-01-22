#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 sa_to_dict 函数的转换过程
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# 数据库连接
DATABASE_URL = "postgresql+psycopg2://postgres:qidianspacetime@localhost:5446/stock_analysis"

def test_sa_to_dict():
    """测试 sa_to_dict 转换过程"""
    
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        print("=== 测试 sa_to_dict 转换过程 ===\n")
        
        # 查询一条已完成的交易记录
        query = text("""
            SELECT id, result_id, stock_code, entry_time, exit_time, 
                   entry_price, exit_price, exit_reason
            FROM pvfrs_trade_records_enhanced 
            WHERE exit_reason IS NOT NULL AND exit_reason != ''
            AND result_id = 8
            LIMIT 3
        """)
        
        records = session.execute(query).fetchall()
        
        print(f"找到 {len(records)} 条已完成的交易记录\n")
        
        # 手动实现 sa_to_dict 逻辑
        for i, record in enumerate(records, 1):
            print(f"--- 记录 {i} (ID: {record.id}) ---")
            print(f"原始数据:")
            print(f"  entry_time: {record.entry_time} (类型: {type(record.entry_time)})")
            print(f"  exit_time: {record.exit_time} (类型: {type(record.exit_time)})")
            print(f"  exit_price: {record.exit_price}")
            print(f"  exit_reason: {record.exit_reason}")
            
            # 模拟 sa_to_dict 转换
            trade_dict = {}
            
            # 处理 entry_time
            if isinstance(record.entry_time, datetime):
                trade_dict['entry_time'] = record.entry_time.isoformat() if record.entry_time else None
            else:
                trade_dict['entry_time'] = record.entry_time
            
            # 处理 exit_time
            if isinstance(record.exit_time, datetime):
                trade_dict['exit_time'] = record.exit_time.isoformat() if record.exit_time else None
            else:
                trade_dict['exit_time'] = record.exit_time
            
            # 处理其他字段
            trade_dict['exit_price'] = float(record.exit_price) if record.exit_price else 0
            trade_dict['exit_reason'] = record.exit_reason
            
            print(f"\n转换后数据:")
            print(f"  entry_time: {trade_dict['entry_time']} (类型: {type(trade_dict['entry_time'])})")
            print(f"  exit_time: {trade_dict['exit_time']} (类型: {type(trade_dict['exit_time'])})")
            print(f"  exit_price: {trade_dict['exit_price']}")
            print(f"  exit_reason: {trade_dict['exit_reason']}")
            
            # 判断交易状态
            is_completed = bool(trade_dict['exit_reason']) or (trade_dict['exit_price'] and trade_dict['exit_price'] > 0)
            frontend_display = '已完成' if trade_dict['exit_time'] else '持仓中'
            
            print(f"\n状态分析:")
            print(f"  交易已完成: {is_completed}")
            print(f"  前端显示: {frontend_display}")
            
            if is_completed and not trade_dict['exit_time']:
                print("  ⚠️  问题: 交易已完成但 exit_time 为空")
            elif is_completed and trade_dict['exit_time']:
                print("  ✅ 正常: 交易已完成且 exit_time 有值")
            
            print()
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        session.close()

if __name__ == "__main__":
    test_sa_to_dict()
