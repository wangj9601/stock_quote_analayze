#!/usr/bin/env python3
"""测试任务进度修复"""
import requests
import json
import time

def test_task_progress():
    """测试任务进度轮询"""
    # 首先创建一个任务
    create_url = "http://localhost:5000/api/admin/pvfrs/backtest/create"
    test_config = {
        "name": "测试进度轮询",
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
        # 创建任务
        print("1. 创建回测任务...")
        create_response = requests.post(create_url, json=test_config)
        
        if create_response.status_code != 200:
            print(f"❌ 任务创建失败: {create_response.status_code}")
            return
            
        create_data = create_response.json()
        if not create_data.get('success') or not create_data.get('data'):
            print("❌ 任务创建响应格式错误")
            return
            
        task_id = create_data['data']['task_id']
        print(f"✅ 任务创建成功，任务ID: {task_id}")
        
        # 测试进度查询
        progress_url = f"http://localhost:5000/api/admin/pvfrs/backtest/progress/{task_id}"
        print(f"\n2. 查询任务进度...")
        
        for i in range(3):  # 轮询3次
            progress_response = requests.get(progress_url)
            
            if progress_response.status_code == 200:
                progress_data = progress_response.json()
                
                # 检查数据结构
                print(f"\n轮询 {i+1}:")
                print(f"  - success: {progress_data.get('success')}")
                print(f"  - task_type: {progress_data.get('task_type')}")
                
                if progress_data.get('data'):
                    data = progress_data['data']
                    print(f"  - task_id: {data.get('task_id')}")
                    print(f"  - status: {data.get('status')}")
                    print(f"  - progress_percentage: {data.get('progress_percentage')}")
                    print(f"  - current_step: {data.get('current_step')}")
                    
                    # 验证前端需要的数据结构
                    required_fields = ['task_id', 'status', 'progress_percentage', 'current_step']
                    missing_fields = [field for field in required_fields if not data.get(field)]
                    
                    if missing_fields:
                        print(f"  ❌ 缺失字段: {missing_fields}")
                    else:
                        print(f"  ✅ 所有必要字段都存在")
                        
                        # 模拟前端逻辑
                        frontend_task = data  # 前端现在使用 task.data
                        task_id_check = frontend_task.get('task_id') or frontend_task.get('id')
                        
                        if task_id_check:
                            print(f"  ✅ 前端可以获取任务ID: {task_id_check}")
                        else:
                            print(f"  ❌ 前端无法获取任务ID")
                else:
                    print("  ❌ 响应中没有data字段")
            else:
                print(f"  ❌ 进度查询失败: {progress_response.status_code}")
            
            if i < 2:  # 不是最后一次
                time.sleep(1)
        
        print("\n✅ 测试完成")
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")

if __name__ == "__main__":
    test_task_progress()
