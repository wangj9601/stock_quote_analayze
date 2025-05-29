#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import akshare as ak
import pandas as pd

def test_specific_indices():
    """测试特定的指数获取方法"""
    try:
        print("=== 测试深证成指获取 ===")
        # 尝试直接获取深证成指
        try:
            sz_data = ak.stock_zh_index_spot(symbol="深证成指")
            print(f"深证成指数据: {sz_data}")
        except Exception as e:
            print(f"获取深证成指失败: {e}")

        print("\n=== 测试创业板指获取 ===")
        # 尝试直接获取创业板指
        try:
            cy_data = ak.stock_zh_index_spot(symbol="创业板指")
            print(f"创业板指数据: {cy_data}")
        except Exception as e:
            print(f"获取创业板指失败: {e}")

        print("\n=== 尝试A股指数列表 ===")
        # 尝试获取A股指数信息列表
        try:
            index_list = ak.stock_zh_index_spot()
            print(f"获取到指数数量: {len(index_list)}")
            
            # 查找深证相关
            shenzhen = index_list[index_list['名称'].str.contains('深证|深圳', na=False)]
            if not shenzhen.empty:
                print("\n深证相关指数:")
                print(shenzhen[['代码', '名称', '最新价']].head())
            
            # 查找创业板相关
            chuangye = index_list[index_list['名称'].str.contains('创业', na=False)]
            if not chuangye.empty:
                print("\n创业板相关指数:")
                print(chuangye[['代码', '名称', '最新价']].head())
                
        except Exception as e:
            print(f"获取A股指数列表失败: {e}")

        print("\n=== 尝试实时指数数据 ===")
        # 尝试用实时接口获取所有指数
        try:
            df_rt = ak.index_zh_a_hist(symbol="000001", period="daily", start_date="20250524", end_date="20250524")
            print(f"上证指数历史数据: {df_rt}")
        except Exception as e:
            print(f"获取上证指数历史数据失败: {e}")

        # 尝试深证成指历史数据
        try:
            df_sz = ak.index_zh_a_hist(symbol="399001", period="daily", start_date="20250524", end_date="20250524")
            print(f"深证成指历史数据: {df_sz}")
        except Exception as e:
            print(f"获取深证成指历史数据失败: {e}")

        # 尝试创业板指历史数据
        try:
            df_cy = ak.index_zh_a_hist(symbol="399006", period="daily", start_date="20250524", end_date="20250524")
            print(f"创业板指历史数据: {df_cy}")
        except Exception as e:
            print(f"获取创业板指历史数据失败: {e}")

    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_specific_indices() 