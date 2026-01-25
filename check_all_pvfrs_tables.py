#!/usr/bin/env python3
"""检查所有PVFRS相关的表是否存在"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from sqlalchemy import text
    from backend_api.database import get_db
    
    print("正在检查所有PVFRS相关表...")
    
    # 获取数据库连接
    db = next(get_db())
    
    # 需要检查的表列表
    tables_to_check = [
        'pvfrs_strategy_configs',
        'pvfrs_backtest_tasks_enhanced',
        'pvfrs_backtest_results_enhanced',
        'pvfrs_trade_records_enhanced',
        'pvfrs_equity_curves_enhanced',
        'pvfrs_monitor_metrics',
        'pvfrs_alerts'
    ]
    
    all_tables_exist = True
    
    for table_name in tables_to_check:
        try:
            # 检查表是否存在
            result = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_name = :table_name
            """), {'table_name': table_name})
            table_exists = result.scalar() > 0
            
            if table_exists:
                # 检查记录数
                count_result = db.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                count = count_result.scalar()
                print(f"✅ {table_name}: 存在 ({count} 条记录)")
            else:
                print(f"❌ {table_name}: 不存在")
                all_tables_exist = False
                
        except Exception as e:
            print(f"❌ {table_name}: 检查失败 - {str(e)}")
            all_tables_exist = False
    
    print("\n" + "="*50)
    if all_tables_exist:
        print("🎉 所有PVFRS表都存在，系统可以正常运行！")
    else:
        print("⚠️ 部分表缺失，可能需要运行迁移脚本")
    
    db.close()
    
except Exception as e:
    print(f"❌ 连接数据库失败: {str(e)}")
