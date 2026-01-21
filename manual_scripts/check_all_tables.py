import sys
import os
from sqlalchemy import text, inspect

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, current_dir)

from backend_api.database import engine

def check_all_tables():
    inspector = inspect(engine)
    tables = [
        'pvfrs_backtest_tasks_enhanced',
        'pvfrs_backtest_results_enhanced',
        'pvfrs_trade_records_enhanced',
        'pvfrs_equity_curves_enhanced'
    ]
    
    for table in tables:
        print(f"\n--- 检查表: {table} ---")
        try:
            columns = inspector.get_columns(table)
            column_names = [col['name'] for col in columns]
            print(f"列数: {len(column_names)}")
            print(f"所有列: {column_names}")
        except Exception as e:
            print(f"❌ 检查表 {table} 不存在或出错: {e}")

if __name__ == "__main__":
    check_all_tables()
