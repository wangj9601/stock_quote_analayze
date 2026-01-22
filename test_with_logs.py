#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试带日志的 admin_interface 调用
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import logging
from backend_core.strategies.pvfrs.admin_interface_enhanced import AdminInterfaceEnhanced
from backend_api.services.pvfrs_admin_service import PVFRSAdminService
from backend_api.database import get_db

# 设置日志级别
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_with_logs():
    """测试带日志的 admin_interface 调用"""
    
    print("=== 测试带日志的 admin_interface 调用 ===\n")
    
    # 创建数据库会话
    db = next(get_db())
    
    try:
        # 创建服务和管理接口
        service = PVFRSAdminService(db)
        admin_interface = AdminInterfaceEnhanced(service)
        
        # 使用任务ID
        task_id = "pvfrs_bt_69059774_141752"
        
        print(f"获取任务 {task_id} 的交易记录（带日志）...\n")
        
        # 获取交易记录（会触发调试日志）
        trades = admin_interface.get_trades(task_id)
        
        print(f"\nAPI返回 {len(trades)} 条交易记录")
        
        # 检查前5条记录的 exit_time
        completed_with_exit_time = 0
        completed_without_exit_time = 0
        
        for i, trade in enumerate(trades[:10], 1):
            exit_time = trade.get('exit_time')
            exit_reason = trade.get('exit_reason')
            exit_price = trade.get('exit_price', 0)
            
            is_completed = bool(exit_reason) or (exit_price and float(exit_price) > 0)
            
            print(f"调试 {i}: stock_code={trade.get('stock_code')}, exit_time={exit_time} (类型: {type(exit_time)}), "
                  f"exit_reason={exit_reason}, is_completed={is_completed}")
            
            if is_completed:
                if exit_time:
                    completed_with_exit_time += 1
                    print(f"  ✅ 已完成且有 exit_time")
                else:
                    completed_without_exit_time += 1
                    print(f"  ⚠️  已完成但无 exit_time: {trade.get('stock_code')} - {exit_reason}")
        
        print(f"\n统计结果:")
        print(f"已完成且有 exit_time: {completed_with_exit_time}")
        print(f"已完成但无 exit_time: {completed_without_exit_time}")
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()

if __name__ == "__main__":
    test_with_logs()
