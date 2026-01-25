#!/usr/bin/env python3
"""测试交易明细API"""
import requests
import json

def test_trades_api():
    """测试交易明细获取"""
    
    # 1. 首先获取一个有交易记录的任务
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
        if not results:
            print("❌ 没有回测结果")
            return
            
        # 找一个有交易记录的结果
        target_result = None
        for result in results:
            if result.get('totalTrades', 0) > 0:
                target_result = result
                break
        
        if not target_result:
            print("❌ 没有找到有交易记录的结果")
            return
            
        task_id = target_result['taskId']
        print(f"✅ 找到有交易记录的任务: {task_id}")
        print(f"   股票: {target_result['stockCode']}")
        print(f"   交易次数: {target_result['totalTrades']}")
        
        # 2. 测试获取交易明细
        print(f"\n2. 获取任务 {task_id} 的交易明细...")
        trades_url = f"http://localhost:5000/api/admin/pvfrs/backtest/trades/{task_id}"
        
        trades_response = requests.get(trades_url)
        print(f"状态码: {trades_response.status_code}")
        
        if trades_response.status_code == 200:
            trades_data = trades_response.json()
            print(f"响应结构: {json.dumps(trades_data, indent=2, ensure_ascii=False)}")
            
            if trades_data.get('success') and trades_data.get('data'):
                trades = trades_data['data']
                print(f"✅ 获取到 {len(trades)} 条交易记录")
                
                if trades:
                    print(f"\n交易明细:")
                    for i, trade in enumerate(trades[:5]):  # 只显示前5条
                        print(f"  交易 {i+1}:")
                        print(f"    股票: {trade.get('stock_code')}")
                        print(f"    买入日期: {trade.get('entry_date')}")
                        print(f"    买入价格: {trade.get('entry_price')}")
                        print(f"    卖出日期: {trade.get('exit_date')}")
                        print(f"    卖出价格: {trade.get('exit_price')}")
                        print(f"    数量: {trade.get('quantity')}")
                        print(f"    盈亏: {trade.get('pnl')}")
                        print(f"    盈亏率: {trade.get('pnl_percent')}%")
                        print()
                else:
                    print("⚠️ 交易记录为空")
            else:
                print("❌ 响应格式错误")
        else:
            print(f"❌ 获取交易明细失败: {trades_response.status_code}")
            print(f"错误信息: {trades_response.text}")
        
        # 3. 测试不存在的任务ID
        print(f"\n3. 测试不存在的任务ID...")
        fake_trades_url = "http://localhost:5000/api/admin/pvfrs/backtest/trades/fake_task_id"
        fake_response = requests.get(fake_trades_url)
        print(f"不存在任务的状态码: {fake_response.status_code}")
        
        print("\n✅ 测试完成")
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")

if __name__ == "__main__":
    test_trades_api()
