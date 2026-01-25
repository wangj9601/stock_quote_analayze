#!/usr/bin/env python3
"""检查comprehensive_data的实际字段名"""
import requests
import json

def check_comprehensive_fields():
    """检查comprehensive_data的实际字段名"""
    
    print("🔍 检查comprehensive_data的实际字段名")
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
        target_result = results[0]
        task_id = target_result['taskId']
        
        # 获取策略分析报告
        report_url = f"http://localhost:5000/api/admin/pvfrs/backtest/report/{task_id}"
        report_response = requests.get(report_url)
        
        if report_response.status_code != 200:
            print(f"❌ 获取策略分析报告失败: {report_response.status_code}")
            return
            
        report_data = report_response.json()
        report = report_data['data']
        
        if 'comprehensive_data' in report:
            comp_data = report['comprehensive_data']
            
            print("📊 comprehensive_data 完整结构:")
            for key, value in comp_data.items():
                if isinstance(value, dict):
                    print(f"   {key}: Object (字段: {list(value.keys())})")
                elif isinstance(value, list):
                    print(f"   {key}: Array (长度: {len(value)})")
                else:
                    print(f"   {key}: {type(value).__name__}")
            
            # 详细检查trade_analysis字段
            if 'trade_analysis' in comp_data:
                trade = comp_data['trade_analysis']
                print(f"\n💰 trade_analysis 详细字段:")
                for key, value in trade.items():
                    print(f"   {key}: {value} ({type(value).__name__})")
        else:
            print("❌ comprehensive_data 字段不存在")
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")

if __name__ == "__main__":
    check_comprehensive_fields()
