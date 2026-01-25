#!/usr/bin/env python3
"""最终检查所有PVFRS表的完整性"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from sqlalchemy import text
    from backend_api.database import get_db
    
    print("🔍 最终检查所有PVFRS表的完整性...")
    print("="*60)
    
    # 获取数据库连接
    db = next(get_db())
    
    # 需要检查的表和字段
    tables_and_fields = {
        'pvfrs_strategy_configs': ['id', 'name', 'description', 'config_params', 'is_active'],
        'pvfrs_backtest_tasks_enhanced': ['id', 'task_id', 'task_name', 'strategy_config_id', 'mode', 'stock_codes', 'total_stocks', 'processed_stocks'],
        'pvfrs_backtest_results_enhanced': ['id', 'task_id', 'stock_code', 'report_id', 'config_snapshot', 'summary_data'],
        'pvfrs_trade_records_enhanced': ['id', 'result_id', 'stock_code', 'trade_date', 'entry_date', 'exit_time', 'holding_period'],
        'pvfrs_equity_curves_enhanced': ['id', 'result_id', 'stock_code', 'curve_date', 'equity', 'portfolio_value'],
        'pvfrs_monitor_metrics': ['id', 'timestamp', 'metric_name', 'metric_value', 'tags'],
        'pvfrs_alerts': ['id', 'level', 'type', 'title', 'message', 'timestamp', 'severity', 'acknowledged']
    }
    
    all_tables_complete = True
    
    for table_name, required_fields in tables_and_fields.items():
        print(f"\n📋 检查表: {table_name}")
        
        try:
            # 检查表是否存在
            result = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_name = :table_name
            """), {'table_name': table_name})
            table_exists = result.scalar() > 0
            
            if not table_exists:
                print(f"   ❌ 表不存在")
                all_tables_complete = False
                continue
            
            # 检查字段
            missing_fields = []
            for field_name in required_fields:
                result = db.execute(text("""
                    SELECT COUNT(*) FROM information_schema.columns 
                    WHERE table_name = :table_name AND column_name = :field_name
                """), {'table_name': table_name, 'field_name': field_name})
                field_exists = result.scalar() > 0
                
                if not field_exists:
                    missing_fields.append(field_name)
            
            # 检查记录数
            count_result = db.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            count = count_result.scalar()
            
            if missing_fields:
                print(f"   ❌ 缺失字段: {', '.join(missing_fields)}")
                all_tables_complete = False
            else:
                print(f"   ✅ 所有必需字段存在 ({count} 条记录)")
                
        except Exception as e:
            print(f"   ❌ 检查失败: {str(e)}")
            all_tables_complete = False
    
    print("\n" + "="*60)
    if all_tables_complete:
        print("🎉 所有PVFRS表结构完整，系统可以完全正常运行！")
        print("\n💡 系统现在支持以下功能:")
        print("   ✅ 策略配置管理")
        print("   ✅ 回测任务管理")
        print("   ✅ 回测结果存储")
        print("   ✅ 交易记录追踪")
        print("   ✅ 收益曲线分析")
        print("   ✅ 系统监控指标")
        print("   ✅ 告警系统")
        print("\n🚀 可以开始使用PVFRS系统的所有功能了！")
    else:
        print("⚠️ 部分表结构不完整，可能需要进一步修复")
    
    db.close()
    
except Exception as e:
    print(f"❌ 连接数据库失败: {str(e)}")
