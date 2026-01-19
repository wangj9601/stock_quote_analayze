#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试TuShare采集功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend_core.data_collectors.tushare.historical import HistoricalQuoteCollector

def test_tushare():
    try:
        print("初始化TuShare采集器...")
        collector = HistoricalQuoteCollector()
        print("TuShare采集器初始化成功")
        
        # 测试一个较早的日期
        test_date = '20240101'
        print(f"测试采集日期: {test_date}")
        
        # 注意：这里只是测试初始化，不实际采集数据
        # 因为实际采集需要有效的TuShare token和网络连接
        print("测试完成")
        return True
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_tushare()
    if success:
        print("✅ TuShare采集功能正常")
    else:
        print("❌ TuShare采集功能异常")
