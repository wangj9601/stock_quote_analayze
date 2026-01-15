"""
验证PVFRS策略回测相关表的创建情况
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import inspect, text
from backend_api.database import engine, SessionLocal

def verify_pvfrs_tables():
    """验证PVFRS相关表"""
    print("="*80)
    print("PVFRS策略回测表验证")
    print("="*80)
    
    inspector = inspect(engine)
    
    # 需要验证的表
    pvfrs_tables = [
        'pvfrs_backtest_tasks',
        'pvfrs_backtest_results', 
        'pvfrs_trade_records',
        'pvfrs_equity_curves'
    ]
    
    print(f"\n数据库连接: {engine.url}\n")
    
    all_tables = inspector.get_table_names()
    pvfrs_existing = [t for t in all_tables if t.startswith('pvfrs')]
    
    print(f"找到 {len(pvfrs_existing)} 个PVFRS相关表:\n")
    
    for table_name in pvfrs_tables:
        exists = table_name in all_tables
        status = "✅" if exists else "❌"
        print(f"{status} {table_name}")
        
        if exists:
            # 获取列信息
            columns = inspector.get_columns(table_name)
            print(f"   列数: {len(columns)}")
            
            # 获取索引信息
            indexes = inspector.get_indexes(table_name)
            print(f"   索引数: {len(indexes)}")
            
            # 获取外键信息
            foreign_keys = inspector.get_foreign_keys(table_name)
            if foreign_keys:
                print(f"   外键数: {len(foreign_keys)}")
            
            # 查询记录数
            db = SessionLocal()
            try:
                result = db.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                count = result.scalar()
                print(f"   记录数: {count}")
            except Exception as e:
                print(f"   记录数: 查询失败 - {str(e)}")
            finally:
                db.close()
            
            print()
    
    print("="*80)
    print("\n详细表结构:\n")
    
    for table_name in pvfrs_tables:
        if table_name in all_tables:
            print(f"📋 {table_name}")
            print("-"*80)
            
            columns = inspector.get_columns(table_name)
            print("列:")
            for col in columns:
                nullable = "NULL" if col['nullable'] else "NOT NULL"
                pk = "PRIMARY KEY" if col.get('primary_key') else ""
                print(f"  • {col['name']:<25} {str(col['type']):<20} {nullable:<10} {pk}")
            
            # 索引
            indexes = inspector.get_indexes(table_name)
            if indexes:
                print("\n索引:")
                for idx in indexes:
                    unique = "UNIQUE" if idx['unique'] else ""
                    cols = ", ".join(idx['column_names'])
                    print(f"  • {idx['name']:<30} ({cols}) {unique}")
            
            # 外键
            foreign_keys = inspector.get_foreign_keys(table_name)
            if foreign_keys:
                print("\n外键:")
                for fk in foreign_keys:
                    const_cols = ", ".join(fk['constrained_columns'])
                    ref_cols = ", ".join(fk['referred_columns'])
                    print(f"  • {fk.get('name', 'unnamed'):<30} {const_cols} -> {fk['referred_table']}.{ref_cols}")
            
            print("\n")
    
    print("="*80)
    print("✅ 验证完成!")
    print("="*80)

if __name__ == "__main__":
    verify_pvfrs_tables()
