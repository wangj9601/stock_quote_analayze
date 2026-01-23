#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单测试报告API
"""

import requests

def test_reports_simple():
    """简单测试报告API"""
    
    print("测试报告API修复")
    
    base_url = "http://localhost:5000"
    
    try:
        # 测试报告列表API
        print("1. 测试报告列表API...")
        reports_response = requests.get(f"{base_url}/api/admin/pvfrs/reports")
        
        print(f"状态码: {reports_response.status_code}")
        
        if reports_response.status_code == 200:
            reports_result = reports_response.json()
            print(f"响应结构: {list(reports_result.keys())}")
            
            if 'success' in reports_result and reports_result['success']:
                if 'data' in reports_result:
                    reports = reports_result['data']
                    print(f"获取到 {len(reports)} 条报告")
                    
                    if reports:
                        print("前3条报告:")
                        for i, report in enumerate(reports[:3], 1):
                            print(f"{i}. ID: {report.get('id')}")
                            print(f"   标题: {report.get('title')}")
                            print(f"   类型: {report.get('type')}")
                            print(f"   收益率: {report.get('totalReturn', 0):.2%}")
                            print(f"   创建时间: {report.get('createdAt')}")
                    else:
                        print("报告列表为空")
                else:
                    print("响应中没有data字段")
                    print(f"完整响应: {reports_result}")
            else:
                print(f"API返回失败: {reports_result}")
        else:
            print(f"API调用失败，状态码: {reports_response.status_code}")
            print(f"响应内容: {reports_response.text[:500]}...")
        
        print("测试完成!")
        
    except Exception as e:
        print(f"测试失败: {str(e)}")

if __name__ == "__main__":
    test_reports_simple()
