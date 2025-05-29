#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import akshare as ak
import pandas as pd

def test_akshare_indices():
    """测试akshare指数数据获取"""
    try:
        print("=== 测试akshare指数数据获取 ===")
        
        # 获取实时指数数据
        df = ak.stock_zh_index_spot_em()
        print(f"总共获取到 {len(df)} 条指数数据")
        
        # 显示前几条数据的结构
        print("\n数据列名:")
        print(df.columns.tolist())
        
        print("\n前5条数据:")
        print(df[['代码', '名称', '最新价', '涨跌额', '涨跌幅']].head())
        
        # 查找我们需要的指数
        target_indices = {
            '000001': '上证指数',
            '399001': '深证成指', 
            '399006': '创业板指',
            '000300': '沪深300'
        }
        
        print("\n=== 查找目标指数 ===")
        for code, expected_name in target_indices.items():
            result = df[df['代码'] == code]
            print(f"\n指数代码 {code} ({expected_name}):")
            if not result.empty:
                row = result.iloc[0]
                print(f"  实际名称: {row['名称']}")
                print(f"  最新价: {row['最新价']}")
                print(f"  涨跌额: {row['涨跌额']}")
                print(f"  涨跌幅: {row['涨跌幅']}%")
                print(f"  成交量: {row.get('成交量', 'N/A')}")
                print(f"  成交额: {row.get('成交额', 'N/A')}")
            else:
                print(f"  ❌ 未找到代码为 {code} 的指数")
                
        # 查找相似的指数
        print("\n=== 查找深证和创业板相关指数 ===")
        shenzhen_indices = df[df['名称'].str.contains('深证|深圳', na=False)]
        print("深证相关指数:")
        if not shenzhen_indices.empty:
            print(shenzhen_indices[['代码', '名称', '最新价']].head())
        else:
            print("未找到深证相关指数")
            
        chuangye_indices = df[df['名称'].str.contains('创业|创业板', na=False)]
        print("\n创业板相关指数:")
        if not chuangye_indices.empty:
            print(chuangye_indices[['代码', '名称', '最新价']].head())
        else:
            print("未找到创业板相关指数")
            
        # 查找包含数字的相似代码
        print("\n=== 查找相似代码的指数 ===")
        codes_like_399001 = df[df['代码'].str.startswith('399')]
        print("以399开头的指数:")
        if not codes_like_399001.empty:
            print(codes_like_399001[['代码', '名称', '最新价']].head(10))
            
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_akshare_indices() 