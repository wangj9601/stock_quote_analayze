#!/usr/bin/env python3
"""检查PVFRS表是否存在"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from backend_api.models.pvfrs_enhanced import PVFRSBacktestResultEnhanced
    from backend_api.database import get_db
    
    print("正在检查数据库表...")
    
    # 获取数据库连接
    db = next(get_db())
    
    # 检查表是否存在并获取记录数
    try:
        count = db.query(PVFRSBacktestResultEnhanced).count()
        print(f"✅ 表 pvfrs_backtest_results_enhanced 存在")
        print(f"📊 当前记录数: {count}")
        
        if count == 0:
            print("💡 表为空，需要运行回测任务来生成数据")
        else:
            print("📋 表中有数据，报告列表应该可以正常显示")
            
    except Exception as e:
        print(f"❌ 表不存在或查询失败: {str(e)}")
        
    db.close()
    
except Exception as e:
    print(f"❌ 连接数据库失败: {str(e)}")
