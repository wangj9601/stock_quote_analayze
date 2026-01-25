#!/usr/bin/env python3
"""测试港股数据采集修复"""
import requests
import json
import time

def test_hk_collection_fix():
    """测试港股数据采集修复"""
    
    print("🔍 测试港股数据采集修复")
    print("="*50)
    
    # 启动港股数据采集任务
    try:
        print("启动港股数据采集任务...")
        
        collection_request = {
            "market": "HK",
            "stock_code": "",  # 空字符串表示采集所有港股
            "full_collection_mode": False
        }
        
        response = requests.post(
            "http://localhost:5000/api/data-collection/realtime",
            json=collection_request,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            task_id = result.get('task_id')
            print(f"✅ 任务启动成功: {task_id}")
            
            # 监控任务进度
            print("监控任务进度...")
            max_wait_time = 120  # 最多等待2分钟
            start_time = time.time()
            
            while time.time() - start_time < max_wait_time:
                try:
                    status_response = requests.get(
                        f"http://localhost:5000/api/data-collection/status/{task_id}",
                        timeout=5
                    )
                    
                    if status_response.status_code == 200:
                        status = status_response.json()
                        print(f"任务状态: {status}")
                        
                        if status.get('status') in ['completed', 'failed']:
                            break
                    
                    time.sleep(5)  # 每5秒检查一次
                    
                except Exception as e:
                    print(f"检查状态时出错: {e}")
                    time.sleep(5)
            
            # 获取最终结果
            final_status_response = requests.get(
                f"http://localhost:5000/api/data-collection/status/{task_id}",
                timeout=5
            )
            
            if final_status_response.status_code == 200:
                final_status = final_status_response.json()
                print(f"\n📊 最终任务结果:")
                print(f"状态: {final_status.get('status')}")
                print(f"总股票数: {final_status.get('total_stocks', 0)}")
                print(f"成功: {final_status.get('success_count', 0)}")
                print(f"失败: {final_status.get('failed_count', 0)}")
                print(f"新增数据: {final_status.get('collected_count', 0)}")
                
                if final_status.get('failed_details'):
                    print(f"失败详情: {final_status['failed_details'][:3]}")  # 显示前3个错误
                
                if final_status.get('status') == 'completed':
                    print("✅ 港股数据采集任务完成！")
                else:
                    print("❌ 港股数据采集任务失败")
            else:
                print(f"❌ 获取最终状态失败: {final_status_response.status_code}")
                
        else:
            print(f"❌ 启动任务失败: {response.status_code}")
            print(f"错误信息: {response.text}")
            
    except Exception as e:
        print(f"❌ 测试过程中出错: {e}")

if __name__ == "__main__":
    test_hk_collection_fix()
