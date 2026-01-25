#!/usr/bin/env python3
"""检查trade_date字段的约束状态"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from sqlalchemy import text
    from backend_api.database import get_db
    
    print("正在检查trade_date字段的约束状态...")
    
    # 获取数据库连接
    db = next(get_db())
    
    try:
        # 检查trade_date字段是否允许NULL
        result = db.execute(text("""
            SELECT is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'pvfrs_trade_records_enhanced' AND column_name = 'trade_date'
        """))
        is_nullable = result.scalar()
        
        if is_nullable == 'YES':
            print("✅ trade_date字段允许NULL值")
        else:
            print("❌ trade_date字段不允许NULL值")
        
        # 检查当前记录数
        count_result = db.execute(text("SELECT COUNT(*) FROM pvfrs_trade_records_enhanced"))
        count = count_result.scalar()
        print(f"📊 当前记录数: {count}")
        
        # 如果有记录，检查是否有NULL的trade_date
        if count > 0:
            null_count_result = db.execute(text("""
                SELECT COUNT(*) FROM pvfrs_trade_records_enhanced 
                WHERE trade_date IS NULL
            """))
            null_count = null_count_result.scalar()
            print(f"📊 trade_date为NULL的记录数: {null_count}")
        
    except Exception as e:
        print(f"❌ 检查失败: {str(e)}")
        
    db.close()
    
except Exception as e:
    print(f"❌ 连接数据库失败: {str(e)}")
