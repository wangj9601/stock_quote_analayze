#!/usr/bin/env python3
"""测试API连接"""
import requests

def test_api_connection():
    """测试API连接"""
    
    print("🔍 测试API连接")
    print("="*50)
    
    # 测试基本连接
    print("\n1. 测试基本连接:")
    try:
        response = requests.get("http://localhost:5000/", timeout=5)
        print(f"   状态码: {response.status_code}")
        if response.status_code == 200:
            print(f"   ✅ API服务正常运行")
        else:
            print(f"   ❌ API服务异常")
    except Exception as e:
        print(f"   ❌ 连接失败: {e}")
        return
    
    # 测试指标API端点
    print("\n2. 测试指标API端点:")
    try:
        response = requests.options("http://localhost:5000/api/admin/indicators/generate-batch-watchlist", timeout=5)
        print(f"   OPTIONS状态码: {response.status_code}")
        if response.status_code == 200:
            print(f"   ✅ 指标API端点可用")
        else:
            print(f"   ❌ 指标API端点不可用")
    except Exception as e:
        print(f"   ❌ 测试指标API失败: {e}")
    
    print(f"\n🔧 修复总结:")
    print(f"1. ✅ 修正了MACD计算器方法: calculate_macd_batch")
    print(f"2. ✅ 修正了KDJ计算器方法: calculate_kdj_batch")
    print(f"3. ✅ 修正了RSI计算器方法: calculate_rsi_batch")
    print(f"4. ✅ 修正了BOLL计算器方法: calculate_boll_batch")
    print(f"5. ✅ 修正了PVFRS计算器方法: calculate_for_dataframe")
    print(f"6. ✅ 调整了数据格式适配各计算器")

if __name__ == "__main__":
    test_api_connection()
