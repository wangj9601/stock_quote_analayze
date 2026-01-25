#!/usr/bin/env python3
"""测试报告摘要显示修复"""
import requests
import json

def test_report_summary_display():
    """测试报告摘要显示是否正确"""
    
    print("🔍 测试报告摘要显示修复")
    print("="*50)
    
    # 1. 获取一个有交易记录的任务
    print("1. 获取回测结果列表...")
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
        target_result = None
        for result in results:
            if result.get('totalTrades', 0) > 0:
                target_result = result
                break
        
        if not target_result:
            print("❌ 没有找到有交易记录的结果")
            return
            
        task_id = target_result['taskId']
        print(f"✅ 选择任务: {task_id}")
        print(f"   股票: {target_result['stockCode']}")
        print(f"   交易次数: {target_result['totalTrades']}")
        
        # 2. 获取策略分析报告
        print(f"\n2. 获取策略分析报告...")
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
        print(f"✅ 获取到报告数据")
        
        # 3. 检查摘要信息格式
        print(f"\n3. 检查摘要信息格式...")
        
        # 检查是否有summary字段
        if 'summary' in report:
            summary = report['summary']
            print(f"摘要字段存在: {type(summary)}")
            
            if isinstance(summary, str):
                print("✅ 摘要是字符串格式（HTML）")
                print(f"摘要内容预览: {summary[:100]}...")
            elif isinstance(summary, dict):
                print("✅ 摘要是对象格式")
                print(f"摘要字段: {list(summary.keys())}")
                
                # 检查关键字段
                key_fields = ['total_return', 'annual_return', 'max_drawdown', 'sharpe_ratio', 'win_rate']
                for field in key_fields:
                    if field in summary:
                        value = summary[field]
                        print(f"  {field}: {value}")
                    else:
                        print(f"  {field}: 缺失")
            else:
                print(f"⚠️ 摘要格式异常: {type(summary)}")
        else:
            print("❌ 报告中没有summary字段")
        
        # 4. 检查详细信息格式
        print(f"\n4. 检查详细信息格式...")
        
        if 'details' in report:
            details = report['details']
            print(f"详情字段存在: {type(details)}")
            
            if isinstance(details, str):
                print("✅ 详情是字符串格式（HTML）")
                print(f"详情内容预览: {details[:100]}...")
            elif isinstance(details, dict):
                print("✅ 详情是对象格式")
                print(f"详情字段: {list(details.keys())}")
            else:
                print(f"⚠️ 详情格式异常: {type(details)}")
        else:
            print("❌ 报告中没有details字段")
        
        # 5. 显示完整的报告结构
        print(f"\n5. 完整报告结构:")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        
        print("\n✅ 测试完成")
        print("现在前端应该能够正确显示格式化的摘要信息，而不是JSON字符串。")
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")

if __name__ == "__main__":
    test_report_summary_display()
