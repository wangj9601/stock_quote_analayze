#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试数据采集API修复
"""

import requests
import json

def test_data_collection_api():
    """测试数据采集API的indicators参数"""
    
    # API基础URL
    BASE_URL = "http://localhost:5000"
    
    # 测试数据
    test_data = {
        "start_date": "2024-01-01",
        "end_date": "2024-01-31",
        "test_mode": True,
        "indicators": ["ma", "kdj"],
        "stock_codes": ["000001"]
    }
    
    try:
        print("测试数据采集API...")
        print(f"请求数据: {json.dumps(test_data, indent=2)}")
        
        # 发送请求
        response = requests.post(
            f"{BASE_URL}/api/data-collection/historical",
            json=test_data,
            timeout=10
        )
        
        print(f"状态码: {response.status_code}")
        print(f"响应数据: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200:
            print("✅ API调用成功，indicators参数修复有效")
            return True
        else:
            print(f"❌ API调用失败: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        return False

if __name__ == "__main__":
    test_data_collection_api()
