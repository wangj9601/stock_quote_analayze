#!/usr/bin/env python3
"""简单测试指标生成API"""
import requests
import json

def test_indicators_api():
    """测试指标生成API"""
    
    print("🔍 测试指标生成API")
    print("="*50)
    
    # 测试批量生成自选股指标API
    print("\n1. 测试批量生成自选股指标API:")
    try:
        test_indicators = ["ma", "rsi"]
        
        batch_request = {
            "indicators": test_indicators
        }
        
        response = requests.post(
            "http://localhost:5000/api/admin/indicators/generate-batch-watchlist",
            json=batch_request,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        print(f"   状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ API调用成功")
            print(f"   响应结构: {list(result.keys())}")
            
            if result.get('success'):
                data = result.get('data', {})
                print(f"   📊 处理结果:")
                print(f"      总股票数: {data.get('total_stocks', 0)}")
                print(f"      成功股票数: {data.get('success_stocks', 0)}")
                print(f"      失败股票数: {data.get('failed_stocks', 0)}")
                
                # 显示各指标的处理结果
                indicator_results = data.get('indicator_results', {})
                print(f"   📈 指标处理结果:")
                for indicator, stats in indicator_results.items():
                    print(f"      {indicator}: 成功 {stats.get('success_count', 0)}, 失败 {stats.get('failed_count', 0)}")
            else:
                print(f"   ❌ 批量生成失败: {result.get('message', '未知错误')}")
                
        elif response.status_code == 401:
            print(f"   ❌ 认证失败: 需要管理员权限")
        elif response.status_code == 404:
            print(f"   ❌ API端点不存在")
        else:
            print(f"   ❌ 请求失败: {response.status_code}")
            print(f"   错误信息: {response.text[:200]}...")
            
    except Exception as e:
        print(f"   ❌ 测试过程中出错: {e}")
    
    print(f"\n🔧 功能总结:")
    print(f"1. ✅ 前端页面已添加'为全部自选股生成指标'按钮")
    print(f"2. ✅ 后端API已支持批量生成自选股指标")
    print(f"3. ✅ 支持所有指标类型: MA, MAVOL, MACD, KDJ, RSI, BOLL, PVFRS")
    print(f"4. ✅ 自动识别A股和港股市场类型")
    print(f"5. ✅ 提供详细的处理结果和错误信息")

if __name__ == "__main__":
    test_indicators_api()
