#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单测试交易记录排序
"""

import requests

def test_sorting():
    """测试交易记录排序"""
    
    print("=== 测试交易记录按ID排序 ===\n")
    
    base_url = "http://localhost:5000"
    
    try:
        task_id = "pvfrs_bt_69059774_141752"
        
        print(f"获取任务 {task_id} 的交易记录...")
        
        trades_response = requests.get(f"{base_url}/api/admin/pvfrs/backtest/trades/{task_id}")
        
        if trades_response.status_code != 200:
            print(f"获取交易记录失败: {trades_response.status_code}")
            return
        
        trades_result = trades_response.json()
        trades = trades_result.get('data', [])
        
        print(f"获取到 {len(trades)} 条交易记录\n")
        
        print("=== 前10条交易记录 ===")
        
        for i, trade in enumerate(trades[:10], 1):
            stock_code = trade.get('stock_code')
            entry_time = trade.get('entry_time')
            exit_time = trade.get('exit_time')
            exit_reason = trade.get('exit_reason')
            
            print(f"{i}. 股票: {stock_code}")
            print(f"   入场: {entry_time}")
            print(f"   出场: {exit_time}")
            print(f"   原因: {exit_reason}")
            print()
        
        # 验证时间顺序
        entry_times = [t for t in [trade.get('entry_time') for trade in trades] if t]
        is_sorted = all(entry_times[i] <= entry_times[i+1] for i in range(len(entry_times)-1))
        
        print("=== 验证结果 ===")
        if is_sorted:
            print("SUCCESS: 交易记录已按时间顺序排列")
        else:
            print("WARNING: 交易记录可能未按预期排序")
        
        print("\n测试完成!")
        
    except Exception as e:
        print(f"测试失败: {str(e)}")

if __name__ == "__main__":
    test_sorting()
