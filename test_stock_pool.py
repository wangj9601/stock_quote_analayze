#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend_core.strategies.pvfrs.frontend_interface import FrontendInterface

def test_stock_pool():
    """测试股票池获取"""
    try:
        print("正在测试股票池获取...")
        interface = FrontendInterface()
        stock_pool = interface._get_stock_pool()
        print(f'股票池大小: {len(stock_pool)}')
        print(f'前10只股票: {stock_pool[:10]}')
        print("测试完成")
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_stock_pool()
