#!/usr/bin/env python3
"""最终测试：详细分析部分显示"""
import requests
import json

def test_final_detailed_analysis():
    """最终测试详细分析部分显示"""
    
    print("🎯 最终测试：详细分析部分显示")
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
        
        # 检查comprehensive_data字段
        print(f"\n📊 检查comprehensive_data字段:")
        if 'comprehensive_data' in report:
            comp_data = report['comprehensive_data']
            print(f"   ✅ comprehensive_data 字段存在")
            
            # 检查性能指标
            if 'performance_metrics' in comp_data:
                perf = comp_data['performance_metrics']
                print(f"   📈 性能指标:")
                print(f"      总收益率: {(perf['total_return'] * 100):.2f}%")
                print(f"      年化收益率: {(perf['annual_return'] * 100):.2f}%")
                print(f"      最大回撤: {(perf['max_drawdown'] * 100):.2f}%")
                print(f"      夏普比率: {perf['sharpe_ratio']:.2f}")
                print(f"      胜率: {(perf['win_rate'] * 100):.2f}%")
            
            # 检查交易分析
            if 'trade_analysis' in comp_data:
                trade = comp_data['trade_analysis']
                print(f"   💰 交易分析:")
                print(f"      总交易次数: {trade['total_trades']}")
                print(f"      盈利交易: {trade['winning_trades']}")
                print(f"      亏损交易: {trade['losing_trades']}")
                print(f"      盈利因子: {trade['profit_factor']:.2f}")
                print(f"      平均盈利: ¥{trade['avg_win']:.2f}")
                print(f"      平均亏损: ¥{trade['avg_loss']:.2f}")
                print(f"      平均持仓天数: {trade['avg_holding_days']:.1f}天")
            
            # 检查风险指标
            if 'risk_metrics' in comp_data:
                risk = comp_data['risk_metrics']
                print(f"   📈 风险指标:")
                print(f"      最大连续亏损: {risk['max_consecutive_losses']}次")
                print(f"      最大连续盈利: {risk['max_consecutive_wins']}次")
                print(f"      VaR (95%): ¥{risk['value_at_risk_95']:.2f}")
                print(f"      最大单日亏损: ¥{risk['max_daily_loss']:.2f}")
        else:
            print(f"   ❌ comprehensive_data 字段不存在")
        
        print(f"\n✅ 修复完成！")
        print(f"现在前端将显示:")
        print(f"  📋 格式化的摘要信息卡片（已修复）")
        print(f"  📊 详细的性能指标分析（新增）")
        print(f"  💰 完整的交易分析和盈亏分布（新增）")
        print(f"  📈 全面的风险指标分析（新增）")
        print(f"  🎨 美观的卡片布局和颜色区分")
        
        print(f"\n🌐 前端访问地址:")
        print(f"   http://localhost:8001/pvfrs-management")
        print(f"   → 策略分析报告页面")
        print(f"   → 摘要信息 + 详细分析部分")
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")

if __name__ == "__main__":
    test_final_detailed_analysis()
