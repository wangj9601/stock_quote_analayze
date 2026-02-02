#!/usr/bin/env python3
"""
港股数据采集修复测试脚本
测试修复后的港股历史数据采集功能
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from direct_hk_historical_collection import fetch_stock_data_from_akshare

def test_hk_data_fetch():
    """测试港股数据获取功能"""
    print("=" * 60)
    print("港股数据采集修复测试")
    print("=" * 60)
    
    # 测试股票列表
    test_stocks = [
        {'code': '00700', 'name': '腾讯控股'},
        {'code': '09988', 'name': '阿里巴巴-SW'},
        {'code': '01810', 'name': '小米集团-W'},
        {'code': '00025', 'name': 'CHEVALIER INT\'L'},  # 原来失败的股票
    ]
    
    # 测试日期范围（最近几天）
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=5)).strftime('%Y%m%d')
    
    print(f"测试日期范围: {start_date} - {end_date}")
    print("-" * 60)
    
    success_count = 0
    fail_count = 0
    
    for stock in test_stocks:
        print(f"测试 {stock['code']} ({stock['name']}):")
        
        try:
            df = fetch_stock_data_from_akshare(
                stock_code=stock['code'],
                start_date=start_date,
                end_date=end_date
            )
            
            if df is not None and not df.empty:
                print(f"  ✓ 成功获取 {len(df)} 条数据")
                print(f"    列名: {list(df.columns)}")
                if len(df) > 0:
                    print(f"    最新日期: {df.iloc[0]['日期']}")
                    print(f"    收盘价: {df.iloc[0]['收盘']}")
                success_count += 1
            else:
                print(f"  ✗ 无数据")
                fail_count += 1
                
        except Exception as e:
            print(f"  ✗ 错误: {e}")
            fail_count += 1
        
        print()
    
    print("=" * 60)
    print(f"测试结果: 成功 {success_count} 只，失败 {fail_count} 只")
    print("=" * 60)
    
    if success_count > 0:
        print("✓ 港股数据采集功能修复成功！")
    else:
        print("✗ 港股数据采集仍有问题，需要进一步调试")

if __name__ == "__main__":
    test_hk_data_fetch()
