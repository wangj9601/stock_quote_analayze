#!/usr/bin/env python3
"""测试详细分析部分显示"""
import requests
import json

def test_detailed_analysis_display():
    """测试详细分析部分是否正确显示"""
    
    print("🔍 测试详细分析部分显示")
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
        
        # 检查详细分析相关字段
        print(f"\n📊 详细分析数据检查:")
        
        # 检查 details 字段
        if 'details' in report:
            print(f"   ✅ details 字段存在: {type(report['details'])}")
        else:
            print(f"   ❌ details 字段不存在")
        
        # 检查 visualization_data 字段
        if 'visualization_data' in report:
            viz_data = report['visualization_data']
            print(f"   ✅ visualization_data 字段存在")
            
            # 检查性能指标
            if 'performance_metrics' in viz_data:
                perf = viz_data['performance_metrics']
                print(f"   📈 性能指标:")
                print(f"      总收益率: {(perf['total_return'] * 100):.2f}%")
                print(f"      年化收益率: {(perf['annual_return'] * 100):.2f}%")
                print(f"      最大回撤: {(perf['max_drawdown'] * 100):.2f}%")
                print(f"      夏普比率: {perf['sharpe_ratio']:.2f}")
                print(f"      胜率: {(perf['win_rate'] * 100):.2f}%")
            
            # 检查交易分析
            if 'trade_analysis' in viz_data:
                trade = viz_data['trade_analysis']
                print(f"   💰 交易分析:")
                print(f"      总交易次数: {trade['total_trades']}")
                print(f"      盈利交易: {trade['winning_trades']}")
                print(f"      亏损交易: {trade['losing_trades']}")
                print(f"      盈利因子: {trade['profit_factor']:.2f}")
            
            # 检查风险指标
            if 'risk_metrics' in viz_data:
                risk = viz_data['risk_metrics']
                print(f"   📈 风险指标:")
                print(f"      最大连续亏损: {risk['max_consecutive_losses']}次")
                print(f"      最大连续盈利: {risk['max_consecutive_wins']}次")
                print(f"      VaR (95%): ¥{risk['var_95']:.2f}")
                print(f"      最大单日亏损: ¥{risk['max_daily_loss']:.2f}")
            
            # 检查交易分布
            if 'trade_distribution' in viz_data:
                dist = viz_data['trade_distribution']
                print(f"   📊 交易分布:")
                print(f"      平均盈利: ¥{dist['avg_win']:.2f}")
                print(f"      平均亏损: ¥{dist['avg_loss']:.2f}")
                print(f"      平均持仓天数: {dist['avg_holding_days']:.1f}天")
        else:
            print(f"   ❌ visualization_data 字段不存在")
        
        print(f"\n✅ 测试完成！")
        print(f"现在前端应该能够显示:")
        print(f"  📊 性能指标分析 - 显示总收益率、年化收益率、最大回撤等")
        print(f"  💰 交易分析 - 显示交易次数、盈利因子、盈亏分布等")
        print(f"  📈 风险分析 - 显示连续盈亏、VaR、最大单日亏损等")
        print(f"  🎨 美观的卡片布局和颜色区分")
        
        print(f"\n🌐 前端访问地址:")
        print(f"   http://localhost:8001/pvfrs-management")
        print(f"   → 策略分析报告页面 → 详细分析部分")
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")

if __name__ == "__main__":
    test_detailed_analysis_display()
