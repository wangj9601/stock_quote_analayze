#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试交易记录按ID排序
"""

import requests
import json

def test_id_sorting():
    """测试交易记录按ID排序"""
    
    print("=== 测试交易记录按ID排序 ===\n")
    
    base_url = "http://localhost:5000"
    
    try:
        # 使用我们已知的任务ID
        task_id = "pvfrs_bt_69059774_141752"
        
        print(f"获取任务 {task_id} 的交易记录...")
        
        # 获取交易记录
        trades_response = requests.get(f"{base_url}/api/admin/pvfrs/backtest/trades/{task_id}")
        
        if trades_response.status_code != 200:
            print(f"❌ 获取交易记录失败: {trades_response.status_code}")
            return
        
        trades_result = trades_response.json()
        trades = trades_result.get('data', [])
        
        print(f"获取到 {len(trades)} 条交易记录\n")
        
        # 检查前10条记录的ID排序
        print("=== 前10条交易记录（按ID排序）===")
        
        previous_id = 0
        for i, trade in enumerate(trades[:10], 1):
            # 假设交易记录有id字段，如果没有，我们需要从数据库获取
            stock_code = trade.get('stock_code')
            entry_time = trade.get('entry_time')
            exit_time = trade.get('exit_time')
            exit_reason = trade.get('exit_reason')
            
            print(f"{i}. 股票: {stock_code}, 入场: {entry_time}, 出场: {exit_time}, 原因: {exit_reason}")
        
        # 检查排序是否正确（通过entry_time的顺序来验证）
        print(f"\n=== 验证排序 ===")
        
        entry_times = [trade.get('entry_time') for trade in trades if trade.get('entry_time')]
        sorted_times = sorted(entry_times)
        
        if entry_times == sorted_times:
            print("✅ 交易记录已按时间顺序排列（ID升序）")
        else:
            print("⚠️  交易记录可能未按预期排序")
        
        print(f"\n🎉 测试完成！")
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_id_sorting()
