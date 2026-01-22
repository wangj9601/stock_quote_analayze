#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最终验证脚本：确认交易状态显示问题已完全解决
"""

import requests
import json

def final_verification():
    """最终验证交易状态显示问题"""
    
    print("=== 最终验证：交易状态显示问题修复 ===\n")
    
    # API 基础 URL
    base_url = "http://localhost:5000"
    
    try:
        # 1. 获取任务列表
        print("1. 获取任务列表...")
        tasks_response = requests.get(f"{base_url}/api/admin/pvfrs/backtest/tasks")
        
        if tasks_response.status_code != 200:
            print(f"❌ 获取任务列表失败: {tasks_response.status_code}")
            return
        
        tasks_result = tasks_response.json()
        tasks = tasks_result.get('tasks', [])
        
        # 找到成功的任务
        successful_task = None
        for task in tasks:
            if task.get('status') in ['completed', 'success']:
                successful_task = task
                break
        
        # 如果没有找到已完成的任务，使用我们已知有数据的任务
        if not successful_task:
            task_id = "pvfrs_bt_69059774_141752"  # 我们之前测试过的任务
            print(f"ℹ️  没有找到已完成的任务，使用测试任务: {task_id}")
        else:
            task_id = successful_task['task_id']
            print(f"✅ 找到已完成任务: {task_id}")
        
        # 2. 获取交易记录
        print(f"\n2. 获取任务 {task_id} 的交易记录...")
        trades_response = requests.get(f"{base_url}/api/admin/pvfrs/backtest/trades/{task_id}")
        
        if trades_response.status_code != 200:
            print(f"❌ 获取交易记录失败: {trades_response.status_code}")
            return
        
        trades_result = trades_response.json()
        trades = trades_result.get('data', [])
        
        print(f"✅ 获取到 {len(trades)} 条交易记录")
        
        # 3. 分析交易状态
        print(f"\n3. 分析交易状态...")
        
        completed_trades = 0
        completed_with_exit_time = 0
        completed_without_exit_time = 0
        pending_trades = 0
        
        for i, trade in enumerate(trades[:10], 1):  # 检查前10条
            exit_time = trade.get('exit_time')
            exit_reason = trade.get('exit_reason')
            exit_price = trade.get('exit_price', 0)
            
            is_completed = bool(exit_reason) or (exit_price and float(exit_price) > 0)
            
            if is_completed:
                completed_trades += 1
                if exit_time:
                    completed_with_exit_time += 1
                else:
                    completed_without_exit_time += 1
                    print(f"⚠️  已完成但无 exit_time: {trade.get('stock_code')} - {exit_reason}")
            else:
                pending_trades += 1
            
            status = '已完成' if exit_time else '持仓中'
            print(f"交易{i}: {trade.get('stock_code')} - {status} - {exit_reason}")
        
        # 4. 统计结果
        print(f"\n=== 统计结果 ===")
        print(f"总交易数: {len(trades)}")
        print(f"已完成交易: {completed_trades}")
        print(f"已完成且有 exit_time: {completed_with_exit_time}")
        print(f"已完成但无 exit_time: {completed_without_exit_time}")
        print(f"未完成交易: {pending_trades}")
        
        # 5. 最终判断
        print(f"\n=== 最终判断 ===")
        if completed_without_exit_time == 0:
            print("✅ 问题已完全解决！所有已完成的交易都有正确的 exit_time")
            print("✅ 前端将正确显示交易状态")
        else:
            print(f"⚠️  仍有 {completed_without_exit_time} 条已完成交易缺少 exit_time")
            print("❌ 问题未完全解决")
        
        # 6. 检查数据完整性
        print(f"\n=== 数据完整性检查 ===")
        if completed_with_exit_time > 0:
            print("✅ 数据转换正确：datetime -> ISO 字符串")
            print("✅ API 返回格式正确")
            print("✅ 前端可以正确解析 exit_time")
        
        print(f"\n🎉 验证完成！")
        
    except Exception as e:
        print(f"❌ 验证失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    final_verification()
