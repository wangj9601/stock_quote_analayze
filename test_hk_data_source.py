#!/usr/bin/env python3
"""测试港股数据源"""
import akshare as ak
import pandas as pd
import json

def test_hk_data_sources():
    """测试港股数据源"""
    
    print("🔍 测试港股数据源")
    print("="*50)
    
    # 测试第一个接口
    print("\n1. 测试 ak.stock_hk_spot_em():")
    try:
        df1 = ak.stock_hk_spot_em()
        if df1 is not None:
            print(f"   ✅ 接口调用成功")
            print(f"   数据形状: {df1.shape}")
            print(f"   列名: {list(df1.columns)}")
            if not df1.empty:
                print(f"   示例数据:")
                print(df1.head(2).to_string())
            else:
                print(f"   ⚠️ 数据为空")
        else:
            print(f"   ❌ 返回None")
    except Exception as e:
        print(f"   ❌ 调用失败: {e}")
        print(f"   错误类型: {type(e).__name__}")
    
    # 测试第二个接口
    print("\n2. 测试 ak.stock_hk_spot():")
    try:
        df2 = ak.stock_hk_spot()
        if df2 is not None:
            print(f"   ✅ 接口调用成功")
            print(f"   数据形状: {df2.shape}")
            print(f"   列名: {list(df2.columns)}")
            if not df2.empty:
                print(f"   示例数据:")
                print(df2.head(2).to_string())
            else:
                print(f"   ⚠️ 数据为空")
        else:
            print(f"   ❌ 返回None")
    except Exception as e:
        print(f"   ❌ 调用失败: {e}")
        print(f"   错误类型: {type(e).__name__}")
    
    # 测试JSON解析（模拟错误）
    print("\n3. 测试JSON解析问题:")
    try:
        # 模拟空字符串导致的JSON解析错误
        test_data = ""
        result = json.loads(test_data)
        print(f"   JSON解析结果: {result}")
    except json.JSONDecodeError as e:
        print(f"   ❌ JSON解析错误: {e}")
        print(f"   这就是 'Expecting value: line 1 column 1 (char 0)' 错误")
    
    print(f"\n🔧 诊断建议:")
    print(f"1. 如果港股接口返回空数据，可能是:")
    print(f"   - 港股市场休市")
    print(f"   - 网络连接问题")
    print(f"   - akshare接口问题")
    print(f"2. 建议在数据采集前添加更详细的数据验证")
    print(f"3. 添加重试机制和更好的错误处理")

if __name__ == "__main__":
    test_hk_data_sources()
