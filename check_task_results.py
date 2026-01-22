#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查任务结果和交易记录的关联关系
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 数据库连接
DATABASE_URL = "postgresql+psycopg2://postgres:qidianspacetime@localhost:5446/stock_analysis"

def check_task_results():
    """检查任务结果和交易记录的关联"""
    
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        print("=== 检查任务结果和交易记录关联 ===\n")
        
        task_id = "pvfrs_bt_69059774_141752"
        
        # 查询任务的所有结果
        results_query = text("""
            SELECT id, task_id, stock_code, backtest_date, created_at
            FROM pvfrs_backtest_results_enhanced 
            WHERE task_id = :task_id
            ORDER BY created_at
        """)
        
        results = session.execute(results_query, {'task_id': task_id}).fetchall()
        
        print(f"任务 {task_id} 有 {len(results)} 个结果:\n")
        
        for i, result in enumerate(results, 1):
            print(f"--- 结果 {i} ---")
            print(f"结果ID: {result.id}")
            print(f"任务ID: {result.task_id}")
            print(f"股票代码: {result.stock_code}")
            print(f"回测日期: {result.backtest_date}")
            print(f"创建时间: {result.created_at}")
            
            # 查询该结果的交易记录
            trades_query = text("""
                SELECT id, stock_code, trade_date, entry_time, exit_time, 
                       entry_price, exit_price, exit_reason
                FROM pvfrs_trade_records_enhanced 
                WHERE result_id = :result_id
                ORDER BY trade_date
            """)
            
            trades = session.execute(trades_query, {'result_id': result.id}).fetchall()
            
            print(f"交易记录数: {len(trades)}")
            
            completed_count = 0
            for j, trade in enumerate(trades, 1):
                is_completed = bool(trade.exit_reason) or (trade.exit_price and trade.exit_price > 0)
                if is_completed:
                    completed_count += 1
                    
                if j <= 3:  # 只显示前3条
                    print(f"  交易{j}: {trade.stock_code} - {trade.entry_time} -> {trade.exit_time} "
                          f"({trade.exit_price}, {trade.exit_reason}) {'[已完成]' if is_completed else '[持仓中]'}")
            
            if len(trades) > 3:
                print(f"  ... 还有 {len(trades) - 3} 条交易记录")
            
            print(f"已完成交易: {completed_count}/{len(trades)}")
            print()
        
        # 查询所有已完成的交易记录
        completed_trades_query = text("""
            SELECT tr.id, tr.result_id, tr.stock_code, tr.exit_time, tr.exit_price, tr.exit_reason,
                   br.task_id, br.backtest_date
            FROM pvfrs_trade_records_enhanced tr
            JOIN pvfrs_backtest_results_enhanced br ON tr.result_id = br.id
            WHERE tr.exit_reason IS NOT NULL AND tr.exit_reason != ''
            ORDER BY tr.created_at DESC
            LIMIT 10
        """)
        
        completed_trades = session.execute(completed_trades_query).fetchall()
        
        print(f"=== 所有已完成的交易记录（前10条） ===\n")
        
        for trade in completed_trades:
            print(f"交易ID: {trade.id}, 结果ID: {trade.result_id}")
            print(f"任务ID: {trade.task_id}, 股票: {trade.stock_code}")
            print(f"退出时间: {trade.exit_time}, 价格: {trade.exit_price}, 原因: {trade.exit_reason}")
            print(f"回测日期: {trade.backtest_date}")
            print()
        
    except Exception as e:
        print(f"❌ 检查失败: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        session.close()

if __name__ == "__main__":
    check_task_results()
