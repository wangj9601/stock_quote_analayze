#!/usr/bin/env python3
"""检查PVFRS监控指标表是否存在"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from sqlalchemy import text
    from backend_api.database import get_db
    
    print("正在检查PVFRS监控指标表...")
    
    # 获取数据库连接
    db = next(get_db())
    
    # 检查表是否存在
    try:
        # 尝试查询表结构
        result = db.execute(text("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_name = 'pvfrs_monitor_metrics'
        """))
        table_exists = result.scalar() > 0
        
        if table_exists:
            print("✅ 表 pvfrs_monitor_metrics 存在")
            
            # 检查记录数
            count_result = db.execute(text("SELECT COUNT(*) FROM pvfrs_monitor_metrics"))
            count = count_result.scalar()
            print(f"📊 当前记录数: {count}")
            
            if count == 0:
                print("💡 表为空，监控服务现在可以正常记录指标了")
            else:
                print("📋 表中有数据，监控服务正在正常工作")
                
        else:
            print("❌ 表 pvfrs_monitor_metrics 不存在")
            
    except Exception as e:
        print(f"❌ 检查表失败: {str(e)}")
        
    db.close()
    
except Exception as e:
    print(f"❌ 连接数据库失败: {str(e)}")
