#!/usr/bin/env python3
"""检查报告结构"""
import requests
import json

def test_report_structure():
    """检查报告的完整结构"""
    
    print("🔍 检查报告完整结构")
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
        
        print(f"\n📋 报告完整结构:")
        for key, value in report.items():
            if isinstance(value, dict):
                print(f"   {key}: Object (字段: {list(value.keys())})")
            elif isinstance(value, list):
                print(f"   {key}: Array (长度: {len(value)})")
            elif isinstance(value, str):
                print(f"   {key}: String (长度: {len(value)})")
            else:
                print(f"   {key}: {type(value).__name__}")
        
        # 检查是否有其他可能包含详细分析的字段
        print(f"\n🔍 检查详细分析相关字段:")
        analysis_fields = [
            'details', 'visualization_data', 'analysis', 'performance', 
            'metrics', 'statistics', 'trades', 'results', 'data'
        ]
        
        for field in analysis_fields:
            if field in report:
                print(f"   ✅ {field}: 存在")
                if isinstance(report[field], dict):
                    print(f"      子字段: {list(report[field].keys())}")
                elif isinstance(report[field], list):
                    print(f"      数组长度: {len(report[field])}")
            else:
                print(f"   ❌ {field}: 不存在")
        
        # 如果有交易记录，显示一些基本信息
        if 'trades' in report and report['trades']:
            trades = report['trades']
            print(f"\n💰 交易记录信息:")
            print(f"   交易数量: {len(trades)}")
            if trades:
                first_trade = trades[0]
                print(f"   第一笔交易字段: {list(first_trade.keys())}")
                
                # 计算一些基本统计
                total_trades = len(trades)
                winning_trades = len([t for t in trades if t.get('pnl', 0) > 0])
                losing_trades = len([t for t in trades if t.get('pnl', 0) < 0])
                total_pnl = sum(t.get('pnl', 0) for t in trades)
                
                print(f"   总交易次数: {total_trades}")
                print(f"   盈利交易: {winning_trades}")
                print(f"   亏损交易: {losing_trades}")
                print(f"   总盈亏: ¥{total_pnl:.2f}")
                if total_trades > 0:
                    print(f"   胜率: {(winning_trades / total_trades * 100):.2f}%")
        
        print(f"\n✅ 结构检查完成！")
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")

if __name__ == "__main__":
    test_report_structure()
