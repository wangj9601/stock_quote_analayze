#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试报告API修复
"""

import requests

def test_reports_api():
    """测试报告API"""
    
    print("=== 测试报告API修复 ===\n")
    
    base_url = "http://localhost:5000"
    
    try:
        # 测试报告列表API
        print("1. 测试报告列表API...")
        reports_response = requests.get(f"{base_url}/api/admin/pvfrs/reports")
        
        if reports_response.status_code == 200:
            reports_result = reports_response.json()
            print(f"✅ API调用成功，状态码: {reports_response.status_code}")
            print(f"响应结构: {list(reports_result.keys())}")
            
            if 'success' in reports_result and reports_result['success']:
                if 'data' in reports_result:
                    reports = reports_result['data']
                    print(f"📊 获取到 {len(reports)} 条报告")
                    
                    if reports:
                        print("\n前3条报告:")
                        for i, report in enumerate(reports[:3], 1):
                            print(f"{i}. ID: {report.get('id')}")
                            print(f"   标题: {report.get('title')}")
                            print(f"   类型: {report.get('type')}")
                            print(f"   收益率: {report.get('totalReturn', 0):.2%}")
                            print(f"   创建时间: {report.get('createdAt')}")
                            print()
                    else:
                        print("⚠️  报告列表为空")
                else:
                    print("⚠️  响应中没有data字段")
                    print(f"完整响应: {reports_result}")
            else:
                print(f"❌ API返回失败: {reports_result}")
        else:
            print(f"❌ API调用失败，状态码: {reports_response.status_code}")
            print(f"响应内容: {reports_response.text}")
        
        # 测试报告概览API
        print("\n2. 测试报告概览API...")
        overview_response = requests.get(f"{base_url}/api/admin/pvfrs/reports/overview")
        
        if overview_response.status_code == 200:
            overview_result = overview_response.json()
            print(f"✅ 概览API调用成功")
            print(f"概览数据: {overview_result}")
        else:
            print(f"❌ 概览API调用失败，状态码: {overview_response.status_code}")
            print(f"响应内容: {overview_response.text}")
        
        print("\n🎉 测试完成!")
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_reports_api()
