#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查报告详细信息
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 数据库连接
DATABASE_URL = "postgresql+psycopg2://postgres:qidianspacetime@localhost:5446/stock_analysis"

def check_report_details():
    """检查报告详细信息"""
    
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        print("=== 检查报告详细信息 ===\n")
        
        # 查看pvfrs_backtest_results_enhanced表中的数据
        query = text("""
            SELECT report_id, task_id, stock_code, created_at
            FROM pvfrs_backtest_results_enhanced
            ORDER BY created_at DESC
            LIMIT 5
        """)
        
        results = session.execute(query).fetchall()
        
        print("pvfrs_backtest_results_enhanced 表数据:")
        for result in results:
            print(f"  报告ID: {result[0]}")
            print(f"  任务ID: {result[1]}")
            print(f"  股票代码: {result[2]}")
            print(f"  创建时间: {result[3]}")
            print()
        
        # 查看任务表中的股票信息
        task_query = text("""
            SELECT task_id, stock_codes, stock_list
            FROM pvfrs_backtest_tasks_enhanced
            WHERE task_id IN (
                SELECT DISTINCT task_id 
                FROM pvfrs_backtest_results_enhanced 
                LIMIT 3
            )
        """)
        
        task_results = session.execute(task_query).fetchall()
        
        print("对应的任务信息:")
        for task in task_results:
            print(f"  任务ID: {task[0]}")
            print(f"  股票代码: {task[1]}")
            print(f"  股票列表: {task[2]}")
            print()
        
    except Exception as e:
        print(f"❌ 检查失败: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        session.close()

if __name__ == "__main__":
    check_report_details()
