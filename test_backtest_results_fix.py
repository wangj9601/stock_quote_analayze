#!/usr/bin/env python3
"""测试回测结果修复"""
import requests
import json
import time

def test_backtest_results():
    """测试回测结果获取"""
    
    # 1. 首先创建一个回测任务
    print("1. 创建回测任务...")
    create_url = "http://localhost:5000/api/admin/pvfrs/backtest/create"
    test_config = {
        "name": "测试结果显示",
        "stock_codes": ["600000"],
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
        "initial_capital": 100000,
        "strategy_config": {
            "buy_bias_min": -0.05,
            "sell_bias_max": 0.15,
            "signal_threshold": 0.6
        }
    }
    
    try:
        create_response = requests.post(create_url, json=test_config)
        if create_response.status_code != 200:
            print(f"❌ 任务创建失败: {create_response.status_code}")
            return
            
        create_data = create_response.json()
        if not create_data.get('success'):
            print("❌ 任务创建失败")
            return
            
        task_id = create_data['data']['task_id']
        print(f"✅ 任务创建成功: {task_id}")
        
        # 2. 等待任务完成
        print("\n2. 等待任务完成...")
        progress_url = f"http://localhost:5000/api/admin/pvfrs/backtest/progress/{task_id}"
        
        for i in range(10):  # 最多等待10秒
            progress_response = requests.get(progress_url)
            if progress_response.status_code == 200:
                progress_data = progress_response.json()
                if progress_data.get('data'):
                    task_data = progress_data['data']
                    status = task_data.get('status')
                    print(f"   轮询 {i+1}: 状态={status}, 进度={task_data.get('progress_percentage', 0)}%")
                    
                    if status == 'completed':
                        print("✅ 任务完成")
                        break
                    elif status == 'failed':
                        print("❌ 任务失败")
                        return
                    
            time.sleep(1)
        else:
            print("⚠️ 任务超时，继续测试...")
        
        # 3. 测试获取回测结果（使用增强版API）
        print("\n3. 测试获取回测结果...")
        reports_url = "http://localhost:5000/api/admin/pvfrs/reports"
        
        reports_response = requests.get(reports_url)
        print(f"状态码: {reports_response.status_code}")
        
        if reports_response.status_code == 200:
            reports_data = reports_response.json()
            print(f"响应结构: {json.dumps(reports_data, indent=2, ensure_ascii=False)}")
            
            if reports_data.get('success') and reports_data.get('data'):
                results = reports_data['data']
                print(f"✅ 获取到 {len(results)} 条回测结果")
                
                if results:
                    # 查看第一条结果的结构
                    first_result = results[0]
                    print(f"\n第一条结果字段:")
                    for key, value in first_result.items():
                        print(f"  {key}: {value}")
                    
                    # 检查是否有我们刚创建的任务的结果
                    our_result = next((r for r in results if r.get('taskId') == task_id), None)
                    if our_result:
                        print(f"\n✅ 找到刚创建任务的结果: {our_result.get('title')}")
                    else:
                        print(f"\n⚠️ 没有找到刚创建任务的结果")
                else:
                    print("⚠️ 结果列表为空")
            else:
                print("❌ 响应格式错误")
        else:
            print(f"❌ 获取结果失败: {reports_response.status_code}")
        
        # 4. 对比普通版API（应该返回不同或空的结果）
        print("\n4. 对比普通版API...")
        results_url = "http://localhost:5000/api/admin/pvfrs/results"
        
        results_response = requests.get(results_url)
        print(f"普通版API状态码: {results_response.status_code}")
        
        if results_response.status_code == 200:
            results_data = results_response.json()
            if isinstance(results_data, list):
                print(f"普通版API返回 {len(results_data)} 条结果")
            else:
                print(f"普通版API返回: {type(results_data)}")
        
        print("\n✅ 测试完成")
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")

if __name__ == "__main__":
    test_backtest_results()
