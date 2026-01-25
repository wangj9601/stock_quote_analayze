#!/usr/bin/env python3
"""测试任务ID修复"""
import requests
import json

def test_backtest_creation():
    """测试回测任务创建"""
    url = "http://localhost:5000/api/admin/pvfrs/backtest/create"
    
    # 简单的测试配置
    test_config = {
        "name": "测试回测任务",
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
        response = requests.post(url, json=test_config)
        print(f"状态码: {response.status_code}")
        print(f"响应内容: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and data.get('data'):
                task_id = data['data'].get('task_id')
                print(f"✅ 任务创建成功，任务ID: {task_id}")
                
                # 测试进度查询
                progress_url = f"http://localhost:5000/api/admin/pvfrs/backtest/progress/{task_id}"
                progress_response = requests.get(progress_url)
                print(f"\n进度查询状态码: {progress_response.status_code}")
                print(f"进度查询响应: {json.dumps(progress_response.json(), indent=2, ensure_ascii=False)}")
                
                if progress_response.status_code == 200:
                    print("✅ 进度查询API正常工作")
                else:
                    print("❌ 进度查询API有问题")
            else:
                print("❌ 响应中没有找到task_id")
        else:
            print("❌ 任务创建失败")
            
    except Exception as e:
        print(f"❌ 请求失败: {str(e)}")

if __name__ == "__main__":
    test_backtest_creation()
