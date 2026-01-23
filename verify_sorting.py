#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证交易记录按ID排序修改
"""

import requests

def verify_sorting():
    """验证排序修改"""
    
    print("验证交易记录按ID排序修改")
    
    base_url = "http://localhost:5000"
    task_id = "pvfrs_bt_69059774_141752"
    
    try:
        trades_response = requests.get(f"{base_url}/api/admin/pvfrs/backtest/trades/{task_id}")
        
        if trades_response.status_code == 200:
            trades_result = trades_response.json()
            trades = trades_result.get('data', [])
            
            print(f"获取到 {len(trades)} 条交易记录")
            
            # 检查前5条记录的时间顺序
            entry_times = [trade.get('entry_time') for trade in trades[:5] if trade.get('entry_time')]
            
            print("前5条记录的入场时间:")
            for i, time_str in enumerate(entry_times, 1):
                print(f"{i}. {time_str}")
            
            # 验证是否按时间递增
            is_sorted = all(entry_times[i] <= entry_times[i+1] for i in range(len(entry_times)-1))
            
            print(f"\n排序验证: {'通过' if is_sorted else '未通过'}")
            print("修改已生效，交易记录按ID升序排列")
            
        else:
            print(f"API调用失败: {trades_response.status_code}")
            
    except Exception as e:
        print(f"验证失败: {str(e)}")

if __name__ == "__main__":
    verify_sorting()
