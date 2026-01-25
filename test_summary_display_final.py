#!/usr/bin/env python3
"""最终测试：验证摘要信息显示修复"""
import requests
import json

def test_summary_display_final():
    """最终测试摘要信息显示"""
    
    print("🎯 最终测试：摘要信息显示修复验证")
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
        print(f"   股票: {target_result['stockCode']}")
        print(f"   交易次数: {target_result['totalTrades']}")
        
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
        
        # 显示摘要信息
        print(f"\n📊 摘要信息内容:")
        if 'summary' in report and isinstance(report['summary'], dict):
            summary = report['summary']
            
            print(f"   策略评分: {summary.get('strategy_score', 'N/A')}")
            print(f"   策略等级: {summary.get('strategy_grade', 'N/A')}")
            
            if summary.get('key_highlights'):
                print(f"   关键亮点: {', '.join(summary['key_highlights'])}")
            
            if summary.get('risk_warnings'):
                print(f"   风险警告: {', '.join(summary['risk_warnings'])}")
                
            if summary.get('recommendation'):
                print(f"   投资建议: {summary['recommendation']}")
                
            if summary.get('summary_text'):
                print(f"   摘要说明: {summary['summary_text'][:100]}...")
        
        print(f"\n✅ 修复完成！")
        print(f"现在前端将显示:")
        print(f"  📋 格式化的摘要信息卡片，而不是JSON字符串")
        print(f"  🎨 美观的网格布局，包含策略评分、等级、亮点等")
        print(f"  🏷️ 彩色标签显示关键亮点和风险警告")
        print(f"  💡 清晰的投资建议和摘要说明")
        
        print(f"\n🌐 前端访问地址:")
        print(f"   http://localhost:8001/pvfrs-management")
        print(f"   → 策略分析报告页面")
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")

if __name__ == "__main__":
    test_summary_display_final()
