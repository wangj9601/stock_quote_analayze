#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试报告数据
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend_core.strategies.pvfrs.admin_interface import create_admin_interface

def debug_reports():
    """调试报告数据"""
    
    print("=== 调试报告数据 ===\n")
    
    try:
        admin_interface = create_admin_interface()
        reports = admin_interface.list_historical_reports(limit=5)
        
        print(f"获取到 {len(reports)} 条报告")
        
        for i, report in enumerate(reports, 1):
            print(f"\n报告 {i}:")
            print(f"  类型: {type(report)}")
            print(f"  属性: {dir(report)}")
            
            if hasattr(report, '__dict__'):
                print(f"  __dict__: {report.__dict__}")
            
            # 检查具体属性
            attrs_to_check = ['report_id', 'task_id', 'stock_code', 'total_return', 'created_at']
            for attr in attrs_to_check:
                if hasattr(report, attr):
                    value = getattr(report, attr)
                    print(f"  {attr}: {value} (类型: {type(value)})")
                else:
                    print(f"  {attr}: 不存在")
        
    except Exception as e:
        print(f"调试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_reports()
