#!/usr/bin/env python3
"""
测试PVFRS管理后台回测任务列表接口修复
"""

import requests
import json
from datetime import datetime

def test_backtest_tasks_list():
    """测试回测任务列表接口"""
    print("=== 测试回测任务列表接口 ===")
    
    url = "http://localhost:5000/api/admin/pvfrs/backtest/tasks"
    params = {
        "page": 1,
        "pageSize": 20,
        "status": ""
    }
    
    try:
        print(f"请求URL: {url}")
        print(f"请求参数: {params}")
        
        response = requests.get(url, params=params, timeout=10)
        
        print(f"响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("响应数据:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            print("✅ 回测任务列表接口测试成功")
            return True
        else:
            print(f"❌ 回测任务列表接口测试失败: {response.status_code}")
            print(f"错误信息: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ 请求超时")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ 连接错误，请确认后端服务是否启动")
        return False
    except Exception as e:
        print(f"❌ 请求异常: {str(e)}")
        return False


def test_with_status_filter():
    """测试带状态过滤的任务列表"""
    print("\n=== 测试带状态过滤的任务列表 ===")
    
    url = "http://localhost:5000/api/admin/pvfrs/backtest/tasks"
    params = {
        "page": 1,
        "pageSize": 10,
        "status": "completed"
    }
    
    try:
        print(f"请求URL: {url}")
        print(f"请求参数: {params}")
        
        response = requests.get(url, params=params, timeout=10)
        
        print(f"响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("响应数据:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            print("✅ 带状态过滤的任务列表测试成功")
            return True
        else:
            print(f"❌ 带状态过滤的任务列表测试失败: {response.status_code}")
            print(f"错误信息: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 请求异常: {str(e)}")
        return False


def main():
    """主测试函数"""
    print("PVFRS管理后台回测任务列表接口修复测试")
    print("=" * 60)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 测试结果
    results = []
    
    # 测试基本任务列表接口
    results.append(test_backtest_tasks_list())
    
    # 测试带状态过滤的接口
    results.append(test_with_status_filter())
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总:")
    
    test_names = ["基本任务列表接口", "带状态过滤的任务列表"]
    for i, (name, result) in enumerate(zip(test_names, results)):
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{i+1}. {name}: {status}")
    
    success_count = sum(results)
    total_count = len(results)
    
    print(f"\n总体结果: {success_count}/{total_count} 测试通过")
    
    if success_count == total_count:
        print("🎉 所有测试通过！PVFRS管理后台回测任务列表接口修复成功")
    else:
        print("⚠️  部分测试失败，需要进一步检查")
    
    return success_count == total_count


if __name__ == "__main__":
    main()