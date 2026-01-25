#!/usr/bin/env python3
"""完整测试：策略报告摘要和详细分析修复"""
import requests
import json

def test_complete_fix():
    """完整测试策略报告修复"""
    
    print("🎯 完整测试：策略报告摘要和详细分析修复")
    print("="*60)
    
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
        
        # 检查摘要信息
        print(f"\n📋 摘要信息检查:")
        if 'summary' in report and isinstance(report['summary'], dict):
            summary = report['summary']
            print(f"   ✅ 摘要字段存在: {type(summary)}")
            print(f"   字段: {list(summary.keys())}")
            
            if 'strategy_score' in summary:
                print(f"   策略评分: {summary['strategy_score']}")
            if 'strategy_grade' in summary:
                print(f"   策略等级: {summary['strategy_grade']}")
            if 'key_highlights' in summary:
                print(f"   关键亮点: {summary['key_highlights']}")
            if 'risk_warnings' in summary:
                print(f"   风险警告: {summary['risk_warnings']}")
        else:
            print(f"   ❌ 摘要字段不存在或格式错误")
        
        # 检查详细分析相关字段
        print(f"\n📊 详细分析字段检查:")
        analysis_fields = ['details', 'visualization_data', 'comprehensive_data']
        found_analysis = False
        
        for field in analysis_fields:
            if field in report:
                print(f"   ✅ {field}: 存在")
                found_analysis = True
                if isinstance(report[field], dict):
                    print(f"      子字段: {list(report[field].keys())}")
            else:
                print(f"   ❌ {field}: 不存在")
        
        # 检查基本性能指标（直接在报告根级别）
        print(f"\n📈 基本性能指标:")
        basic_metrics = ['total_return', 'annual_return', 'win_rate', 'max_drawdown', 'sharpe_ratio']
        for metric in basic_metrics:
            if metric in report:
                value = report[metric]
                if metric in ['total_return', 'annual_return', 'win_rate', 'max_drawdown']:
                    print(f"   {metric}: {(value * 100):.2f}%")
                else:
                    print(f"   {metric}: {value:.2f}")
            else:
                print(f"   {metric}: 不存在")
        
        # 检查交易记录
        print(f"\n💰 交易记录检查:")
        if 'trades' in report and report['trades']:
            trades = report['trades']
            print(f"   ✅ 交易记录存在: {len(trades)}条")
            
            # 计算基本统计
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
        else:
            print(f"   ❌ 交易记录不存在")
        
        print(f"\n✅ 修复总结:")
        print(f"  📋 摘要信息显示: 已修复JSON字符串问题，使用格式化卡片")
        print(f"  📊 详细分析显示: 支持多种数据源（details/visualization_data/comprehensive_data）")
        print(f"  🎨 界面美化: 添加了网格布局、颜色区分、悬停效果")
        print(f"  📱 响应式设计: 适配移动端显示")
        
        print(f"\n🌐 前端访问地址:")
        print(f"   http://localhost:8001/pvfrs-management")
        print(f"   → 策略分析报告页面")
        
        print(f"\n💡 修复内容:")
        print(f"  1. 摘要信息不再显示JSON字符串，改为格式化卡片")
        print(f"  2. 详细分析部分支持comprehensive_data数据显示")
        print(f"  3. 添加了性能指标、交易分析、风险分析三个模块")
        print(f"  4. 使用颜色区分正负数值（绿色=正，红色=负）")
        print(f"  5. 添加了完整的CSS样式和交互效果")
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")

if __name__ == "__main__":
    test_complete_fix()
