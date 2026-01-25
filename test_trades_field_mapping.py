#!/usr/bin/env python3
"""测试交易明细字段映射修复"""
import requests
import json

def test_trades_field_mapping():
    """测试交易明细字段映射"""
    
    print("🔍 测试交易明细字段映射修复")
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
        
        # 2. 获取交易明细
        print(f"\n2. 获取交易明细（验证字段映射）...")
        trades_url = f"http://localhost:5000/api/admin/pvfrs/backtest/trades/{task_id}"
        
        trades_response = requests.get(trades_url)
        if trades_response.status_code != 200:
            print(f"❌ 获取交易明细失败: {trades_response.status_code}")
            return
            
        trades_data = trades_response.json()
        if not trades_data.get('success') or not trades_data.get('data'):
            print("❌ 交易明细为空")
            return
            
        trades = trades_data['data']
        print(f"✅ 获取到 {len(trades)} 条交易记录")
        
        # 3. 验证字段映射
        print(f"\n3. 验证字段映射...")
        if trades:
            first_trade = trades[0]
            print(f"第一条交易记录的字段:")
            
            # 检查前端期望的字段
            expected_fields = [
                'entryDate', 'exitDate', 'entryPrice', 'exitPrice', 
                'pnl', 'pnlPercent', 'holdingDays', 'exitReason'
            ]
            
            missing_fields = []
            present_fields = []
            
            for field in expected_fields:
                if field in first_trade:
                    present_fields.append(field)
                    value = first_trade[field]
                    print(f"  ✅ {field}: {value}")
                else:
                    missing_fields.append(field)
                    print(f"  ❌ {field}: 缺失")
            
            print(f"\n字段映射结果:")
            print(f"  ✅ 存在字段: {len(present_fields)}/{len(expected_fields)}")
            print(f"  ❌ 缺失字段: {missing_fields}")
            
            # 显示完整的交易记录
            print(f"\n完整的第一条交易记录:")
            print(json.dumps(first_trade, indent=2, ensure_ascii=False))
        
        print("\n✅ 测试完成")
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")

if __name__ == "__main__":
    test_trades_field_mapping()
