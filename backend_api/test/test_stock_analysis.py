#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能分析功能测试脚本
"""

import sys
import os
import requests
import json
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_stock_analysis_api():
    """测试股票分析API"""
    base_url = "http://localhost:8000"
    
    # 测试股票代码
    test_stocks = ["000001", "000002", "600000"]
    
    print("=" * 60)
    print("智能分析API测试")
    print("=" * 60)
    
    for stock_code in test_stocks:
        print(f"\n测试股票: {stock_code}")
        print("-" * 40)
        
        try:
            # 测试完整分析
            response = requests.get(f"{base_url}/analysis/stock/{stock_code}")
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    print("✓ 完整分析API调用成功")
                    analysis_data = data["data"]
                    
                    # 显示价格预测
                    prediction = analysis_data["price_prediction"]
                    print(f"  价格预测: {prediction['target_price']} ({prediction['change_percent']}%)")
                    print(f"  置信度: {prediction['confidence']}%")
                    
                    # 显示交易建议
                    recommendation = analysis_data["trading_recommendation"]
                    print(f"  交易建议: {recommendation['action']} (强度: {recommendation['strength']})")
                    print(f"  风险等级: {recommendation['risk_level']}")
                    
                    # 显示技术指标
                    indicators = analysis_data["technical_indicators"]
                    print(f"  RSI: {indicators['rsi']['value']} ({indicators['rsi']['signal']})")
                    print(f"  MACD: {indicators['macd']['value']} ({indicators['macd']['signal']})")
                    print(f"  KDJ: {indicators['kdj']['value']} ({indicators['kdj']['signal']})")
                    
                else:
                    print(f"✗ 分析失败: {data.get('message', '未知错误')}")
            else:
                print(f"✗ HTTP错误: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print("✗ 连接失败: 请确保后端服务正在运行")
        except Exception as e:
            print(f"✗ 测试异常: {str(e)}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

def test_individual_apis():
    """测试各个独立的API端点"""
    base_url = "http://localhost:8000"
    stock_code = "000001"
    
    print(f"\n测试独立API端点 - 股票: {stock_code}")
    print("-" * 50)
    
    apis = [
        ("技术指标", f"/analysis/technical/{stock_code}"),
        ("价格预测", f"/analysis/prediction/{stock_code}"),
        ("交易建议", f"/analysis/recommendation/{stock_code}"),
        ("关键价位", f"/analysis/levels/{stock_code}"),
        ("分析摘要", f"/analysis/summary/{stock_code}")
    ]
    
    for name, endpoint in apis:
        try:
            response = requests.get(f"{base_url}{endpoint}")
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    print(f"✓ {name} API调用成功")
                else:
                    print(f"✗ {name} API失败: {data.get('message', '未知错误')}")
            else:
                print(f"✗ {name} HTTP错误: {response.status_code}")
        except Exception as e:
            print(f"✗ {name} 测试异常: {str(e)}")

def test_error_handling():
    """测试错误处理"""
    base_url = "http://localhost:8000"
    
    print(f"\n测试错误处理")
    print("-" * 30)
    
    # 测试无效股票代码
    try:
        response = requests.get(f"{base_url}/analysis/stock/INVALID")
        if response.status_code == 400:
            print("✓ 无效股票代码处理正确")
        else:
            print(f"✗ 无效股票代码处理异常: {response.status_code}")
    except Exception as e:
        print(f"✗ 错误处理测试异常: {str(e)}")

if __name__ == "__main__":
    print("智能分析功能测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 测试完整分析API
    test_stock_analysis_api()
    
    # 测试独立API端点
    test_individual_apis()
    
    # 测试错误处理
    test_error_handling() 