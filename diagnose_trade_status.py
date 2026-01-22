#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
诊断交易状态问题
检查为什么已止盈退出的交易还显示持仓中
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import json
from datetime import datetime

# 数据库连接
DATABASE_URL = "postgresql+psycopg2://postgres:qidianspacetime@localhost:5446/stock_analysis"

def diagnose_trade_records():
    """诊断交易记录状态"""
    
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        print("=== 诊断交易记录状态 ===\n")
        
        # 查询最近的交易记录
        query = text("""
            SELECT 
                result_id,
                stock_code,
                market,
                trade_date,
                entry_time,
                exit_time,
                entry_price,
                exit_price,
                quantity,
                pnl,
                pnl_percent,
                exit_reason,
                created_at
            FROM pvfrs_trade_records_enhanced 
            ORDER BY created_at DESC 
            LIMIT 10
        """)
        
        results = session.execute(query).fetchall()
        
        if not results:
            print("❌ 没有找到交易记录")
            return
        
        print(f"📊 找到 {len(results)} 条最近的交易记录:\n")
        
        for i, row in enumerate(results, 1):
            print(f"--- 交易记录 {i} ---")
            print(f"结果ID: {row.result_id}")
            print(f"股票代码: {row.stock_code}")
            print(f"市场: {row.market}")
            print(f"交易日期: {row.trade_date}")
            print(f"入场时间: {row.entry_time}")
            print(f"出场时间: {row.exit_time}")
            print(f"入场价格: {row.entry_price}")
            print(f"出场价格: {row.exit_price}")
            print(f"数量: {row.quantity}")
            print(f"盈亏: {row.pnl}")
            print(f"盈亏比例: {row.pnl_percent}")
            print(f"退出原因: {row.exit_reason}")
            print(f"创建时间: {row.created_at}")
            
            # 判断交易状态
            exit_price = float(row.exit_price) if row.exit_price else 0
            exit_reason = row.exit_reason
            exit_time = row.exit_time
            
            is_completed = bool(exit_reason) or (exit_price > 0)
            
            print(f"🔍 交易状态分析:")
            print(f"   - 有退出原因: {bool(exit_reason)}")
            print(f"   - 出场价格 > 0: {exit_price > 0} (价格: {exit_price})")
            print(f"   - 交易已完成: {is_completed}")
            print(f"   - 前端显示: {'已完成' if exit_time else '持仓中'}")
            
            if is_completed and not exit_time:
                print("   ⚠️  问题: 交易已完成但 exit_time 为空，前端会显示'持仓中'")
            elif not is_completed and exit_time:
                print("   ⚠️  问题: 交易未完成但 exit_time 有值")
            elif is_completed and exit_time:
                print("   ✅ 正常: 交易已完成且 exit_time 有值")
            else:
                print("   ℹ️  正常: 交易未完成且 exit_time 为空")
            
            print()
        
        # 检查有问题的记录
        print("\n=== 检查有问题的记录 ===")
        
        problematic_query = text("""
            SELECT COUNT(*) as count
            FROM pvfrs_trade_records_enhanced 
            WHERE (exit_reason IS NOT NULL AND exit_reason != '') 
            OR (exit_price > 0)
        """)
        
        completed_count = session.execute(problematic_query).scalar()
        
        null_exit_time_query = text("""
            SELECT COUNT(*) as count
            FROM pvfrs_trade_records_enhanced 
            WHERE exit_time IS NULL
            AND ((exit_reason IS NOT NULL AND exit_reason != '') 
            OR (exit_price > 0))
        """)
        
        problematic_count = session.execute(null_exit_time_query).scalar()
        
        print(f"已完成的交易总数: {completed_count}")
        print(f"有问题的交易数 (已完成但exit_time为空): {problematic_count}")
        
        if problematic_count > 0:
            print(f"\n❌ 发现 {problematic_count} 条有问题的交易记录")
            
            # 显示具体的问题记录
            fix_query = text("""
                SELECT task_id, stock_code, exit_price, exit_reason, exit_date
                FROM pvfrs_trade_records_enhanced 
                WHERE exit_time IS NULL
                AND ((exit_reason IS NOT NULL AND exit_reason != '') 
                OR (exit_price > 0))
                LIMIT 5
            """)
            
            problem_records = session.execute(fix_query).fetchall()
            
            print("\n需要修复的交易记录:")
            for record in problem_records:
                print(f"  - 任务: {record.task_id}, 股票: {record.stock_code}, "
                      f"出场价格: {record.exit_price}, 原因: {record.exit_reason}, "
                      f"出场日期: {record.exit_date}")
        
    except Exception as e:
        print(f"❌ 诊断失败: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        session.close()

def fix_trade_records():
    """修复有问题的交易记录"""
    
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        print("\n=== 修复交易记录 ===")
        
        # 查找需要修复的记录
        find_query = text("""
            SELECT id, result_id, stock_code, trade_date, exit_price, exit_reason
            FROM pvfrs_trade_records_enhanced 
            WHERE exit_time IS NULL
            AND ((exit_reason IS NOT NULL AND exit_reason != '') 
            OR (exit_price > 0))
        """)
        
        records_to_fix = session.execute(find_query).fetchall()
        
        if not records_to_fix:
            print("✅ 没有需要修复的记录")
            return
        
        print(f"🔧 找到 {len(records_to_fix)} 条需要修复的记录")
        
        fixed_count = 0
        for record in records_to_fix:
            try:
                # 从 trade_date 推断 exit_time
                exit_time = None
                if record.trade_date:
                    exit_time = datetime.combine(record.trade_date, datetime.min.time())
                
                # 更新记录
                update_query = text("""
                    UPDATE pvfrs_trade_records_enhanced 
                    SET exit_time = :exit_time
                    WHERE id = :id
                """)
                
                session.execute(update_query, {
                    'exit_time': exit_time,
                    'id': record.id
                })
                
                print(f"✅ 修复记录: 结果 {record.result_id}, 股票 {record.stock_code}")
                fixed_count += 1
                
            except Exception as e:
                print(f"❌ 修复失败: 结果 {record.result_id}, 股票 {record.stock_code}, 错误: {str(e)}")
        
        session.commit()
        print(f"\n🎉 成功修复 {fixed_count} 条记录")
        
    except Exception as e:
        print(f"❌ 修复失败: {str(e)}")
        session.rollback()
        import traceback
        traceback.print_exc()
    
    finally:
        session.close()

if __name__ == "__main__":
    diagnose_trade_records()
    
    # 询问是否修复
    response = input("\n是否修复有问题的记录? (y/N): ").strip().lower()
    if response == 'y':
        fix_trade_records()
        print("\n修复完成！请重新检查前端显示。")
