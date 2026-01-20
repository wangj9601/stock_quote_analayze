#!/usr/bin/env python3
"""
PVFRS策略管理增强版测试脚本
测试重构后的API功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import requests
import json
import time
from datetime import datetime, timedelta

# API基础URL
BASE_URL = "http://localhost:5000"

def test_health_check():
    """测试健康检查"""
    print("=== 测试健康检查 ===")
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"响应数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
            print("[成功] 健康检查通过")
            return True
        else:
            print(f"[失败] 健康检查失败: {response.text}")
            return False
            
    except Exception as e:
        print(f"[异常] 健康检查异常: {str(e)}")
        return False

def test_strategy_configs():
    """测试策略配置管理"""
    print("\n=== 测试策略配置管理 ===")
    
    try:
        # 1. 创建策略配置
        config_data = {
            "name": "测试策略",
            "description": "这是一个测试策略",
            "config_params": {
                "strategy_params": {
                    "buy_bias_min": -0.05,
                    "sell_bias_max": 0.15,
                    "buy_consecutive_days": 2,
                    "signal_threshold": 0.6
                },
                "risk_params": {
                    "stop_loss_rate": 0.1,
                    "take_profit_rate": 0.2,
                    "max_position_size": 0.1,
                    "commission_rate": 0.0003,
                    "slippage_rate": 0.001
                }
            },
            "is_active": True
        }
        
        response = requests.post(
            f"{BASE_URL}/api/admin/pvfrs/strategy-configs",
            json=config_data,
            timeout=10
        )
        
        print(f"创建策略配置 - 状态码: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"创建结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
            config_id = result.get('config_id')
            
            # 2. 获取策略配置
            response = requests.get(
                f"{BASE_URL}/api/admin/pvfrs/strategy-configs/{config_id}",
                timeout=10
            )
            
            print(f"获取策略配置 - 状态码: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print(f"配置详情: {json.dumps(result, indent=2, ensure_ascii=False)}")
                print("[成功] 策略配置管理测试通过")
                return True
            else:
                print(f"[失败] 获取策略配置失败: {response.text}")
                return False
        else:
            print(f"[失败] 创建策略配置失败: {response.text}")
            return False
            
    except Exception as e:
        print(f"[异常] 策略配置管理测试异常: {str(e)}")
        return False

def test_backtest_creation():
    """测试回测任务创建"""
    print("\n=== 测试回测任务创建 ===")
    
    try:
        # 创建回测任务
        backtest_data = {
            "strategy_name": "PVFRS默认策略",
            "stock_pool": ["000001", "000002", "600000"],
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "initial_capital": 100000.0,
            "strategy_params": {
                "buy_bias_min": -0.05,
                "sell_bias_max": 0.15,
                "buy_consecutive_days": 2,
                "signal_threshold": 0.6
            },
            "risk_params": {
                "stop_loss_rate": 0.1,
                "take_profit_rate": 0.2,
                "max_position_size": 0.1,
                "commission_rate": 0.0003,
                "slippage_rate": 0.001
            },
            "mode": "batch",
            "force_update": False
        }
        
        response = requests.post(
            f"{BASE_URL}/api/admin/pvfrs/backtests",
            json=backtest_data,
            timeout=10
        )
        
        print(f"创建回测任务 - 状态码: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"创建结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
            task_id = result.get('task_id')
            
            # 2. 获取任务进度
            response = requests.get(
                f"{BASE_URL}/api/admin/pvfrs/backtests/{task_id}/progress",
                timeout=10
            )
            
            print(f"获取任务进度 - 状态码: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print(f"任务进度: {json.dumps(result, indent=2, ensure_ascii=False)}")
                print("[成功] 回测任务创建测试通过")
                return True
            else:
                print(f"[失败] 获取任务进度失败: {response.text}")
                return False
        else:
            print(f"[失败] 创建回测任务失败: {response.text}")
            return False
            
    except Exception as e:
        print(f"[异常] 回测任务创建测试异常: {str(e)}")
        return False

def test_task_list():
    """测试任务列表"""
    print("\n=== 测试任务列表 ===")
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/admin/pvfrs/backtests",
            params={"limit": 10, "offset": 0},
            timeout=10
        )
        
        print(f"获取任务列表 - 状态码: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"任务列表: {json.dumps(result, indent=2, ensure_ascii=False)}")
            print("[成功] 任务列表测试通过")
            return True
        else:
            print(f"[失败] 获取任务列表失败: {response.text}")
            return False
            
    except Exception as e:
        print(f"[异常] 任务列表测试异常: {str(e)}")
        return False

def test_statistics():
    """测试统计信息"""
    print("\n=== 测试统计信息 ===")
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/admin/pvfrs/statistics",
            timeout=10
        )
        
        print(f"获取统计信息 - 状态码: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"统计信息: {json.dumps(result, indent=2, ensure_ascii=False)}")
            print("[成功] 统计信息测试通过")
            return True
        else:
            print(f"[失败] 获取统计信息失败: {response.text}")
            return False
            
    except Exception as e:
        print(f"[异常] 统计信息测试异常: {str(e)}")
        return False

def test_pvfrs_screening():
    """测试PVFRS选股功能"""
    print("\n=== 测试PVFRS选股功能 ===")
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/screening/pvfrs-strategy",
            timeout=30
        )
        
        print(f"PVFRS选股 - 状态码: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"选股结果数量: {len(result.get('data', []))}")
            
            # 打印前3条结果
            if result.get('data'):
                for i, stock in enumerate(result['data'][:3]):
                    print(f"股票 {i+1}: {stock.get('symbol')} - {stock.get('name')}")
            
            print("[成功] PVFRS选股功能测试通过")
            return True
        else:
            print(f"[失败] PVFRS选股失败: {response.text}")
            return False
            
    except Exception as e:
        print(f"[异常] PVFRS选股测试异常: {str(e)}")
        return False

def main():
    """主测试函数"""
    print("开始PVFRS策略管理增强版功能测试...")
    print(f"API地址: {BASE_URL}")
    print("=" * 50)
    
    # 测试列表
    tests = [
        ("健康检查", test_health_check),
        ("策略配置管理", test_strategy_configs),
        ("回测任务创建", test_backtest_creation),
        ("任务列表", test_task_list),
        ("统计信息", test_statistics),
        ("PVFRS选股功能", test_pvfrs_screening)
    ]
    
    # 执行测试
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n[测试] 执行测试: {test_name}")
        try:
            if test_func():
                passed += 1
                print(f"[通过] {test_name} - 通过")
            else:
                print(f"[失败] {test_name} - 失败")
        except Exception as e:
            print(f"[异常] {test_name} - 异常: {str(e)}")
        
        # 测试间隔
        time.sleep(1)
    
    # 测试总结
    print("\n" + "=" * 50)
    print(f"测试完成: {passed}/{total} 通过")
    
    if passed == total:
        print("[成功] 所有测试通过！PVFRS策略管理增强版功能正常")
    else:
        print("[警告] 部分测试失败，请检查相关功能")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
