#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
详细测试报告API
"""

import requests
import json

def test_reports_detailed():
    """详细测试报告API"""
    
    print("=== 详细测试报告API ===\n")
    
    try:
        # 测试报告列表API
        response = requests.get('http://localhost:5000/api/admin/pvfrs/reports')
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"状态码: {response.status_code}")
            print(f"成功: {data.get('success')}")
            print(f"消息: {data.get('message')}")
            print(f"总数: {data.get('total')}")
            print(f"页码: {data.get('page')}")
            print(f"每页: {data.get('pageSize')}")
            print(f"总页数: {data.get('totalPages')}")
            
            reports = data.get('data', [])
            print(f"\n获取到 {len(reports)} 条报告")
            
            for i, report in enumerate(reports[:3], 1):
                print(f"\n报告 {i}:")
                print(f"  ID: {report.get('id')}")
                print(f"  标题: {report.get('title')}")
                print(f"  类型: {report.get('type')}")
                print(f"  股票代码: {report.get('stockCode')}")
                print(f"  总收益率: {report.get('totalReturn'):.2f}%")
                print(f"  年化收益率: {report.get('annualReturn'):.2f}%")
                print(f"  最大回撤: {report.get('maxDrawdown'):.2f}%")
                print(f"  夏普比率: {report.get('sharpeRatio'):.4f}")
                print(f"  胜率: {report.get('winRate'):.2f}%")
                print(f"  总交易数: {report.get('totalTrades')}")
                print(f"  创建时间: {report.get('createdAt')}")
                print(f"  任务ID: {report.get('taskId')}")
            
            print(f"\n✅ 报告列表API测试成功！")
            
        else:
            print(f"❌ 请求失败，状态码: {response.status_code}")
            print(f"响应: {response.text}")
            
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")

if __name__ == "__main__":
    test_reports_detailed()
