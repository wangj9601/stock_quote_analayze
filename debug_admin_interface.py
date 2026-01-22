#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试 admin_interface_enhanced.py 的数据转换过程
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend_core.strategies.pvfrs.admin_interface_enhanced import AdminInterfaceEnhanced
from backend_api.services.pvfrs_admin_service import PVFRSAdminService
from backend_api.database import get_db

def debug_admin_interface():
    """调试 admin_interface 的数据转换"""
    
    print("=== 调试 admin_interface 数据转换 ===\n")
    
    # 创建数据库会话
    db = next(get_db())
    
    try:
        # 创建服务和管理接口
        service = PVFRSAdminService(db)
        admin_interface = AdminInterfaceEnhanced(service)
        
        # 使用任务ID
        task_id = "pvfrs_bt_69059774_141752"
        
        print(f"获取任务 {task_id} 的交易记录...\n")
        
        # 获取交易记录
        trades = admin_interface.get_trades(task_id)
        
        print(f"API返回 {len(trades)} 条交易记录\n")
        
        # 检查前5条记录
        for i, trade in enumerate(trades[:5], 1):
            print(f"--- API返回的交易 {i} ---")
            print(f"股票代码: {trade.get('stock_code')}")
            print(f"入场时间: {trade.get('entry_time')}")
            print(f"出场时间: {trade.get('exit_time')}")
            print(f"入场价格: {trade.get('entry_price')}")
            print(f"出场价格: {trade.get('exit_price')}")
            print(f"退出原因: {trade.get('exit_reason')}")
            print(f"交易日期: {trade.get('trade_date')}")
            
            # 判断交易状态
            exit_time = trade.get('exit_time')
            exit_reason = trade.get('exit_reason')
            exit_price = trade.get('exit_price', 0)
            
            is_completed = bool(exit_reason) or (exit_price and float(exit_price) > 0)
            frontend_display = '已完成' if exit_time else '持仓中'
            
            print(f"🔍 API数据分析:")
            print(f"   - 有退出原因: {bool(exit_reason)}")
            print(f"   - 出场价格 > 0: {exit_price > 0} (价格: {exit_price})")
            print(f"   - 交易已完成: {is_completed}")
            print(f"   - 前端显示: {frontend_display}")
            
            if is_completed and not exit_time:
                print("   ⚠️  问题: 交易已完成但 exit_time 为空")
            elif not is_completed and exit_time:
                print("   ⚠️  问题: 交易未完成但 exit_time 有值")
            elif is_completed and exit_time:
                print("   ✅ 正常: 交易已完成且 exit_time 有值")
            else:
                print("   ℹ️  正常: 交易未完成且 exit_time 为空")
            
            print()
        
        # 直接查询数据库对比
        print("=== 直接查询数据库对比 ===\n")
        
        results = service.get_backtest_results(task_id)
        if results:
            result = results[0]
            db_trades = service.get_trade_records(result.id)
            
            print(f"数据库中有 {len(db_trades)} 条交易记录\n")
            
            for i, db_trade in enumerate(db_trades[:5], 1):
                print(f"--- 数据库交易 {i} ---")
                print(f"股票代码: {db_trade.stock_code}")
                print(f"入场时间: {db_trade.entry_time}")
                print(f"出场时间: {db_trade.exit_time}")
                print(f"入场价格: {db_trade.entry_price}")
                print(f"出场价格: {db_trade.exit_price}")
                print(f"退出原因: {db_trade.exit_reason}")
                print(f"交易日期: {db_trade.trade_date}")
                
                # 判断交易状态
                is_completed = bool(db_trade.exit_reason) or (db_trade.exit_price and db_trade.exit_price > 0)
                frontend_display = '已完成' if db_trade.exit_time else '持仓中'
                
                print(f"🔍 数据库分析:")
                print(f"   - 有退出原因: {bool(db_trade.exit_reason)}")
                print(f"   - 出场价格 > 0: {db_trade.exit_price > 0} (价格: {db_trade.exit_price})")
                print(f"   - 交易已完成: {is_completed}")
                print(f"   - 前端显示: {frontend_display}")
                
                if is_completed and not db_trade.exit_time:
                    print("   ⚠️  问题: 交易已完成但 exit_time 为空")
                elif not is_completed and db_trade.exit_time:
                    print("   ⚠️  问题: 交易未完成但 exit_time 有值")
                elif is_completed and db_trade.exit_time:
                    print("   ✅ 正常: 交易已完成且 exit_time 有值")
                else:
                    print("   ℹ️  正常: 交易未完成且 exit_time 为空")
                
                print()
        
    except Exception as e:
        print(f"❌ 调试失败: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()

if __name__ == "__main__":
    debug_admin_interface()
