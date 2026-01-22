#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试交易记录API返回数据
"""

import requests
import json
from datetime import datetime

def test_trades_api():
    """测试交易记录API"""
    
    BASE_URL = "http://localhost:5000"
    
    # 首先获取任务列表
    try:
        print("=== 获取任务列表 ===")
        tasks_response = requests.get(
            f"{BASE_URL}/api/admin/pvfrs/backtest/tasks",
            timeout=10
        )
        
        if tasks_response.status_code == 200:
            tasks_result = tasks_response.json()
            print(f"API响应: {tasks_result}")
            
            # 处理不同的响应格式
            tasks = []
            if isinstance(tasks_result, dict):
                if 'data' in tasks_result:
                    tasks = tasks_result['data']
                elif 'tasks' in tasks_result:
                    tasks = tasks_result['tasks']
                else:
                    tasks = list(tasks_result.values()) if tasks_result else []
            elif isinstance(tasks_result, list):
                tasks = tasks_result
            
            print(f"找到 {len(tasks)} 个任务")
            
            if not tasks:
                print("❌ 没有找到任务")
                return
            
            # 使用第一个任务
            task = tasks[0]
            task_id = task.get('id') or task.get('task_id')
            print(f"测试任务: {task_id}")
            
            # 获取交易记录
            print(f"\n=== 获取任务 {task_id} 的交易记录 ===")
            trades_response = requests.get(
                f"{BASE_URL}/api/admin/pvfrs/backtest/trades/{task_id}",
                timeout=10
            )
            
            if trades_response.status_code == 200:
                trades_data = trades_response.json()
                print(f"API响应状态: {trades_data.get('success')}")
                
                trades = trades_data.get('data', [])
                print(f"找到 {len(trades)} 条交易记录\n")
                
                for i, trade in enumerate(trades[:5], 1):  # 只显示前5条
                    print(f"--- 交易 {i} ---")
                    print(f"股票代码: {trade.get('stock_code')}")
                    print(f"入场时间: {trade.get('entry_time')}")
                    print(f"出场时间: {trade.get('exit_time')}")
                    print(f"入场价格: {trade.get('entry_price')}")
                    print(f"出场价格: {trade.get('exit_price')}")
                    print(f"退出原因: {trade.get('exit_reason')}")
                    
                    # 判断前端显示逻辑
                    exit_time = trade.get('exit_time')
                    exit_reason = trade.get('exit_reason')
                    exit_price = trade.get('exit_price', 0)
                    
                    is_completed = bool(exit_reason) or (exit_price and float(exit_price) > 0)
                    frontend_display = '已完成' if exit_time else '持仓中'
                    
                    print(f"🔍 交易状态分析:")
                    print(f"   - 有退出原因: {bool(exit_reason)}")
                    print(f"   - 出场价格 > 0: {exit_price > 0} (价格: {exit_price})")
                    print(f"   - 交易已完成: {is_completed}")
                    print(f"   - 前端显示: {frontend_display}")
                    
                    if is_completed and not exit_time:
                        print("   ⚠️  问题: 交易已完成但 exit_time 为空，前端会显示'持仓中'")
                    elif not is_completed and exit_time:
                        print("   ⚠️  问题: 交易未完成但 exit_time 有值")
                    elif is_completed and exit_time:
                        print("   ✅ 正常: 交易已完成且 exit_time 有值")
                    else:
                        print("   ℹ️  正常: 交易未完成且 exit_time 为空")
                    
                    print()
                
            else:
                print(f"❌ 获取交易记录失败: {trades_response.status_code}")
                print(trades_response.text)
                
        else:
            print(f"❌ 获取任务列表失败: {tasks_response.status_code}")
            print(tasks_response.text)
            
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_trades_api()
