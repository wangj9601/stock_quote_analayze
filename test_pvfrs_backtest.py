#!/usr/bin/env python3
"""
测试PVFRS回测功能
"""

import requests
import json
import time

# API基础URL
BASE_URL = "http://localhost:5000/api/admin"

def test_pvfrs_backtest():
    """测试PVFRS回测功能"""
    
    # 1. 登录获取token
    login_data = {
        "username": "admin",
        "password": "admin123"
    }
    
    # 使用form data格式
    form_data = f"username={login_data['username']}&password={login_data['password']}"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    print("正在登录...")
    login_response = requests.post(f"{BASE_URL}/auth/login", data=form_data, headers=headers)
    
    if login_response.status_code != 200:
        print(f"登录失败: {login_response.status_code}")
        print(login_response.text)
        return
    
    token = login_response.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    print("登录成功!")
    
    # 2. 获取配置
    print("\n获取策略配置...")
    config_response = requests.get(f"{BASE_URL}/pvfrs/config", headers=headers)
    if config_response.status_code == 200:
        config = config_response.json()
        print(f"配置获取成功: {json.dumps(config, indent=2, ensure_ascii=False)}")
    else:
        print(f"获取配置失败: {config_response.status_code}")
        return
    
    # 3. 提交单股回测任务
    print("\n提交单股回测任务...")
    backtest_data = {
        "mode": "single",
        "code": "000001",
        "market": "CN",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "initial_capital": 100000
    }
    
    backtest_response = requests.post(f"{BASE_URL}/pvfrs/backtest", json=backtest_data, headers=headers)
    
    if backtest_response.status_code == 200:
        result = backtest_response.json()
        task_id = result.get("task_id")
        print(f"回测任务提交成功! 任务ID: {task_id}")
        
        # 4. 轮询任务状态
        print("\n监控任务状态...")
        max_wait = 300  # 最多等待5分钟
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            status_response = requests.get(f"{BASE_URL}/pvfrs/task/{task_id}", headers=headers)
            
            if status_response.status_code == 200:
                status = status_response.json()
                print(f"任务状态: {status['status']}, 进度: {status['progress']}%, 当前步骤: {status.get('current_step', 'N/A')}")
                
                if status['status'] in ['completed', 'failed']:
                    if status['status'] == 'completed':
                        print("✅ 回测任务完成!")
                    else:
                        print(f"❌ 回测任务失败: {status.get('error_message', '未知错误')}")
                    break
            else:
                print(f"获取任务状态失败: {status_response.status_code}")
                break
            
            time.sleep(5)  # 每5秒查询一次
        
        # 5. 获取回测结果
        if status['status'] == 'completed':
            print("\n获取回测结果...")
            results_response = requests.get(f"{BASE_URL}/pvfrs/results", headers=headers)
            
            if results_response.status_code == 200:
                results = results_response.json()
                print(f"回测结果: {json.dumps(results, indent=2, ensure_ascii=False)}")
            else:
                print(f"获取结果失败: {results_response.status_code}")
        
    else:
        print(f"提交回测任务失败: {backtest_response.status_code}")
        print(backtest_response.text)

if __name__ == "__main__":
    test_pvfrs_backtest()
