#!/usr/bin/env python3
"""测试交易记录一致性"""
import requests
import json

def test_trades_consistency():
    """测试策略管理任务详情和策略分析报告中的交易记录一致性"""
    
    print("🔍 测试交易记录一致性")
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
        
        # 2. 获取策略管理-任务详情中的交易记录
        print(f"\n2. 获取策略管理-任务详情中的交易记录...")
        trades_url = f"http://localhost:5000/api/admin/pvfrs/backtest/trades/{task_id}"
        
        trades_response = requests.get(trades_url)
        if trades_response.status_code != 200:
            print(f"❌ 获取任务详情交易记录失败: {trades_response.status_code}")
            return
            
        trades_data = trades_response.json()
        if not trades_data.get('success') or not trades_data.get('data'):
            print("❌ 任务详情交易记录为空")
            return
            
        task_trades = trades_data['data']
        print(f"✅ 任务详情交易记录: {len(task_trades)} 条")
        
        # 3. 获取策略分析报告中的交易记录
        print(f"\n3. 获取策略分析报告中的交易记录...")
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
        report_trades = report.get('trades', [])
        print(f"✅ 策略分析报告交易记录: {len(report_trades)} 条")
        
        # 4. 比较交易记录
        print(f"\n4. 比较交易记录一致性...")
        
        print(f"任务详情交易记录数: {len(task_trades)}")
        print(f"策略分析报告交易记录数: {len(report_trades)}")
        
        if len(task_trades) == len(report_trades):
            print("✅ 交易记录数量一致")
            
            # 比较具体内容
            consistent = True
            for i, (task_trade, report_trade) in enumerate(zip(task_trades, report_trades)):
                # 比较关键字段
                key_fields = ['stock_code', 'entry_price', 'exit_price', 'quantity', 'pnl']
                for field in key_fields:
                    task_field = task_trade.get(field)
                    report_field = report_trade.get(field)
                    
                    if task_field != report_field:
                        print(f"❌ 交易记录 {i+1} 字段 {field} 不一致:")
                        print(f"   任务详情: {task_field}")
                        print(f"   策略报告: {report_field}")
                        consistent = False
            
            if consistent:
                print("✅ 所有交易记录内容一致")
            else:
                print("❌ 交易记录内容不一致")
        else:
            print("❌ 交易记录数量不一致")
        
        # 5. 显示交易记录样例
        if task_trades and report_trades:
            print(f"\n5. 交易记录样例对比:")
            print("任务详情第一条记录:")
            print(json.dumps(task_trades[0], indent=2, ensure_ascii=False))
            print("\n策略分析报告第一条记录:")
            print(json.dumps(report_trades[0], indent=2, ensure_ascii=False))
        
        print("\n✅ 测试完成")
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")

if __name__ == "__main__":
    test_trades_consistency()
