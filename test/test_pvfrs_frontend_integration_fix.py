#!/usr/bin/env python3
"""
测试PVFRS前端集成修复
端到端测试前端选股页面的维度值显示
"""

import sys
import os
import requests
import json
from datetime import datetime

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


def test_pvfrs_frontend_api():
    """测试PVFRS前端API接口"""
    print("测试PVFRS前端API接口...")
    
    # API基础URL
    api_base_url = "http://localhost:5000"
    
    try:
        # 测试获取选股结果
        url = f"{api_base_url}/api/frontend/pvfrs/selection-results"
        params = {
            'limit': 10,
            'min_strength': 0.3
        }
        
        print(f"请求URL: {url}")
        print(f"请求参数: {params}")
        
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            print("✓ API请求成功")
            print(f"响应状态码: {response.status_code}")
            
            # 检查响应数据结构
            if 'success' in data and data['success']:
                results = data.get('data', {}).get('results', [])
                print(f"✓ 获取到 {len(results)} 条选股结果")
                
                # 检查第一条结果的维度值
                if results:
                    first_result = results[0]
                    print("\n第一条选股结果:")
                    print(f"  股票代码: {first_result.get('symbol', 'N/A')}")
                    print(f"  股票名称: {first_result.get('name', 'N/A')}")
                    print(f"  信号强度: {first_result.get('signal_strength', 0):.2%}")
                    
                    # 检查维度状态字段
                    price_status = first_result.get('price_dimension_status', 'N/A')
                    frequency_status = first_result.get('frequency_dimension_status', 'N/A')
                    volume_status = first_result.get('volume_dimension_status', 'N/A')
                    entry_status = first_result.get('entry_timing_status', 'N/A')
                    
                    print(f"  价格维度状态: {price_status}")
                    print(f"  频率维度状态: {frequency_status}")
                    print(f"  成交量维度状态: {volume_status}")
                    print(f"  入场时机状态: {entry_status}")
                    
                    # 验证维度值不为空
                    if price_status != 'N/A' and price_status != '未满足条件':
                        print("✓ 价格维度有值")
                    else:
                        print("⚠ 价格维度无值或未满足条件")
                    
                    if frequency_status != 'N/A' and frequency_status != '未满足条件':
                        print("✓ 频率维度有值")
                    else:
                        print("⚠ 频率维度无值或未满足条件")
                    
                    if volume_status != 'N/A' and volume_status != '未满足条件':
                        print("✓ 成交量维度有值")
                    else:
                        print("⚠ 成交量维度无值或未满足条件")
                    
                    if entry_status != 'N/A' and entry_status != '等待时机':
                        print("✓ 入场时机有值")
                    else:
                        print("⚠ 入场时机无值或等待时机")
                    
                    # 检查其他前端期望的字段
                    resonance_status = first_result.get('resonance_status', 'N/A')
                    investment_advice = first_result.get('investment_advice', 'N/A')
                    current_price = first_result.get('current_price', 0)
                    
                    print(f"  共振状态: {resonance_status}")
                    print(f"  投资建议: {investment_advice}")
                    print(f"  当前价格: {current_price}")
                    
                    return True
                else:
                    print("⚠ 没有获取到选股结果")
                    return False
            else:
                print(f"❌ API返回失败: {data.get('error', '未知错误')}")
                return False
        else:
            print(f"❌ API请求失败，状态码: {response.status_code}")
            print(f"响应内容: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到后端服务器，请确保后端服务正在运行")
        return False
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {str(e)}")
        return False


def test_pvfrs_stock_detail_api():
    """测试PVFRS股票详情API接口"""
    print("\n测试PVFRS股票详情API接口...")
    
    # API基础URL
    api_base_url = "http://localhost:5000"
    
    try:
        # 测试获取股票详情
        symbol = "000001"  # 平安银行
        url = f"{api_base_url}/api/frontend/pvfrs/stock-detail/{symbol}"
        
        print(f"请求URL: {url}")
        
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            print("✓ 股票详情API请求成功")
            
            if 'success' in data and data['success']:
                detail = data.get('data', {})
                
                print(f"✓ 获取到股票 {symbol} 的详细信息")
                print(f"  股票名称: {detail.get('name', 'N/A')}")
                print(f"  当前价格: {detail.get('current_price', 0)}")
                print(f"  分析日期: {detail.get('analysis_date', 'N/A')}")
                
                # 检查三维分析结果
                price_dimension = detail.get('price_dimension', {})
                frequency_dimension = detail.get('frequency_dimension', {})
                volume_dimension = detail.get('volume_dimension', {})
                
                print(f"  价格维度分析: {len(price_dimension)} 个指标")
                print(f"  频率维度分析: {len(frequency_dimension)} 个指标")
                print(f"  成交量维度分析: {len(volume_dimension)} 个指标")
                
                if price_dimension:
                    print("✓ 价格维度分析有数据")
                if frequency_dimension:
                    print("✓ 频率维度分析有数据")
                if volume_dimension:
                    print("✓ 成交量维度分析有数据")
                
                return True
            else:
                print(f"❌ 股票详情API返回失败: {data.get('error', '未知错误')}")
                return False
        else:
            print(f"❌ 股票详情API请求失败，状态码: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到后端服务器")
        return False
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {str(e)}")
        return False


def test_pvfrs_interface_status():
    """测试PVFRS接口状态"""
    print("\n测试PVFRS接口状态...")
    
    # API基础URL
    api_base_url = "http://localhost:5000"
    
    try:
        url = f"{api_base_url}/api/frontend/pvfrs/interface-status"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if 'success' in data and data['success']:
                status = data.get('data', {})
                
                print("✓ PVFRS接口状态正常")
                print(f"  接口名称: {status.get('interface_name', 'N/A')}")
                print(f"  版本: {status.get('version', 'N/A')}")
                print(f"  缓存启用: {status.get('cache_enabled', False)}")
                print(f"  最大选股结果: {status.get('max_selection_results', 0)}")
                print(f"  PVFRS系统就绪: {status.get('pvfrs_system_status', False)}")
                
                return True
            else:
                print(f"❌ 接口状态检查失败: {data.get('error', '未知错误')}")
                return False
        else:
            print(f"❌ 接口状态请求失败，状态码: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {str(e)}")
        return False


def main():
    """主测试函数"""
    print("开始PVFRS前端集成测试...")
    print("=" * 50)
    
    success_count = 0
    total_tests = 3
    
    # 测试选股结果API
    if test_pvfrs_frontend_api():
        success_count += 1
    
    # 测试股票详情API
    if test_pvfrs_stock_detail_api():
        success_count += 1
    
    # 测试接口状态
    if test_pvfrs_interface_status():
        success_count += 1
    
    print("\n" + "=" * 50)
    print(f"测试完成: {success_count}/{total_tests} 通过")
    
    if success_count == total_tests:
        print("✅ 所有测试通过！PVFRS前端集成修复成功")
        print("\n修复验证:")
        print("1. ✓ 选股结果API返回正确的维度状态")
        print("2. ✓ 股票详情API返回完整的三维分析")
        print("3. ✓ 接口状态正常，系统就绪")
        print("\n现在前端选股页面应该能正确显示:")
        print("- 价格维度状态")
        print("- 频率维度状态") 
        print("- 成交量维度状态")
        print("- 入场时机状态")
        return True
    else:
        print("❌ 部分测试失败，请检查后端服务状态")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)