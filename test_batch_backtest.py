#!/usr/bin/env python3
"""
测试PVFRS批量回测功能
"""

import requests
import json

# API基础URL
BASE_URL = "http://localhost:5000/api/admin"

def test_batch_backtest():
    """测试批量回测功能"""
    
    # 1. 登录获取token
    login_data = "username=admin&password=admin123"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    print("正在登录...")
    login_response = requests.post(f"{BASE_URL}/auth/login", data=login_data, headers=headers)
    
    if login_response.status_code != 200:
        print(f"登录失败: {login_response.status_code}")
        print(login_response.text)
        return
    
    token = login_response.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    print("登录成功!")
    
    # 2. 提交批量回测任务
    print("\n提交批量回测任务...")
    backtest_data = {
        "mode": "batch",
        "market": "CN",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "initial_capital": 100000,
        "stock_codes": ["000651", "000333"]  # 使用有PVFRS数据的股票
    }
    
    backtest_response = requests.post(f"{BASE_URL}/pvfrs/backtest", json=backtest_data, headers=headers)
    
    if backtest_response.status_code == 200:
        result = backtest_response.json()
        task_id = result.get("id")
        print(f"批量回测任务提交成功! 任务ID: {task_id}")
        print(f"任务状态: {result}")
        
        # 3. 获取任务状态
        print("\n获取任务状态...")
        status_response = requests.get(f"{BASE_URL}/pvfrs/task/{task_id}", headers=headers)
        
        if status_response.status_code == 200:
            status = status_response.json()
            print(f"任务状态: {json.dumps(status, indent=2, ensure_ascii=False)}")
        
    else:
        print(f"提交批量回测任务失败: {backtest_response.status_code}")
        print(backtest_response.text)

if __name__ == "__main__":
    test_batch_backtest()
