#!/usr/bin/env python3
"""完整的交易明细测试"""
import requests
import json
import time

def test_complete_trades_flow():
    """完整的交易明细测试流程"""
    
    print("🔍 完整的交易明细测试流程")
    print("="*50)
    
    # 1. 创建回测任务
    print("1. 创建回测任务...")
    create_url = "http://localhost:5000/api/admin/pvfrs/backtest/create"
    test_config = {
        "name": "测试交易明细",
        "stock_codes": ["600000"],
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
        "initial_capital": 100000,
        "strategy_config": {
            "buy_bias_min": -0.05,
            "sell_bias_max": 0.15,
            "signal_threshold": 0.6
        }
    }
    
    try:
        create_response = requests.post(create_url, json=test_config)
        if create_response.status_code != 200:
            print(f"❌ 任务创建失败: {create_response.status_code}")
            return
            
        create_data = create_response.json()
        if not create_data.get('success'):
            print("❌ 任务创建失败")
            return
            
        task_id = create_data['data']['task_id']
        print(f"✅ 任务创建成功: {task_id}")
        
        # 2. 等待任务完成
        print("\n2. 等待任务完成...")
        progress_url = f"http://localhost:5000/api/admin/pvfrs/backtest/progress/{task_id}"
        
        for i in range(10):
            progress_response = requests.get(progress_url)
            if progress_response.status_code == 200:
                progress_data = progress_response.json()
                if progress_data.get('data'):
                    task_data = progress_data['data']
                    status = task_data.get('status')
                    print(f"   轮询 {i+1}: 状态={status}, 进度={task_data.get('progress_percentage', 0)}%")
                    
                    if status == 'completed':
                        print("✅ 任务完成")
                        break
                    elif status == 'failed':
                        print("❌ 任务失败")
                        return
                    
            time.sleep(1)
        
        # 3. 获取交易明细
        print(f"\n3. 获取交易明细...")
        trades_url = f"http://localhost:5000/api/admin/pvfrs/backtest/trades/{task_id}"
        
        trades_response = requests.get(trades_url)
        if trades_response.status_code != 200:
            print(f"❌ 获取交易明细失败: {trades_response.status_code}")
            print(f"错误信息: {trades_response.text}")
            return
            
        trades_data = trades_response.json()
        if not trades_data.get('success') or not trades_data.get('data'):
            print("❌ 交易明细为空")
            return
            
        trades = trades_data['data']
        print(f"✅ 获取到 {len(trades)} 条交易记录")
        
        # 4. 验证字段映射
        print(f"\n4. 验证字段映射...")
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
            print(f"  ✅ 孅在字段: {len(present_fields)}/{len(expected_fields)}")
            print(f"  ❌ 缺失字段: {missing_fields}")
            
            if len(missing_fields) == 0:
                print("\n🎉 所有字段映射正确！前端应该可以正常显示交易明细了。")
            else:
                print(f"\n⚠️ 还有 {len(missing_fields)} 个字段缺失，需要进一步修复。")
            
            # 显示完整的交易记录
            print(f"\n完整的第一条交易记录:")
            print(json.dumps(first_trade, indent=2, ensure_ascii=False))
        
        print("\n✅ 测试完成")
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")

if __name__ == "__main__":
    test_complete_trades_flow()
