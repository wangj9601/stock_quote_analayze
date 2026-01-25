#!/usr/bin/env python3
"""测试所有主要的PVFRS API端点"""
import requests
import json

def test_api_endpoint(url, description):
    """测试单个API端点"""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ {description}: 正常 (状态码: {response.status_code})")
            if 'data' in data:
                print(f"   📊 数据条数: {len(data['data']) if isinstance(data['data'], list) else 'N/A'}")
            return True
        else:
            print(f"❌ {description}: 失败 (状态码: {response.status_code})")
            print(f"   错误信息: {response.text}")
            return False
    except Exception as e:
        print(f"❌ {description}: 异常 - {str(e)}")
        return False

def main():
    """测试所有PVFRS API端点"""
    base_url = "http://localhost:5000"
    
    print("正在测试所有PVFRS API端点...")
    print("="*60)
    
    # 要测试的API端点列表
    endpoints = [
        (f"{base_url}/api/admin/pvfrs/reports", "报告列表"),
        (f"{base_url}/api/admin/pvfrs/backtest/tasks", "任务列表"),
        (f"{base_url}/api/frontend/pvfrs/monitor/alerts", "监控告警"),
        (f"{base_url}/api/frontend/pvfrs/monitor/performance", "性能指标"),
        (f"{base_url}/api/frontend/pvfrs/interface-status", "接口状态"),
        (f"{base_url}/api/frontend/pvfrs/selection-results?limit=1", "选股结果"),
    ]
    
    success_count = 0
    total_count = len(endpoints)
    
    for url, description in endpoints:
        if test_api_endpoint(url, description):
            success_count += 1
        print()
    
    print("="*60)
    print(f"测试结果: {success_count}/{total_count} 个API端点正常工作")
    
    if success_count == total_count:
        print("🎉 所有PVFRS API端点都正常工作！")
    else:
        print("⚠️ 部分API端点存在问题，需要进一步检查")

if __name__ == "__main__":
    main()
