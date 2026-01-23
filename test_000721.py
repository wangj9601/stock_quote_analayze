#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试股票代码 000721 的交易记录排序
"""

import requests

def test_000721():
    """测试股票代码 000721 的交易记录"""
    
    print("=== 测试股票代码 000721 的交易记录 ===\n")
    
    base_url = "http://localhost:5000"
    
    try:
        # 获取所有任务，寻找包含 000721 的任务
        print("1. 获取任务列表...")
        tasks_response = requests.get(f"{base_url}/api/admin/pvfrs/backtest/tasks")
        
        if tasks_response.status_code != 200:
            print(f"获取任务列表失败: {tasks_response.status_code}")
            return
        
        tasks_result = tasks_response.json()
        tasks = tasks_result.get('tasks', [])
        
        # 寻找包含 000721 的任务
        target_task = None
        for task in tasks:
            stock_list = task.get('stockList', [])
            if '000721' in stock_list:
                target_task = task
                break
        
        if not target_task:
            print("未找到包含股票代码 000721 的任务")
            print("可用的任务:")
            for task in tasks[:3]:  # 显示前3个任务
                print(f"  - {task.get('task_id')}: {task.get('stockList', [])}")
            return
        
        task_id = target_task['task_id']
        print(f"找到包含 000721 的任务: {task_id}")
        
        # 获取交易记录
        print(f"\n2. 获取任务 {task_id} 的交易记录...")
        trades_response = requests.get(f"{base_url}/api/admin/pvfrs/backtest/trades/{task_id}")
        
        if trades_response.status_code != 200:
            print(f"获取交易记录失败: {trades_response.status_code}")
            return
        
        trades_result = trades_response.json()
        trades = trades_result.get('data', [])
        
        # 过滤出 000721 的交易记录
        stock_000721_trades = [trade for trade in trades if trade.get('stock_code') == '000721']
        
        print(f"找到 {len(stock_000721_trades)} 条 000721 的交易记录\n")
        
        if stock_000721_trades:
            print("=== 000721 交易记录 ===")
            for i, trade in enumerate(stock_000721_trades, 1):
                entry_time = trade.get('entry_time')
                exit_time = trade.get('exit_time')
                exit_reason = trade.get('exit_reason')
                
                print(f"{i}. 入场: {entry_time}")
                print(f"   出场: {exit_time}")
                print(f"   原因: {exit_reason}")
                print()
            
            # 验证排序
            entry_times = [t for t in [trade.get('entry_time') for trade in stock_000721_trades] if t]
            if entry_times:
                is_sorted = all(entry_times[i] <= entry_times[i+1] for i in range(len(entry_times)-1))
                print("=== 验证结果 ===")
                if is_sorted:
                    print("SUCCESS: 000721 交易记录已按ID升序排列")
                else:
                    print("WARNING: 000721 交易记录可能未按预期排序")
        else:
            print("该任务中没有 000721 的交易记录")
        
        print("\n测试完成!")
        
    except Exception as e:
        print(f"测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_000721()
