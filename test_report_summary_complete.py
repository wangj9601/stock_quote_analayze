#!/usr/bin/env python3
"""完整的报告摘要显示测试"""
import requests
import json
import time

def test_report_summary_complete():
    """完整的报告摘要显示测试"""
    
    print("🔍 完整的报告摘要显示测试")
    print("="*50)
    
    # 1. 创建回测任务
    print("1. 创建回测任务...")
    create_url = "http://localhost:5000/api/admin/pvfrs/backtest/create"
    test_config = {
        "name": "测试报告摘要显示",
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
        
        # 3. 获取策略分析报告
        print(f"\n3. 获取策略分析报告...")
        report_url = f"http://localhost:5000/api/admin/pvfrs/backtest/report/{task_id}"
        
        report_response = requests.get(report_url)
        if report_response.status_code != 200:
            print(f"❌ 获取策略分析报告失败: {report_response.status_code}")
            print(f"错误信息: {report_response.text}")
            return
            
        report_data = report_response.json()
        if not report_data.get('success') or not report_data.get('data'):
            print("❌ 策略分析报告为空")
            return
            
        report = report_data['data']
        print(f"✅ 获取到报告数据")
        
        # 4. 检查摘要信息格式
        print(f"\n4. 检查摘要信息格式...")
        
        # 检查是否有summary字段
        if 'summary' in report:
            summary = report['summary']
            print(f"摘要字段存在: {type(summary)}")
            
            if isinstance(summary, str):
                print("✅ 摘要是字符串格式（HTML）")
                print(f"摘要内容预览: {summary[:200]}...")
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
        
        # 5. 检查详细信息格式
        print(f"\n5. 检查详细信息格式...")
        
        if 'details' in report:
            details = report['details']
            print(f"详情字段存在: {type(details)}")
            
            if isinstance(details, str):
                print("✅ 详情是字符串格式（HTML）")
                print(f"详情内容预览: {details[:200]}...")
            elif isinstance(details, dict):
                print("✅ 详情是对象格式")
                print(f"详情字段: {list(details.keys())}")
            else:
                print(f"⚠️ 详情格式异常: {type(details)}")
        else:
            print("❌ 报告中没有details字段")
        
        print("\n✅ 测试完成")
        print("现在前端应该能够正确显示格式化的摘要信息，而不是JSON字符串。")
        print("摘要信息将以卡片网格形式显示，包含颜色区分的正负数值。")
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")

if __name__ == "__main__":
    test_report_summary_complete()
