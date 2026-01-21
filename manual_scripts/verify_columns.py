import sys
import os
from sqlalchemy import text, inspect

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, current_dir)

from backend_api.database import engine

def check_columns():
    print("正在检查 pvfrs_backtest_results_enhanced 表的列...")
    inspector = inspect(engine)
    columns = inspector.get_columns('pvfrs_backtest_results_enhanced')
    column_names = [col['name'] for col in columns]
    print(f"存在列: {column_names}")
    
    if 'report_id' in column_names:
        print("✅ report_id 列已存在")
    else:
        print("❌ report_id 列仍然缺失")

if __name__ == "__main__":
    check_columns()
