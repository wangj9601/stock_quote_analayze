#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证交易记录修复是否有效
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# 数据库连接
DATABASE_URL = "postgresql+psycopg2://postgres:qidianspacetime@localhost:5446/stock_analysis"

def test_fix():
    """测试修复后的交易记录"""
    
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        print("=== 验证交易记录修复 ===\n")
        
        # 查找有问题的记录（已完成但exit_time为空）
        query = text("""
            SELECT id, result_id, stock_code, trade_date, entry_time, exit_price, exit_reason, exit_time
            FROM pvfrs_trade_records_enhanced 
            WHERE exit_time IS NULL
            AND ((exit_reason IS NOT NULL AND exit_reason != '') 
            OR (exit_price > 0))
            ORDER BY created_at DESC
            LIMIT 5
        """)
        
        problematic_records = session.execute(query).fetchall()
        
        if not problematic_records:
            print("✅ 没有找到有问题的记录")
            return
        
        print(f"🔧 找到 {len(problematic_records)} 条有问题的记录")
        
        for record in problematic_records:
            print(f"\n--- 记录 ID: {record.id} ---")
            print(f"股票代码: {record.stock_code}")
            print(f"交易日期: {record.trade_date}")
            print(f"入场时间: {record.entry_time}")
            print(f"退出原因: {record.exit_reason}")
            print(f"出场价格: {record.exit_price}")
            print(f"出场时间: {record.exit_time}")
            
            # 如果有 trade_date，尝试修复
            if record.trade_date and not record.exit_time:
                try:
                    exit_dt = datetime.combine(record.trade_date, datetime.min.time())
                    exit_time_str = exit_dt.isoformat()
                    
                    print(f"🔧 尝试修复: {record.trade_date} -> {exit_time_str}")
                    
                    # 执行修复
                    update_query = text("""
                        UPDATE pvfrs_trade_records_enhanced 
                        SET exit_time = :exit_time
                        WHERE id = :id
                    """)
                    
                    session.execute(update_query, {
                        'exit_time': exit_time_str,
                        'id': record.id
                    })
                    
                    print(f"✅ 修复成功")
                    
                except Exception as e:
                    print(f"❌ 修复失败: {str(e)}")
        
        # 提交所有修复
        session.commit()
        print(f"\n🎉 修复完成")
        
    except Exception as e:
        print(f"❌ 验证失败: {str(e)}")
        session.rollback()
        import traceback
        traceback.print_exc()
    
    finally:
        session.close()

if __name__ == "__main__":
    test_fix()
