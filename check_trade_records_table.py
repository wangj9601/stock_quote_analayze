#!/usr/bin/env python3
"""检查PVFRS交易记录表字段是否存在"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from sqlalchemy import text
    from backend_api.database import get_db
    
    print("正在检查PVFRS交易记录表字段...")
    
    # 获取数据库连接
    db = next(get_db())
    
    # 检查表是否存在
    try:
        # 检查表是否存在
        result = db.execute(text("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_name = 'pvfrs_trade_records_enhanced'
        """))
        table_exists = result.scalar() > 0
        
        if table_exists:
            print("✅ 表 pvfrs_trade_records_enhanced 存在")
            
            # 检查特定字段是否存在
            fields_to_check = ['entry_date', 'exit_time', 'holding_period']
            
            for field_name in fields_to_check:
                result = db.execute(text("""
                    SELECT COUNT(*) FROM information_schema.columns 
                    WHERE table_name = 'pvfrs_trade_records_enhanced' AND column_name = :field_name
                """), {'field_name': field_name})
                field_exists = result.scalar() > 0
                
                if field_exists:
                    print(f"✅ 字段 {field_name}: 存在")
                else:
                    print(f"❌ 字段 {field_name}: 不存在")
            
            # 尝试查询记录数
            count_result = db.execute(text("SELECT COUNT(*) FROM pvfrs_trade_records_enhanced"))
            count = count_result.scalar()
            print(f"📊 当前记录数: {count}")
            
        else:
            print("❌ 表 pvfrs_trade_records_enhanced 不存在")
            
    except Exception as e:
        print(f"❌ 检查失败: {str(e)}")
        
    db.close()
    
except Exception as e:
    print(f"❌ 连接数据库失败: {str(e)}")
