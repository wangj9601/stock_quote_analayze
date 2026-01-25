#!/usr/bin/env python3
"""测试报告详细分析部分"""
import requests
import json

def test_report_details():
    """测试报告详细分析数据"""
    
    print("🔍 测试报告详细分析数据")
    print("="*50)
    
    # 获取最新的报告数据
    reports_url = "http://localhost:5000/api/admin/pvfrs/reports"
    
    try:
        reports_response = requests.get(reports_url)
        if reports_response.status_code != 200:
            print(f"❌ 获取报告列表失败: {reports_response.status_code}")
            return
            
        reports_data = reports_response.json()
        if not reports_data.get('success') or not reports_data.get('data'):
            print("❌ 报告列表为空")
            return
            
        results = reports_data['data']
        if not results:
            print("❌ 没有找到报告结果")
            return
            
        # 取第一个结果
        target_result = results[0]
        task_id = target_result['taskId']
        
        print(f"✅ 选择任务: {task_id}")
        
        # 获取策略分析报告
        print(f"\n🔍 获取策略分析报告...")
        report_url = f"http://localhost:5000/api/admin/pvfrs/backtest/report/{task_id}"
        
        report_response = requests.get(report_url)
        if report_response.status_code != 200:
            print(f"❌ 获取策略分析报告失败: {report_response.status_code}")
            return
            
        report_data = report_response.json()
        if not report_data.get('success') or not report_data.get('data'):
            print("❌ 策略分析报告为空")
            return
            
        report = report_data['data']
        
        # 检查所有字段
        print(f"\n📊 报告数据字段:")
        for key in report.keys():
            value = report[key]
            if isinstance(value, str):
                print(f"   {key}: {type(value).__name__} (长度: {len(value)})")
            elif isinstance(value, list):
                print(f"   {key}: {type(value).__name__} (数量: {len(value)})")
            else:
                print(f"   {key}: {type(value).__name__}")
        
        # 特别检查 details 字段
        print(f"\n🔍 详细分析检查:")
        if 'details' in report:
            details = report['details']
            print(f"   details 字段存在: {type(details)}")
            if isinstance(details, str):
                print(f"   内容长度: {len(details)}")
                print(f"   内容预览: {details[:200]}...")
            elif isinstance(details, dict):
                print(f"   字段: {list(details.keys())}")
            else:
                print(f"   内容: {details}")
        else:
            print("   ❌ details 字段不存在")
        
        # 检查其他可能包含详细分析的字段
        print(f"\n🔍 其他可能的分析字段:")
        possible_fields = ['analysis', 'detailed_analysis', 'performance_analysis', 'trade_analysis', 'risk_analysis']
        for field in possible_fields:
            if field in report:
                print(f"   ✅ {field}: 存在")
            else:
                print(f"   ❌ {field}: 不存在")
        
        # 显示完整的报告结构
        print(f"\n📋 完整报告结构:")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")

if __name__ == "__main__":
    test_report_details()
